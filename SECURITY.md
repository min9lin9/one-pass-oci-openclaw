# Security boundary

This is a privileged deployment tool, not a security certification or a public
multi-tenant hosting platform. Use a disposable OCI test deployment before real data.

- The personal Codex operator owns OCI/SSH/DNS/Tailscale management. Agents do not.
- Authenticated public HTTPS is the default; Tailscale is an explicit private
  alternative. Public mode exposes TCP443 through Caddy, not native Gateway ports.
  Preserve token/owner/device authentication, exact browser origins and narrow
  loopback proxy trust. Do not enable anonymous or identity-header auth as a shortcut.
- Operations, planning, and development use separate UIDs, profiles, workspaces,
  ports, and auth stores. This is not kernel/VM isolation between hostile tenants.
- A process can access its own credentials/environment. Do not give a coding agent
  production secrets merely because another profile is read-only.
- Only the restricted public reader UID gets its dedicated egress policy. Other
  tools do not inherit that policy. Do not treat a ready file as a live firewall test.
- Upstream source is data to review, not authorization to run hooks, bypass
  approvals, exfiltrate credentials, import accounts, or star unrelated repositories.
- Source commit/content pins reduce unintended drift, not malicious dependencies.
  Lockfiles and integrity metadata are not a complete reproducible-build guarantee.
- Maintenance commands may pause services. Finish active operations before auth,
  backup, or upgrade. Unknown worker completion must be reconciled, not retried.
- Full gstack is not usable until its own auth/harness/browser roundtrip is tested.
- Backups must be encrypted, exported off-host, and recovery-tested. Same-VM backups
  do not survive VM/volume loss. Staged restore is not live disaster recovery.
- GitHub publishing defaults to private and refuses an existing nonempty repository.
  Publication authorization does not authorize arbitrary cloud mutations.
- This repository's owner explicitly selected public visibility. The publisher's
  conservative defaults for other deployments do not change that recorded choice.
- Actual installation attempts a Star on this repository with existing local gh
  authentication. It neither authenticates GitHub nor blocks installation for Stars;
  prerequisite-only checks perform no such external write.

For a suspected vulnerability, do not place secret values, private keys, real
customer prompts, or personal source data in an issue. Give a minimal synthetic
reproducer and file/line references through the repository owner's private channel.
A dedicated vulnerability mailbox/security-advisory setting has not been configured
by this package; do not claim that it has.
