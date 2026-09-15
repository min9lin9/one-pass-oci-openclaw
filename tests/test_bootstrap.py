import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import bootstrap  # noqa: E402
import stack  # noqa: E402
from stacklib import StackError, digest_tree  # noqa: E402


class BootstrapFixture(unittest.TestCase):
    def write_env(self, root, values):
        path = root / "secrets.env"
        path.write_text("".join(f"{key}={value}\n" for key, value in values.items()))
        path.chmod(0o600)
        return path

    def reviewed_stage(self, root):
        stage = root / "stage"
        (stage / "core/caddy-dns-cloudflare").mkdir(parents=True)
        for name in ("oci-instance-creator", "gbrain", "ecc"):
            (stage / "aux" / name).mkdir(parents=True)
        sources = {"schema": 1, "sources": []}
        (stage / "sources.lock.json").write_text(json.dumps(sources))
        empty_hash = digest_tree(stage / "core/caddy-dns-cloudflare")
        lock = {
            "schema": 3,
            "bootstrap": {},
            "caddy_tree_sha256": empty_hash,
            "aux_sources": {
                name: {"sha256": digest_tree(stage / "aux" / name)}
                for name in ("oci-instance-creator", "gbrain", "ecc")
            },
        }
        (stage / "deployment.lock.json").write_text(json.dumps(lock))
        receipt = {
            "lock_sha256": hashlib.sha256((stage / "sources.lock.json").read_bytes()).hexdigest(),
            "deployment_lock_sha256": hashlib.sha256((stage / "deployment.lock.json").read_bytes()).hexdigest(),
        }
        (stage / "review.receipt.json").write_text(json.dumps(receipt))
        return stage

    def existing_values(self, root, *, secret="cloudflare-test-secret"):
        key = root / "ssh-key"
        key.write_text("fixture private key")
        key.chmod(0o600)
        known = root / "known_hosts"
        known.write_text("example-host.test ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFixtureOnly\n")
        return {
            "ACCESS_MODE": "public",
            "DOMAIN": "example.com",
            "CLOUDFLARE_API_TOKEN": secret,
            "ORACLE_HOST": "example-host.test",
            "PUBLIC_IP": "8.8.4.4",
            "ORACLE_SSH_KEY": str(key),
            "SSH_KNOWN_HOSTS": str(known),
        }

    def options(self, root, secrets, stage, *, apply=False, notes=None, fingerprint=None):
        return bootstrap.Options(
            secrets=secrets,
            stage=stage,
            state=root / "state",
            apply=apply,
            review_notes=notes,
            host_fingerprint=fingerprint,
        )


