# Unreleased: clean Gateway restart and PostgreSQL memory — 2026-09-16

Use Restart=always for Gateway units so a normal plugin-triggered supervisor
restart does not leave the service stopped. Preserve explicit maintenance stops.
Add the pinned private PostgreSQL+pgvector template and include its data volume,
secrets and Gateway drop-ins in backups; retain volumes during managed shutdown.
Preserve existing PostgreSQL memory configuration at the actual
GBRAIN_HOME/.gbrain/config.json path. Bound memory output during capture, allow
30 seconds of graceful termination, and disable automatic PGlite WAL repair.
The approved live migration used full SQL export and relation fingerprints,
not the incomplete upstream migration command. See references/gbrain-postgres.md.
These changes have not been committed or published as a new GitHub release.

# Nondeveloper onboarding and continuation — 2026-09-15

Make the agent prepare missing local configuration and guide one human action
at a time, using linked official domain, Cloudflare token and OCI signing-key
instructions. Map the OCI console preview instead of asking a novice to translate
variables. Add a private continuation-note procedure, explicit post-login commands,
native browser-device approval and distinct backup/export/restore evidence.
Do not rerun setup to resume acceptance. Document that model probes can configure
models and require preserving existing choices. These are agent instructions,
not a new unattended installer, browser driver or live deployment verification.

# Public access and agent-driven bootstrap — 2026-09-15

Default to authenticated public HTTPS; make Tailscale explicit and optional.
Add an agent-facing prerequisite/apply coordinator and a network-only action.
Persist the initial bootstrap mode for interrupted-install recovery; missing
network metadata on a completed host still fails closed.
Preserve loopback gateways, owner/device auth, existing profiles and data.
Add a scoped persistent HTTPS exception for OCI's pre-UFW reject rule.
Record automatic, nonblocking Star verification for this repository.
Handle the reviewed gstack alias as regular files and record Baoyu's actual
README license evidence so fresh source preparation can complete.
See `references/public-installation.md` for maturity and current live limits.

# OpenClaw-only deployment — 2026-09-15

Make OpenClaw Control UI the active interface. Remove Buzz from normal
preparation, setup/repair, profile installation, DNS/proxy, status, acceptance
and active-volume lifecycle paths. Preserve retired data and the three native
profiles. Distinguish running services from verified client behavior.
See `references/openclaw-only.md` for the applied OCI change and its evidence.

# Publication target correction — 2026-09-14

Correct the assistant-introduced `opnclaw` typo to the user-requested
`min9lin9/one-pass-oci-openclaw` throughout the publishing target and skill metadata.
Legacy backup tags remain readable. This does not migrate or provision infrastructure.

# 0.4.0-beta — 2026-09-14

Review release, renamed skill to `one-pass-oci-openclaw`; internal data layout
remains schema 3. See REVIEW.md for actual findings and regression evidence.
Secure FD-based atomic writes; unprivileged agent-home copies; supported model
catalog commands; actual inference and strict response checks; bounded subprocess
output; honest acceptance status; failed backup resumption fails the command;
network readiness polling; pre-upload host ownership checks; shared maintenance
lock; destination-specific DNS exceptions; source execute-bit hashing; review-note
exclusion; explicit package manifest, installer, private GitHub publisher and CI.
No live infrastructure/auth/Buzz/restore test or remote publication performed.

---

# v0.3-beta — 2026-09-14

- Added local OCI SDK provisioning adapted from min9lin9/oci-instance-creator:
  scoped variables, fixed A1 2/12, home-region/ARM-image discovery, dedicated optional
  network, bounded retry, stable request tokens, tagged-resource reconciliation,
  authenticated hostkey receipt and SSH handoff. No cron or paid fallback.
- Three native named profiles and Linux identities, distinct state/workspaces/ports,
  operations-only GBrain/gstack and curated skills. ECC planner/architect and
  TDD/reviewer references supply role methods, not Claude models or hooks.
- Operations-to-worker Unix socket dispatcher with peer checks, request bounds,
  single worker concurrency, idempotent task receipts and auth readiness gates.
- Per-profile ChatGPT OAuth or OpenCode Go/Zen key, catalog-backed model selection,
  direct live probes with exclusive state ownership; old PASS invalidated on changes.
- GBrain pinned-source/Bun installation and keyless PGLite remember/recall wrapper.
  No paid embeddings, identity rewrite, ingestion or dream loop enabled.
- Expanded coherent backup and stop/restore-to-staging runbooks to three homes,
  GBrain DB, workers/sockets and all Buzz stores. No implicit live v0.2 migration.
- Automated live acceptance entrypoints added; not run against OCI/models here.

## Earlier package history

# Changelog

## 0.2-beta — 2026-09-14

This is a new reviewed workflow and code revision, not a production-certified release.

- Preserve Oracle Ubuntu ARM + native OpenClaw + Docker Buzz + Tailscale-only domains.
- Add eight curated source groups, including mandatory gstack and insane-search;
  add operator-side restic and Gitleaks.
- Add code-aware staging, commit/hash locks, review receipts, bounded archive extraction,
  catalog path validation, installed-skill provenance and user-edit preservation.
- Separate gstack's four native skills from full Codex-host setup and dispatch acceptance.
- Introduce host adapters for public reading, local document reading, Mermaid rendering,
  MCP CLI use and learning proposals. No upstream Star-on-first-use or hook import.
- Send operator credentials through SSH stdin, never a literal command-line env argument.
  Require strict known_hosts and preserve the currently working SSH route.
- Use dedicated OpenClaw and public-reader users; keep Cloudflare, owner and backup keys
  outside the agent's access. No Docker-group or broad sudo grant.
- Pin resolved Buzz image digests. Reuse Caddy core/module/parent pins on repair and build
  Caddy in a context that excludes generated Compose files and credentials.
- Add actual Buzz relay/plugin/identity installation and room-binding operations. Owner
  room creation/Bot-role steps remain an official CLI-driven Codex procedure.
- Back up coherent stopped application state, including PostgreSQL, Redis, MinIO, Git,
  OpenClaw home and private configuration; use encrypted restic snapshots.
- Restore to a separate verified staging tree, not silently onto a live database.
- Keep update application and live restore as reviewed operator procedures.
- Add explicit acceptance states and tests; no synthetic end-to-end success flag.

No Oracle instance was contacted, provider OAuth completed, GitHub star changed or
production restore performed while authoring this release.
