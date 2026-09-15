#!/usr/bin/env python3
"""Agent-friendly, non-mutating preflight and explicit installer coordinator."""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import pathlib
import shutil
import sys
from dataclasses import dataclass

import oci_provision
import stack
from package_manifest import PackageError, verify as verify_package
from stacklib import StackError, load_env, private_file

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_HOME = pathlib.Path.home() / ".config/oracle-ai-stack"
TOOLS = ("git", "ssh", "ssh-keygen", "ssh-keyscan")
COMMON_SETTINGS = ("DOMAIN", "CLOUDFLARE_API_TOKEN")
OCI_SETTINGS = ("OCI_USER", "OCI_FINGERPRINT", "OCI_TENANCY", "OCI_REGION", "OCI_KEY_FILE")


@dataclass(frozen=True)
class Options:
    secrets: pathlib.Path = DEFAULT_HOME / "secrets.env"
    stage: pathlib.Path = DEFAULT_HOME / "stage"
    state: pathlib.Path = DEFAULT_HOME / "state"
    apply: bool = False
    review_notes: pathlib.Path | None = None
    host_fingerprint: str | None = None


def _capture(call, *args):
    """Keep delegated CLI progress off the machine-readable stdout surface."""
    with contextlib.redirect_stdout(io.StringIO()):
        return call(*args)


def _safe_error(exc: Exception, cfg: dict[str, str] | None = None) -> str:
    message = str(exc) or type(exc).__name__
    for key, value in sorted((cfg or {}).items(), key=lambda item: len(str(item[1])), reverse=True):
        if value:
            message = message.replace(str(value), f"<redacted:{key}>")
    return message