class PreflightTests(BootstrapFixture):
    def test_existing_tailnet_host_can_reuse_enrollment_without_new_key(self):
        with tempfile.TemporaryDirectory() as td, patch.object(bootstrap, "verify_package"):
            root = pathlib.Path(td)
            values = self.existing_values(root)
            values["ACCESS_MODE"] = "tailscale"
            env = self.write_env(root, values)
            result = bootstrap.run(self.options(root, env, self.reviewed_stage(root)))
        self.assertEqual(result["state"], "READY_TO_APPLY")
        self.assertNotIn("TAILSCALE_AUTH_KEY", result["missing"]["settings"])

    def test_missing_secrets_reports_names_and_path(self):
        with tempfile.TemporaryDirectory() as td, patch.object(bootstrap, "verify_package"):
            root = pathlib.Path(td)
            result = bootstrap.run(self.options(root, root / "missing.env", root / "stage"))
        self.assertEqual(result["state"], "INPUT_REQUIRED")
        self.assertEqual(result["missing"]["paths"][0]["name"], "SECRETS_FILE")
        self.assertTrue(result["missing"]["paths"][0]["path"].endswith("missing.env"))

    def test_existing_host_does_not_require_oci_account_inputs(self):
        with tempfile.TemporaryDirectory() as td, patch.object(bootstrap, "verify_package"):
            root = pathlib.Path(td)
            env = self.write_env(root, self.existing_values(root))
            result = bootstrap.run(self.options(root, env, self.reviewed_stage(root)))
        self.assertEqual(result["route"], "existing_host")
        self.assertEqual(result["state"], "READY_TO_APPLY")
        self.assertFalse(any(name.startswith("OCI_") for name in result["missing"]["settings"]))
        self.assertNotIn("TAILSCALE_AUTH_KEY", result["missing"]["settings"])

    def test_new_host_requires_only_new_host_oci_inputs(self):
        with tempfile.TemporaryDirectory() as td, patch.object(bootstrap, "verify_package"):
            root = pathlib.Path(td)
            env = self.write_env(root, {
                "ACCESS_MODE": "public",
                "DOMAIN": "example.com",
                "CLOUDFLARE_API_TOKEN": "cloudflare-test-secret",
            })
            result = bootstrap.run(self.options(root, env, self.reviewed_stage(root)))
        self.assertEqual(result["route"], "new_oci_host")
        self.assertEqual(result["state"], "INPUT_REQUIRED")
        self.assertEqual(set(result["missing"]["settings"]), {
            "OCI_USER", "OCI_FINGERPRINT", "OCI_TENANCY", "OCI_REGION",
            "OCI_KEY_FILE", "OCI_SSH_ALLOWED_CIDR",
        })
        self.assertNotIn("TAILSCALE_AUTH_KEY", result["missing"]["settings"])

    def test_dry_run_never_calls_mutating_install_helpers(self):
        with tempfile.TemporaryDirectory() as td, patch.object(bootstrap, "verify_package"), \
             patch.object(stack, "prepare") as prepare, patch.object(stack, "seal_all") as seal, \
             patch.object(stack, "setup") as setup, patch.object(stack, "trust_host") as trust:
            root = pathlib.Path(td)
            env = self.write_env(root, self.existing_values(root))
            bootstrap.run(self.options(root, env, root / "missing-stage"))
        prepare.assert_not_called()
        seal.assert_not_called()
        setup.assert_not_called()
        trust.assert_not_called()

    def test_stale_review_is_actionable_and_not_installed(self):
        with tempfile.TemporaryDirectory() as td, patch.object(bootstrap, "verify_package"), \
             patch.object(stack, "setup") as setup:
            root = pathlib.Path(td)
            env = self.write_env(root, self.existing_values(root))
            stage = self.reviewed_stage(root)
            receipt = json.loads((stage / "review.receipt.json").read_text())
            receipt["lock_sha256"] = "0" * 64
            (stage / "review.receipt.json").write_text(json.dumps(receipt))
            result = bootstrap.run(self.options(root, env, stage, apply=True))
        self.assertEqual(result["state"], "REVIEW_REQUIRED")
        self.assertEqual(result["source"]["review"], "STALE")
        self.assertIn("review_notes", result["required_inputs"])
        setup.assert_not_called()

    def test_invalid_partial_stage_requires_a_new_stage_not_fake_review(self):
        with tempfile.TemporaryDirectory() as td, patch.object(bootstrap, "verify_package"):
            root = pathlib.Path(td)
            env = self.write_env(root, self.existing_values(root))
            stage = root / "stage"
            stage.mkdir()
            result = bootstrap.run(self.options(root, env, stage, apply=True))
        self.assertEqual(result["state"], "STAGE_INVALID")
        self.assertEqual(result["required_inputs"], ["new_stage_path"])

    def test_untrusted_existing_host_never_reaches_setup(self):
        with tempfile.TemporaryDirectory() as td, patch.object(bootstrap, "verify_package"), \
             patch.object(stack, "setup") as setup:
            root = pathlib.Path(td)
            values = self.existing_values(root)
            pathlib.Path(values["SSH_KNOWN_HOSTS"]).write_text("")
            env = self.write_env(root, values)
            result = bootstrap.run(self.options(root, env, self.reviewed_stage(root), apply=True))
        self.assertEqual(result["state"], "HOST_TRUST_REQUIRED")
        self.assertEqual(result["required_inputs"], ["independently_verified_host_fingerprint"])
        setup.assert_not_called()


