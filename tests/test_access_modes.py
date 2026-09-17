"""Offline access-mode and network reconfiguration regression contracts."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import oci_provision as oci
import profile_spec
import remote
import stack
import stacklib
from stacklib import StackError


class AccessModeValidationTests(unittest.TestCase):
    def env(self, text):
        temp = tempfile.TemporaryDirectory()
        path = pathlib.Path(temp.name) / "secrets.env"
        path.write_text(text)
        path.chmod(0o600)
        return temp, stacklib.load_env(path)

    def test_access_mode_defaults_public_and_tracks_implicit_default(self):
        temp, cfg = self.env("DOMAIN=example.com\n")
        self.addCleanup(temp.cleanup)
        self.assertEqual(cfg["ACCESS_MODE"], "public")
        self.assertFalse(cfg["_ACCESS_MODE_EXPLICIT"])

    def test_blank_mode_is_an_implicit_public_default(self):
        temp, cfg = self.env("DOMAIN=example.com\nACCESS_MODE=\n")
        self.addCleanup(temp.cleanup)
        self.assertEqual(cfg["ACCESS_MODE"], "public")
        self.assertFalse(cfg["_ACCESS_MODE_EXPLICIT"])

    def test_loaded_environment_preserves_string_value_contract(self):
        temp, cfg = self.env("DOMAIN=example.com\n")
        self.addCleanup(temp.cleanup)
        self.assertTrue(all(isinstance(value, str) for value in cfg.values()))

    def test_explicit_tailscale_mode_is_supported(self):
        temp, cfg = self.env("DOMAIN=example.com\nACCESS_MODE=tailscale\n")
        self.addCleanup(temp.cleanup)
        self.assertEqual(stacklib.access_mode(cfg), "tailscale")
        self.assertTrue(cfg["_ACCESS_MODE_EXPLICIT"])

    def test_unknown_access_mode_is_rejected(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = pathlib.Path(temp.name) / "secrets.env"
        path.write_text("ACCESS_MODE=internet\n")
        path.chmod(0o600)
        with self.assertRaises(StackError):
            stacklib.load_env(path)

    def test_public_ip_must_be_numeric_global_ipv4(self):
        self.assertEqual(stacklib.public_ipv4("8.8.4.4"), "8.8.4.4")
        for value in ("example.com", "10.0.0.1", "100.64.0.1", "::1"):
            with self.subTest(value=value), self.assertRaises(StackError):
                stacklib.public_ipv4(value)

    def test_public_ip_derives_only_from_configured_numeric_oracle_host(self):
        self.assertEqual(stack.public_ip_for({"ORACLE_HOST": "8.8.4.4"}), "8.8.4.4")
        with self.assertRaises(StackError):
            stack.public_ip_for({"ORACLE_HOST": "vm.example.com"})


class DnsModeTests(unittest.TestCase):
    def cfg(self, mode):
        return {"DOMAIN": "example.com", "CLOUDFLARE_API_TOKEN": "fixture", "ACCESS_MODE": mode}

    def test_public_dns_uses_public_ipv4(self):
        with patch.object(stack, "cf_request", return_value={"result": []}):
            action = stack.dns_plan(self.cfg("public"), "zone", "8.8.4.4")[0]
        self.assertEqual(action[2]["content"], "8.8.4.4")
        self.assertFalse(action[2]["proxied"])

    def test_public_dns_rejects_tailnet_ip(self):
        with self.assertRaises(StackError):
            stack.dns_plan(self.cfg("public"), "zone", "100.64.1.1")

    def test_tailscale_dns_rejects_public_ip(self):
        with self.assertRaises(StackError):
            stack.dns_plan(self.cfg("tailscale"), "zone", "8.8.4.4")

    def test_only_managed_record_is_updated(self):
        existing = {"type": "A", "content": "100.64.1.1", "id": "record", "comment": "managed-by:oracle-ai-stack-v0.2"}
        with patch.object(stack, "cf_request", return_value={"result": [existing]}):
            actions = stack.dns_plan(self.cfg("public"), "zone", "8.8.4.4")
        self.assertEqual(actions[0][0], "PUT")
        self.assertEqual(actions[0][2]["content"], "8.8.4.4")


class RemoteNetworkTests(unittest.TestCase):
    def paths(self, root):
        base = root / "base"
        state = root / "state"
        etc = root / "etc"
        stage = root / "stage"
        for path in (base, state, etc, stage / "core"):
            path.mkdir(parents=True, exist_ok=True)
        return base, state, etc, stage

    def test_public_configuration_never_touches_tailscale(self):
        with tempfile.TemporaryDirectory() as td:
            base, state, etc, stage = self.paths(pathlib.Path(td))
            calls = []

            def run(args, **kwargs):
                calls.append(list(map(str, args)))
                return subprocess.CompletedProcess(args, 0, b"", b"")

            cfg = {"DOMAIN": "example.com", "CLOUDFLARE_API_TOKEN": "cert-token",
                   "ACCESS_MODE": "public", "_ACCESS_MODE_EXPLICIT": True,
                   "PUBLIC_IP": "8.8.4.4", "_SSH_CONNECTION": "8.8.8.8 1.1.1.1 54321 22"}
            with patch.object(remote, "BASE", base), patch.object(remote, "STATE", state), \
                 patch.object(remote, "ETC", etc), patch.object(remote, "run", side_effect=run), \
                 patch.object(remote, "write") as write, patch.object(remote, "atom_json") as atom:
                result = remote.configure_network(cfg, stage)

            flat = "\n".join(" ".join(row) for row in calls)
            self.assertNotIn("tailscale", flat.lower())
            self.assertEqual(result["access_mode"], "public")
            self.assertEqual(result["dns_ip"], "8.8.4.4")
            self.assertIn(["ufw", "allow", "443/tcp"], calls)
            self.assertIn(["systemctl", "restart", "oracle-public-https.service"], calls)
            unit = next(call.args[1] for call in write.call_args_list
                        if pathlib.Path(call.args[0]).name == "oracle-public-https.service")
            self.assertIn("ExecStart=/usr/sbin/iptables -I INPUT 1 -p tcp --dport 443", unit)
            self.assertIn("ExecStop=/usr/sbin/iptables -D INPUT -p tcp --dport 443", unit)
            env = next(call.args[1] for call in write.call_args_list if pathlib.Path(call.args[0]).name == "proxy.env")
            self.assertIn("PROXY_BIND=0.0.0.0", env)
            network = next(call.args[1] for call in atom.call_args_list if pathlib.Path(call.args[0]).name == "network.json")
            self.assertEqual(network["access_mode"], "public")

    def test_invalid_public_address_stops_before_firewall_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            _, state, etc, stage = self.paths(pathlib.Path(td))
            cfg = {"DOMAIN": "example.com", "CLOUDFLARE_API_TOKEN": "cert-token",
                   "ACCESS_MODE": "public", "_ACCESS_MODE_EXPLICIT": True,
                   "PUBLIC_IP": "10.0.0.1", "_SSH_CONNECTION": "8.8.8.8 1.1.1.1 54321 22"}
            with patch.object(remote, "STATE", state), patch.object(remote, "ETC", etc), patch.object(remote, "run") as run:
                with self.assertRaises(StackError):
                    remote.configure_network(cfg, stage)
            run.assert_not_called()

    def test_interrupted_bootstrap_reuses_its_recorded_access_mode(self):
        with tempfile.TemporaryDirectory() as td:
            _, state, etc, stage = self.paths(pathlib.Path(td))
            (state / "managed.json").write_text(json.dumps({
                "schema": 3, "domain": "example.com", "state": "BOOTSTRAPPING",
                "access_mode": "public",
            }))
            cfg = {"DOMAIN": "example.com", "CLOUDFLARE_API_TOKEN": "fixture",
                   "PUBLIC_IP": "8.8.4.4", "_ACCESS_MODE_EXPLICIT": False,
                   "_SSH_CONNECTION": "8.8.8.8 50000 10.0.1.2 22"}
            with patch.object(remote, "STATE", state), patch.object(remote, "ETC", etc), \
                 patch.object(remote, "write"), patch.object(
                     remote, "run", return_value=subprocess.CompletedProcess([], 0, b"", b"")):
                result = remote.configure_network(cfg, stage)
            managed = json.loads((state / "managed.json").read_text())
        self.assertEqual(result["access_mode"], "public")
        self.assertEqual(managed["state"], "HOST_CONFIGURED")

    def test_completed_host_with_missing_network_requires_explicit_mode(self):
        with tempfile.TemporaryDirectory() as td:
            _, state, etc, stage = self.paths(pathlib.Path(td))
            (state / "managed.json").write_text(json.dumps({
                "schema": 3, "domain": "example.com", "state": "HOST_CONFIGURED",
                "access_mode": "public",
            }))
            cfg = {"DOMAIN": "example.com", "CLOUDFLARE_API_TOKEN": "fixture",
                   "PUBLIC_IP": "8.8.4.4", "_ACCESS_MODE_EXPLICIT": False,
                   "_SSH_CONNECTION": "8.8.8.8 50000 10.0.1.2 22"}
            with patch.object(remote, "STATE", state), patch.object(remote, "ETC", etc), \
                 patch.object(remote, "run") as command:
                with self.assertRaises(StackError):
                    remote.configure_network(cfg, stage)
            command.assert_not_called()

    def test_active_tailnet_is_reused_without_up_or_logout(self):
        with tempfile.TemporaryDirectory() as td:
            _, state, etc, stage = self.paths(pathlib.Path(td))
            (state / "network.json").write_text(json.dumps({"tailscale_ip": "100.64.1.1"}))
            calls = []

            def run(args, **kwargs):
                calls.append(list(map(str, args)))
                if args[:3] == ["tailscale", "status", "--json"]:
                    return subprocess.CompletedProcess(args, 0, b'{"BackendState":"Running"}', b"")
                if args[:3] == ["tailscale", "ip", "-4"]:
                    return subprocess.CompletedProcess(args, 0, b"100.64.1.1\n", b"")
                return subprocess.CompletedProcess(args, 0, b"", b"")

            cfg = {"DOMAIN": "example.com", "CLOUDFLARE_API_TOKEN": "cert-token",
                   "ACCESS_MODE": "tailscale", "_ACCESS_MODE_EXPLICIT": True,
                   "_SSH_CONNECTION": "8.8.8.8 1.1.1.1 54321 22"}
            with patch.object(remote, "STATE", state), patch.object(remote, "ETC", etc), \
                 patch.object(remote.shutil, "which", return_value="/usr/bin/tailscale"), \
                 patch.object(remote, "run", side_effect=run), patch.object(remote, "write"), patch.object(remote, "atom_json"):
                remote.configure_network(cfg, stage)
            flat = "\n".join(" ".join(call) for call in calls)
            self.assertNotIn("tailscale up", flat)
            self.assertNotIn("tailscale down", flat)
            self.assertNotIn("tailscale-install.sh", flat)

    def test_legacy_tailnet_state_is_preserved_without_explicit_migration(self):
        previous = {"domain": "example.com", "tailscale_ip": "100.64.1.1"}
        self.assertEqual(remote.select_access_mode({"ACCESS_MODE": "public", "_ACCESS_MODE_EXPLICIT": False}, previous), "tailscale")
        self.assertEqual(remote.select_access_mode({"ACCESS_MODE": "public", "_ACCESS_MODE_EXPLICIT": True}, previous), "public")

    def test_switch_to_tailnet_stops_owned_public_firewall_exception(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            _, state, etc, stage = self.paths(root)
            unit = root / "oracle-public-https.service"
            unit.write_text("[Service]\n")
            (state / "network.json").write_text(json.dumps({"access_mode": "public"}))
            def run(args, **kwargs):
                output = b""
                if args[:3] == ["tailscale", "status", "--json"]:
                    output = b'{"BackendState":"Running"}'
                if args[:3] == ["tailscale", "ip", "-4"]:
                    output = b"100.64.1.1\n"
                return subprocess.CompletedProcess(args, 0, output, b"")
            cfg = {"DOMAIN": "example.com", "CLOUDFLARE_API_TOKEN": "fixture",
                   "ACCESS_MODE": "tailscale", "_SSH_CONNECTION": "8.8.8.8 1.1.1.1 50000 22"}
            with patch.object(remote, "STATE", state), patch.object(remote, "ETC", etc), \
                 patch.object(remote, "PUBLIC_FIREWALL", unit), patch.object(remote, "write"), \
                 patch.object(remote.shutil, "which", return_value="/usr/bin/tailscale"), \
                 patch.object(remote, "run", side_effect=run) as command:
                remote.configure_network(cfg, stage)
            self.assertIn(
                unittest.mock.call(["systemctl", "disable", "--now", unit.name]),
                command.call_args_list,
            )

    def test_public_proxy_binds_wildcard_and_exposes_no_http_site(self):
        with tempfile.TemporaryDirectory() as td:
            base, state, etc, _ = self.paths(pathlib.Path(td))
            (state / "network.json").write_text(json.dumps({"access_mode": "public", "public_ip": "8.8.4.4"}))
            lock = {"caddy_dns_commit": "a" * 40}
            (state / "caddy-build-lock.json").write_text(json.dumps({
                "cloudflare_commit": lock["caddy_dns_commit"],
                "parents": {"caddy:2-builder": "builder@sha256:x", "caddy:2-alpine": "caddy@sha256:y"},
                "caddy_version": "v2.10.0",
            }))
            with patch.object(remote, "BASE", base), patch.object(remote, "STATE", state), \
                 patch.object(remote, "ETC", etc), patch.object(remote, "write") as write, \
                 patch.object(remote, "atom_json"), patch.object(remote, "run", return_value=subprocess.CompletedProcess([], 0, b"", b"")):
                result = remote.proxy_install({}, lock)
            caddy = next(call.args[1] for call in write.call_args_list if pathlib.Path(call.args[0]).name == "Caddyfile")
            self.assertIn("bind {$PROXY_BIND}", caddy)
            self.assertIn("https://openclaw.{$DOMAIN}", caddy)
            self.assertNotIn("http://", caddy)
            self.assertEqual(result["phase"], "PUBLIC_PROXY_INSTALLED")

    def test_public_status_does_not_require_or_check_tailscale(self):
        with tempfile.TemporaryDirectory() as td:
            base, state, _, _ = self.paths(pathlib.Path(td))
            home = pathlib.Path(td) / "home"
            (home / ".local/state/oracle-ai-stack").mkdir(parents=True)
            (home / ".local/state/oracle-ai-stack/runtime-checks.json").write_text("{}")
            (state / "network.json").write_text(json.dumps({"access_mode": "public", "public_ip": "8.8.4.4"}))
            (state / "gbrain-install.json").write_text("{}")
            (base / "compose.proxy.json").write_text("{}")
            profiles = {name: {"gateway": "PASS", "auth": "NOT_PROBED"} for name in ("operations", "planning", "development", "finance")}
            calls = []

            def run(args, **kwargs):
                calls.append(args)
                stdout = b"proxy\n" if args[:2] == ["docker", "compose"] else b""
                return subprocess.CompletedProcess(args, 0, stdout, b"")

            with patch.object(remote, "BASE", base), patch.object(remote, "STATE", state), patch.object(remote, "HOME", home), \
                 patch.object(remote, "run", side_effect=run), patch("profiles_runtime.profile_status", return_value=profiles):
                result = remote.status()
            self.assertEqual(result["access_mode"], "public")
            self.assertEqual(result["overall"], "SERVICES_RUNNING")
            self.assertEqual(result["client_verification"], "NOT_TESTED")
            self.assertNotEqual(result["overall"], "READY")
            self.assertNotIn("tailscale", result["checks"])
            self.assertFalse(any("tailscaled" in " ".join(call) for call in calls))

    def test_missing_network_state_is_unknown_not_implicit_public(self):
        with tempfile.TemporaryDirectory() as td:
            base, state, _, _ = self.paths(pathlib.Path(td))
            home = pathlib.Path(td) / "home"
            (home / ".local/state/oracle-ai-stack").mkdir(parents=True)
            with patch.object(remote, "BASE", base), patch.object(remote, "STATE", state), patch.object(remote, "HOME", home), \
                 patch.object(remote, "run", return_value=subprocess.CompletedProcess([], 1, b"", b"")), \
                 patch("profiles_runtime.profile_status", return_value={}):
                result = remote.status()
            self.assertEqual(result["access_mode"], "UNKNOWN")
            self.assertEqual(result["overall"], "INCOMPLETE")


class OciIngressTests(unittest.TestCase):
    def cfg(self, **updates):
        cfg = {"OCI_USER": "ocid1.user.oc1..user", "OCI_TENANCY": "ocid1.tenancy.oc1..tenant",
               "OCI_FINGERPRINT": ":".join(["ab"] * 16), "OCI_REGION": "example-region-1",
               "OCI_KEY_FILE": "/local/key.pem", "DOMAIN": "example.com", "OCI_SSH_ALLOWED_CIDR": "8.8.8.8/32"}
        cfg.update(updates)
        return cfg

    def test_default_public_dedicated_network_has_https_without_broadening_ssh(self):
        rules = oci.desired_ingress_rules(oci.normalized(self.cfg()), NS(core=NS(models=Models())))
        ports = [(r.source, r.tcp_options.destination_port_range.min, r.tcp_options.destination_port_range.max) for r in rules]
        self.assertEqual(ports, [("8.8.8.8/32", 22, 22), ("0.0.0.0/0", 443, 443)])

    def test_explicit_tailscale_dedicated_network_has_ssh_only(self):
        rules = oci.desired_ingress_rules(oci.normalized(self.cfg(ACCESS_MODE="tailscale")), NS(core=NS(models=Models())))
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0].tcp_options.destination_port_range.min, 22)

    def test_unmanaged_subnet_plan_reports_ingress_review_without_rewrite(self):
        cfg = oci.normalized(self.cfg(OCI_CREATE_NETWORK="false", OCI_SUBNET="ocid1.subnet.oc1..fixture"))
        self.assertEqual(oci.ingress_disposition(cfg), "UNMANAGED_SUBNET_REVIEW_REQUIRED")

    def test_access_mode_does_not_change_immutable_instance_request(self):
        public = {"image": "image", "shape": oci.SHAPE, "access_mode": "public", "https_ingress": "managed"}
        tailscale = {"image": "image", "shape": oci.SHAPE, "access_mode": "tailscale", "https_ingress": "managed"}
        self.assertEqual(oci.infrastructure_proposal(public), oci.infrastructure_proposal(tailscale))


class Models:
    def __getattr__(self, name):
        return lambda **kwargs: NS(**kwargs)


class GatewaySecurityTests(unittest.TestCase):
    def test_public_origin_keeps_loopback_token_device_and_proxy_protections(self):
        config = profile_spec.config_for(profile_spec.PROFILES["operations"], {"DOMAIN": "example.com"}, "secret-token")
        gateway = config["gateway"]
        self.assertEqual(gateway["bind"], "loopback")
        self.assertEqual(gateway["auth"], {"mode": "token", "token": "secret-token"})
        self.assertEqual(gateway["publicOrigin"], "https://openclaw.example.com")
        self.assertEqual(gateway["controlUi"]["allowedOrigins"], ["https://openclaw.example.com"])
        self.assertEqual(gateway["trustedProxies"], ["127.0.0.1", "::1"])
        self.assertNotIn("dangerouslyDisableDeviceAuth", json.dumps(config))


class WorkflowTests(unittest.TestCase):
    def test_setup_stars_only_this_repository(self):
        ok = subprocess.CompletedProcess([], 0, b"", b"")
        with patch.object(stack.shutil, "which", return_value="/usr/bin/gh"), patch.object(stack, "run", return_value=ok) as run:
            self.assertTrue(stack.star_repository())
        self.assertEqual(run.call_args_list[1].args[0], ["gh", "api", "--method", "PUT", "/user/starred/min9lin9/one-pass-oci-openclaw"])
        self.assertEqual(run.call_args_list[2].args[0], ["gh", "api", "/user/starred/min9lin9/one-pass-oci-openclaw"])
        self.assertFalse(any("prompt-engineering-skills" in str(call) for call in run.call_args_list))

    def test_star_is_non_blocking_without_gh_or_auth(self):
        with patch.object(stack.shutil, "which", return_value=None), patch.object(stack, "run") as run:
            self.assertFalse(stack.star_repository())
            run.assert_not_called()
        failed = subprocess.CompletedProcess([], 1, b"", b"")
        with patch.object(stack.shutil, "which", return_value="/usr/bin/gh"), patch.object(stack, "run", return_value=failed):
            self.assertFalse(stack.star_repository())
        ok = subprocess.CompletedProcess([], 0, b"", b"")
        with patch.object(stack.shutil, "which", return_value="/usr/bin/gh"), \
             patch.object(stack, "run", side_effect=[ok, failed]) as run:
            self.assertFalse(stack.star_repository())
            self.assertEqual(run.call_count, 2)

    def test_only_setup_and_explicit_action_star(self):
        source = (ROOT / "scripts/stack.py").read_text()
        prepare_body = source[source.index("def prepare("):source.index("def verify_core(")]
        self.assertNotIn("star_repository()", prepare_body)
        setup_body = source[source.index("def setup("):source.index("def hydrate_handoff(")]
        self.assertIn("star_repository()", setup_body)

    def test_network_action_is_narrow(self):
        cfg = {"DOMAIN": "example.com", "CLOUDFLARE_API_TOKEN": "fixture", "ORACLE_HOST": "8.8.4.4",
               "ACCESS_MODE": "public", "_ACCESS_MODE_EXPLICIT": True}
        with tempfile.TemporaryDirectory() as td, patch.object(stack, "verify_all"), \
             patch.object(stack, "cloudflare_zone", return_value="zone"), patch.object(stack, "upload"), \
             patch.object(stack, "dns_plan", return_value=[]), patch.object(stack, "cf_request"), \
             patch.object(stack, "atom_json"), patch.object(stack, "remote", side_effect=[
                 {"phase": "NETWORK_CONFIGURED", "access_mode": "public", "dns_ip": "8.8.4.4"},
                 {"phase": "PUBLIC_PROXY_INSTALLED"},
                 {"overall": "SERVICES_RUNNING", "client_verification": "NOT_TESTED"},
             ]) as worker:
            stack.reconfigure_network(cfg, pathlib.Path(td) / "stage", pathlib.Path(td) / "state")
        self.assertEqual([call.args[1] for call in worker.call_args_list], ["network", "proxy", "status"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