def _source_status(stage: pathlib.Path) -> dict[str, str]:
    if not stage.exists():
        return {"stage": "MISSING", "review": "REQUIRED"}
    required = (stage / "sources.lock.json", stage / "deployment.lock.json")
    if not all(path.is_file() for path in required):
        return {"stage": "INVALID", "review": "REQUIRED", "detail": "prepared source locks are missing"}
    try:
        stack.verify_stage(stage, reviewed=False)
        stack.verify_core(stage)
    except (StackError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        return {"stage": "INVALID", "review": "REQUIRED", "detail": _safe_error(exc)}
    if not (stage / "review.receipt.json").is_file():
        return {"stage": "PREPARED", "review": "REQUIRED"}
    try:
        stack.verify_all(stage)
    except (StackError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        return {"stage": "PREPARED", "review": "STALE", "detail": _safe_error(exc)}
    return {"stage": "PREPARED", "review": "VALID"}


def _saved_handoff(cfg: dict[str, str], state: pathlib.Path) -> dict:
    path = state / "oci-handoff.json"
    if cfg.get("ORACLE_HOST") or not path.exists():
        return {}
    private_file(path)
    saved = json.loads(path.read_text())
    for key in ("DOMAIN", "OCI_TENANCY", "OCI_REGION"):
        if cfg.get(key) and cfg[key] != saved.get(key):
            raise StackError("OCI handoff belongs to another deployment; use a separate --state directory")
    if not all(saved.get(key) for key in ("ORACLE_HOST", "ORACLE_SSH_KEY", "SSH_PORT", "SSH_FINGERPRINT")):
        raise StackError("OCI handoff is incomplete; inspect private local state")
    return saved


def _known_hosts_path(cfg: dict[str, str], state: pathlib.Path, saved_handoff: bool) -> pathlib.Path:
    if saved_handoff:
        return state / "known_hosts"
    return pathlib.Path(cfg.get("SSH_KNOWN_HOSTS") or pathlib.Path.home() / ".ssh/known_hosts").expanduser()


def _host_trusted(cfg: dict[str, str], path: pathlib.Path) -> bool:
    if not path.is_file() or not shutil.which("ssh-keygen"):
        return False
    host = cfg.get("ORACLE_HOST", "")
    if not host:
        return False
    query = host if cfg.get("SSH_PORT", "22") == "22" else f"[{host}]:{cfg['SSH_PORT']}"
    result = stack.run(["ssh-keygen", "-F", query, "-f", str(path)], check=False)
    return result.returncode == 0 and bool(result.stdout.strip())


def _base(options: Options) -> dict:
    return {
        "schema": 1,
        "state": "PREFLIGHT",
        "mode": "apply" if options.apply else "preflight",
        "route": "unknown",
        "paths": {
            "secrets": str(options.secrets.expanduser()),
            "stage": str(options.stage.expanduser()),
            "state": str(options.state.expanduser()),
        },
        "package": "UNKNOWN",
        "source": _source_status(options.stage.expanduser()),
        "missing": {"settings": [], "paths": [], "executables": []},
        "required_inputs": [],
        "user_prerequisites": [],
    }


def _missing_inputs(cfg: dict[str, str], route: str) -> list[str]:
    required = list(COMMON_SETTINGS)
    mode = cfg.get("ACCESS_MODE", "public")
    if mode == "tailscale" and route == "new_oci_host":
        required.append("TAILSCALE_AUTH_KEY")
    if route == "existing_host":
        if not cfg.get("ORACLE_HOST"):
            required.append("ORACLE_HOST")
        required.append("ORACLE_SSH_KEY")
        if mode == "public":
            try:
                stack.public_ip_for(cfg)
            except StackError:
                required.append("PUBLIC_IP")
    else:
        required.extend(OCI_SETTINGS)
        create_network = cfg.get("OCI_CREATE_NETWORK") or ("false" if cfg.get("OCI_SUBNET") else "true")
        required.append("OCI_SSH_ALLOWED_CIDR" if create_network == "true" else "OCI_SUBNET")
    return [key for key in required if not cfg.get(key)]


def _user_prerequisites(missing: list[str]) -> list[str]:
    actions = []
    if "DOMAIN" in missing:
        actions.append("domain_ownership")
    if "CLOUDFLARE_API_TOKEN" in missing:
        actions.append("dns_zone_access")
    if any(key in missing for key in OCI_SETTINGS):
        actions.append("oci_account_and_registered_api_signing_key")
    if "TAILSCALE_AUTH_KEY" in missing:
        actions.append("tailscale_account_membership")
    return actions


def run(options: Options) -> dict:
    options = Options(
        secrets=options.secrets.expanduser(), stage=options.stage.expanduser(),
        state=options.state.expanduser(), apply=options.apply,
        review_notes=options.review_notes.expanduser() if options.review_notes else None,
        host_fingerprint=options.host_fingerprint,
    )
    result = _base(options)
    result["missing"]["executables"] = [name for name in TOOLS if not shutil.which(name)]
    if sys.version_info < (3, 11):
        result["missing"]["executables"].append("python>=3.11")

    try:
        verify_package(ROOT)
        result["package"] = "VALID"
    except (PackageError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        result["package"] = "INVALID"
        result["package_error"] = _safe_error(exc)

    cfg: dict[str, str] = {}
    if not options.secrets.is_file():
        result["missing"]["paths"].append({"name": "SECRETS_FILE", "path": str(options.secrets)})
    else:
        try:
            cfg = load_env(options.secrets)
        except (StackError, OSError, ValueError) as exc:
            result["state"] = "INPUT_INVALID"
            result["error"] = _safe_error(exc)
            return result

    if result["missing"]["paths"]:
        result["state"] = "INPUT_REQUIRED"
        result["required_inputs"] = ["secrets_file"]
        return result

    try:
        saved_handoff = _saved_handoff(cfg, options.state)
    except (StackError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        result["state"] = "INPUT_INVALID"
        result["error"] = _safe_error(exc, cfg)
        return result
    route = "existing_host" if cfg.get("ORACLE_HOST") or saved_handoff else "new_oci_host"
    result["route"] = route
    route_cfg = dict(cfg)
    if saved_handoff:
        for key in ("ORACLE_HOST", "ORACLE_SSH_USER", "ORACLE_SSH_KEY", "SSH_PORT", "PUBLIC_IP"):
            if saved_handoff.get(key):
                route_cfg[key] = saved_handoff[key]
        if saved_handoff.get("ACCESS_MODE") and not cfg.get("_ACCESS_MODE_EXPLICIT"):
            route_cfg["ACCESS_MODE"] = saved_handoff["ACCESS_MODE"]
    missing = _missing_inputs(route_cfg, route)
    result["missing"]["settings"] = missing
    result["user_prerequisites"] = _user_prerequisites(missing)

    for setting in ("ORACLE_SSH_KEY",) if route == "existing_host" else ():
        if route_cfg.get(setting) and not pathlib.Path(route_cfg[setting]).expanduser().is_file():
            path = pathlib.Path(route_cfg[setting]).expanduser()
            result["missing"]["paths"].append({"name": setting, "path": str(path)})
    if route == "new_oci_host" and cfg.get("OCI_KEY_FILE") and not pathlib.Path(cfg["OCI_KEY_FILE"]).expanduser().is_file():
        result["missing"]["paths"].append({"name": "OCI_KEY_FILE", "path": str(pathlib.Path(cfg["OCI_KEY_FILE"]).expanduser())})

    if missing or result["missing"]["paths"]:
        result["state"] = "INPUT_REQUIRED"
        result["required_inputs"] = missing + [entry["name"] for entry in result["missing"]["paths"]]
        return result
    try:
        private_file(pathlib.Path(route_cfg["ORACLE_SSH_KEY"]).expanduser() if route == "existing_host"
                     else pathlib.Path(cfg["OCI_KEY_FILE"]).expanduser())
        if route == "new_oci_host":
            oci_provision.normalized(cfg)
    except (StackError, OSError, ValueError, KeyError) as exc:
        result["state"] = "INPUT_INVALID"
        result["error"] = _safe_error(exc, cfg)
        return result
    if result["missing"]["executables"]:
        result["state"] = "PREREQUISITES_REQUIRED"
        result["required_inputs"] = ["local_executables"]
        return result
    if result["package"] != "VALID":
        result["state"] = "PACKAGE_INVALID"
        return result

    source = result["source"]
    if source["stage"] == "MISSING":
        if not options.apply:
            result["state"] = "PREPARE_REQUIRED"
            return result
        try:
            _capture(stack.prepare, options.stage, stack.access_mode(cfg))
        except (StackError, OSError, ValueError, KeyError) as exc:
            result["state"] = "PREPARE_BLOCKED"
            result["error"] = _safe_error(exc, cfg)
            return result
        result["source"] = _source_status(options.stage)
        if result["source"]["stage"] != "PREPARED":
            result["state"] = "PREPARE_BLOCKED"
            result["required_inputs"] = ["new_stage_path"]
            return result
        result["source"]["review"] = "REQUIRED"
        result["state"] = "REVIEW_REQUIRED"
        result["required_inputs"] = ["source_review", "review_notes"]
        return result

    if source["stage"] == "INVALID":
        result["state"] = "STAGE_INVALID"
        result["required_inputs"] = ["new_stage_path"]
        return result
    if source["review"] != "VALID":
        if not options.apply or not options.review_notes:
            result["state"] = "REVIEW_REQUIRED"
            result["required_inputs"] = ["source_review", "review_notes"]
            return result
        if not options.review_notes.is_file():
            result["state"] = "INPUT_REQUIRED"
            result["missing"]["paths"].append({"name": "REVIEW_NOTES", "path": str(options.review_notes)})
            result["required_inputs"] = ["review_notes"]
            return result
        try:
            _capture(stack.seal_all, options.stage, options.review_notes)
            result["source"] = _source_status(options.stage)
            if result["source"]["review"] != "VALID":
                raise StackError("Source review receipt did not validate after sealing")
        except (StackError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            result["state"] = "REVIEW_BLOCKED"
            result["error"] = _safe_error(exc, cfg)
            return result

    if route == "existing_host" and not saved_handoff:
        known_hosts = _known_hosts_path(cfg, options.state, False)
        if not _host_trusted(cfg, known_hosts):
            result["host_trust"] = "REQUIRED"
            if not options.apply or not options.host_fingerprint:
                result["state"] = "HOST_TRUST_REQUIRED"
                result["required_inputs"] = ["independently_verified_host_fingerprint"]
                return result
            try:
                _capture(stack.trust_host, cfg, options.host_fingerprint)
            except (StackError, OSError, ValueError, KeyError) as exc:
                result["state"] = "HOST_TRUST_BLOCKED"
                result["error"] = _safe_error(exc, cfg)
                return result
            if not _host_trusted(cfg, known_hosts):
                result["state"] = "HOST_TRUST_BLOCKED"
                result["error"] = "Verified host key enrollment did not produce a matching known-host entry"
                return result
        result["host_trust"] = "VALID"
    elif saved_handoff:
        result["host_trust"] = "VALID" if _host_trusted(route_cfg, _known_hosts_path(route_cfg, options.state, True)) else "OCI_HANDOFF_ENROLLMENT_PENDING"

    if not options.apply:
        result["state"] = "READY_TO_APPLY"
        return result

    try:
        effective = _capture(stack.hydrate_handoff, cfg, options.state)
        installation = _capture(stack.setup, effective, options.stage, options.state)
    except (StackError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        result["state"] = "APPLY_BLOCKED"
        result["error"] = _safe_error(exc, cfg)
        return result
    result["state"] = "INSTALLED_PENDING_ACCEPTANCE"
    result["star"] = installation["star"]
    result["pending"] = [
        "profile_model_authentication", "profile_model_probe",
        "browser_device_approval", "client_acceptance", "backup_restore_drill",
    ]
    return result


def parse_args(argv=None) -> Options:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="perform explicit preparation or installation mutations")
    parser.add_argument("--secrets", type=pathlib.Path, default=DEFAULT_HOME / "secrets.env")
    parser.add_argument("--stage", type=pathlib.Path, default=DEFAULT_HOME / "stage")
    parser.add_argument("--state", type=pathlib.Path, default=DEFAULT_HOME / "state")
    parser.add_argument("--review-notes", type=pathlib.Path)
    parser.add_argument("--host-fingerprint")
    args = parser.parse_args(argv)
    return Options(args.secrets, args.stage, args.state, args.apply, args.review_notes, args.host_fingerprint)


def main(argv=None) -> int:
    result = run(parse_args(argv))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["state"] in ("READY_TO_APPLY", "INSTALLED_PENDING_ACCEPTANCE") else 2


if __name__ == "__main__":
    raise SystemExit(main())