class ApplyTests(BootstrapFixture):
    def test_apply_reports_pending_star_without_losing_install_result(self):
        with tempfile.TemporaryDirectory() as td, patch.object(bootstrap, "verify_package"), \
             patch.object(stack, "setup", return_value={"star": "PENDING"}):
            root = pathlib.Path(td)
            env = self.write_env(root, self.existing_values(root))
            result = bootstrap.run(self.options(root, env, self.reviewed_stage(root), apply=True))
        self.assertEqual(result["state"], "INSTALLED_PENDING_ACCEPTANCE")
        self.assertEqual(result["star"], "PENDING")

    def test_apply_invokes_existing_setup_and_reports_pending_acceptance(self):
        with tempfile.TemporaryDirectory() as td, patch.object(bootstrap, "verify_package"), \
             patch.object(stack, "setup", return_value={"star": "CONFIRMED"}) as setup:
            root = pathlib.Path(td)
            env = self.write_env(root, self.existing_values(root))
            options = self.options(root, env, self.reviewed_stage(root), apply=True)
            result = bootstrap.run(options)
        setup.assert_called_once()
        self.assertEqual(setup.call_args.args[0]["ORACLE_HOST"], "example-host.test")
        self.assertEqual(result["state"], "INSTALLED_PENDING_ACCEPTANCE")
        self.assertIn("profile_model_authentication", result["pending"])
        self.assertIn("browser_device_approval", result["pending"])
        self.assertNotEqual(result["state"], "READY")

    def test_apply_seals_explicit_review_notes_then_uses_setup(self):
        with tempfile.TemporaryDirectory() as td, patch.object(bootstrap, "verify_package"), \
             patch.object(stack, "setup", return_value={"star": "CONFIRMED"}) as setup:
            root = pathlib.Path(td)
            env = self.write_env(root, self.existing_values(root))
            stage = self.reviewed_stage(root)
            (stage / "review.receipt.json").unlink()
            notes = root / "review-notes.md"
            notes.write_text("Fixture review covered source identities, licenses, entry points, hooks, network and filesystem effects, privileges, smoke scope, and unresolved transitive dependency limits.\n")
            result = bootstrap.run(self.options(root, env, stage, apply=True, notes=notes))
        setup.assert_called_once()
        self.assertEqual(result["source"]["review"], "VALID")
        self.assertEqual(result["state"], "INSTALLED_PENDING_ACCEPTANCE")

    def test_apply_error_is_structured_and_redacts_loaded_values(self):
        secret = "do-not-disclose-this-token"
        with tempfile.TemporaryDirectory() as td, patch.object(bootstrap, "verify_package"), \
             patch.object(stack, "setup", side_effect=StackError("provider rejected " + secret)):
            root = pathlib.Path(td)
            env = self.write_env(root, self.existing_values(root, secret=secret))
            result = bootstrap.run(self.options(root, env, self.reviewed_stage(root), apply=True))
        encoded = json.dumps(result)
        self.assertEqual(result["state"], "APPLY_BLOCKED")
        self.assertIn("provider rejected", result["error"])
        self.assertNotIn(secret, encoded)

    def test_missing_stage_apply_prepares_but_never_claims_review_or_install(self):
        with tempfile.TemporaryDirectory() as td, patch.object(bootstrap, "verify_package"), \
             patch.object(stack, "prepare") as prepare, patch.object(stack, "setup") as setup:
            root = pathlib.Path(td)
            env = self.write_env(root, self.existing_values(root))
            stage = root / "stage"
            def prepare_only(where, mode):
                self.reviewed_stage(where.parent)
                (where / "review.receipt.json").unlink()
            prepare.side_effect = prepare_only
            result = bootstrap.run(self.options(root, env, stage, apply=True))
        prepare.assert_called_once_with(stage, "public")
        setup.assert_not_called()
        self.assertEqual(result["state"], "REVIEW_REQUIRED")
        self.assertEqual(result["source"]["review"], "REQUIRED")

    def test_cli_subprocess_missing_file_is_single_json_document_and_no_writes(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            missing = root / "missing.env"
            stage = root / "stage"
            state = root / "state"
            proc = subprocess.run(
                [sys.executable, str(ROOT / "scripts/bootstrap.py"),
                 "--secrets", str(missing), "--stage", str(stage), "--state", str(state)],
                cwd=ROOT,
                env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=20,
            )
        self.assertEqual(proc.returncode, 2, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["state"], "INPUT_REQUIRED")
        self.assertEqual(proc.stdout.count("\n{"), 0)
        self.assertFalse(stage.exists())
        self.assertFalse(state.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
