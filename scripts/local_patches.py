#!/usr/bin/env python3
"""Local compatibility patches for the installed OpenClaw bundle.

These are reviewed, minimal edits to the shipped minified dist files. A package
update replaces them, so this script re-applies or verifies them. Run on the
server with permission to read/write the openclaw dist directory (sudo).

Usage:
  python3 scripts/local_patches.py --dist /path/to/openclaw/dist --check
  python3 scripts/local_patches.py --dist /path/to/openclaw/dist --apply

Each patch reports one of: ALREADY_APPLIED, APPLIED, UPSTREAM_CHANGED,
NOT_FOUND. UPSTREAM_CHANGED means the exact upstream text was not found, so the
patch was NOT applied and must be re-reviewed against the new source.
"""
from __future__ import annotations
import argparse, datetime, hashlib, pathlib, shutil, sys

BACKUP_ROOT = pathlib.Path("/var/lib/oracle-ai-stack")

# Patch contract: (file glob, [(old, new) exact replacements]). The glob resolves
# the hashed bundle name; every replacement must match exactly once or the patch
# reports UPSTREAM_CHANGED and nothing is written.

PLUGINS_ROUTE_PATCH = (
    "control-ui-share-*.mjs",
    [
        (
            'if (pathname === "/plugins" || pathname.startsWith("/plugins/")) return { kind: "not-control-ui" };',
            'if (pathname.startsWith("/plugins/")) return { kind: "not-control-ui" };',
        ),
    ],
)

CLAWHUB_VERSIONS_PATCH = (
    "management-service-*.mjs",
    [
        (
            "\tconst version = params.version ?? catalog.latestVersion;\n"
            "\tconst [versionsValue, versionValue, readme, security] = await Promise.all([\n"
            "\t\tfetchClawHubJson({\n"
            "\t\t\t...shared,\n"
            "\t\t\tpath: `/api/v1/packages/${encodeURIComponent(params.packageName)}/versions`,\n"
            "\t\t\tsearch: { limit: \"10\" }\n"
            "\t\t}),",
            "\tconst version = params.version ?? catalog.latestVersion;\n"
            "\tlet versionHistoryError;\n"
            "\tconst [versionsValue, versionValue, readme, security] = await Promise.all([\n"
            "\t\tfetchClawHubJson({\n"
            "\t\t\t...shared,\n"
            "\t\t\tpath: `/api/v1/packages/${encodeURIComponent(params.packageName)}/versions`,\n"
            "\t\t\tsearch: { limit: \"10\" }\n"
            "\t\t}).catch((error) => {\n"
            "\t\t\tif (!(error instanceof ClawHubRequestError) || error.status < 500 || error.status >= 600) throw error;\n"
            "\t\t\tversionHistoryError = error;\n"
            "\t\t\treturn void 0;\n"
            "\t\t}),",
        ),
        (
            "\tif (versionValue !== void 0 && !isRecord(versionValue)) throw new Error(\"Malformed ClawHub plugin version response: expected an object.\");\n"
            "\tconst versionRecord = versionValue ? readOptionalRecord(versionValue, \"version\", \"plugin version response\") : void 0;\n"
            "\tconst manifest = parseManifest(",
            "\tif (versionValue !== void 0 && !isRecord(versionValue)) throw new Error(\"Malformed ClawHub plugin version response: expected an object.\");\n"
            "\tconst versionRecord = versionValue ? readOptionalRecord(versionValue, \"version\", \"plugin version response\") : void 0;\n"
            "\tif (versionHistoryError && !versionRecord) throw versionHistoryError;\n"
            "\tconst detailReadme = versionHistoryError\n"
            "\t\t? `> **OpenClaw registry warning:** ClawHub version history is unavailable (HTTP ${versionHistoryError.status}). Only the independently fetched release is shown; this is not a complete version history. Package and release checks have not been bypassed.\\n\\n${readme ?? \"\"}`\n"
            "\t\t: readme;\n"
            "\tconst manifest = parseManifest(",
        ),
        (
            "\t\t...readme ? { readme } : {},",
            "\t\t...detailReadme ? { readme: detailReadme } : {},",
        ),
        (
            "\t\tversions: parseVersions(versionsValue),",
            "\t\tversions: parseVersions(versionHistoryError ? { items: [versionRecord] } : versionsValue),\n"
            "\t\t...versionHistoryError ? { versionHistoryError: {\n"
            "\t\t\tstatus: versionHistoryError.status,\n"
            "\t\t\tmessage: versionHistoryError.message\n"
            "\t\t} } : {},",
        ),
    ],
)

PATCHES = {
    "plugins-route": PLUGINS_ROUTE_PATCH,
    "clawhub-versions-5xx-fallback": CLAWHUB_VERSIONS_PATCH,
}


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve_file(dist: pathlib.Path, pattern: str) -> pathlib.Path | None:
    # Hashed bundle names: the real module is the largest match; re-export stubs are tiny.
    matches = [p for p in dist.glob(pattern) if p.is_file()]
    if not matches:
        return None
    return max(matches, key=lambda p: p.stat().st_size)


def patch_status(path: pathlib.Path, replacements: list[tuple[str, str]]) -> str:
    text = path.read_text()
    applied = sum(1 for old, new in replacements if new in text)
    pending = sum(1 for old, new in replacements if old in text)
    if applied == len(replacements):
        return "ALREADY_APPLIED"
    if pending == len(replacements):
        return "APPLYABLE"
    return "UPSTREAM_CHANGED"


def apply_patch(path: pathlib.Path, replacements: list[tuple[str, str]], backup_dir: pathlib.Path) -> str:
    text = path.read_text()
    status = patch_status(path, replacements)
    if status == "ALREADY_APPLIED":
        return "ALREADY_APPLIED"
    if status != "APPLYABLE":
        return "UPSTREAM_CHANGED"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / (path.name + ".before")
    shutil.copyfile(path, backup)
    (backup_dir / (path.name + ".sha256")).write_text(sha256(path) + "  " + path.name + "\n")
    for old, new in replacements:
        assert text.count(old) == 1, f"expected exactly one match, got {text.count(old)}"
        text = text.replace(old, new)
    path.write_text(text)
    return "APPLIED"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dist", type=pathlib.Path, required=True,
                    help="openclaw dist directory (contains the hashed .mjs bundles)")
    ap.add_argument("--check", action="store_true", help="report status only, do not write")
    ap.add_argument("--apply", action="store_true", help="apply patches that are APPLYABLE")
    ap.add_argument("--backup-dir", type=pathlib.Path, default=None,
                    help="backup directory (default: /var/lib/oracle-ai-stack/local-patches-<ts>)")
    args = ap.parse_args()
    if not args.check and not args.apply:
        ap.error("pass --check or --apply")
    dist = args.dist.expanduser()
    if not dist.is_dir():
        print(f"NOT_FOUND: dist directory {dist} does not exist", file=sys.stderr)
        return 2
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = args.backup_dir or (BACKUP_ROOT / f"local-patches-{stamp}")
    worst = 0
    for name, (pattern, replacements) in PATCHES.items():
        path = resolve_file(dist, pattern)
        if path is None:
            print(f"{name}: NOT_FOUND ({pattern})")
            worst = max(worst, 2)
            continue
        if args.check:
            status = patch_status(path, replacements)
        else:
            status = apply_patch(path, replacements, backup_dir)
        print(f"{name}: {status} ({path.name})")
        if status in ("UPSTREAM_CHANGED", "NOT_FOUND"):
            worst = max(worst, 2)
    if not args.check and worst == 0:
        print(f"backups: {backup_dir}")
        print("restart the gateway unit to load patched modules")
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
