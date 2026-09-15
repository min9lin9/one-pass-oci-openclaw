# Acceptance: install files != usable environment

Record exact version/commit, command, exit code, UTC time, relevant output/message
IDs and limitations. Redact credentials and personal content. Do not manufacture
screenshots, logs or test IDs. Assertions below require real execution on the target.

| Gate | Required actual evidence |
|---|---|
| Host | Ubuntu 24.04/aarch64, expected memory/disk, SSH host fingerprint verified |
| Identity | OpenClaw has no root/sudo/docker group; operator credentials remain outside agent access |
| Network | Selected mode and matching public/Tailnet IPv4; DNS-only A record; no conflicting AAAA/CNAME |
| Listeners | Public mode:443 externally reachable; Tailscale mode:443 Tailnet-only; 18789/19789/20789 loopback; no Buzz or public 80 redirect listener |
| TLS | Valid hostname/certificate chain through the selected route; public mode must actually use the public IP rather than a Tailnet route |
| Authentication | Static UI/health200 is not authenticated access; an unpaired/unauthorized client cannot run agent actions |
| OpenClaw | Three native profiles active, unique UIDs/state/ports; actual responses under each selected auth/model |
| Delegation | Operations submits unique task UUID to planning and development; actual model-backed result recorded |
| GBrain | Operations-only store; CLI remember/recall, then separate new-chat recall/correction/withdrawal verification |
| Retired Buzz | No active channel/binding/proxy route; dedicated containers stopped with restart disabled; existing data retained |
| Message path | Authenticated Control UI request → accepted OpenClaw turn → matching actual response |
| Native gstack | All four upstream native skills recognized; a realistic harmless task uses one |
| Full gstack | Authenticated Codex host discovers full skills; real read-only browser task; actual dispatch/delivery proved |
| insane-search | Real public page text, separate UID, API-less basic path, private URL rejection and timeout |
| Document reader | Local allowed file transforms; outside-workspace path rejected; scanned input not hallucinated |
| Mermaid | Actual SVG generated and inspected; source retained; no surprise runtime npm downloads |
| MCPorter | CLI/schema work in dedicated config; no imported client auth; missing external config not called READY |
| Learning | Proposal created, active skills/AGENTS/SOUL/privileges unchanged |
| Operations | Consistent encrypted backup, separate exported copy, staged restore --verify, actual recovery drill separately |
| Persistence | Authorized reboot test or explicitly mark reboot persistence NOT_TESTED |

## Example live smoke commands (operator resolves exact protected paths)
- Use `stack.py profiles --probe` for exclusive-state model probing; it defers if a worker task is active.
- Use the recorded binary with `--profile operations` for `config validate` and `skills check`.
- Use `stack.py acceptance` for actual model-backed worker markers and `stack.py memory-smoke` for CLI memory.
- Direct model probes/OAuth require exclusive ownership of the selected state; do not run them against a live Gateway.
- Public reader with `https://example.com` (no user secrets).
- Public reader with `http://169.254.169.254/` MUST reject before request.
- Inspect firewall both IPv4 and IPv6; a static ready marker alone does not prove
  rules survived an unrelated firewall rewrite.

Testing a request to YOUR cloud metadata endpoint is only a rejection test; do not
fetch metadata content or try to harvest instance credentials. Do not test against
unknown third-party systems or amplify rate-limited website requests.

## Resource budget
One browser/fetch job and one delegated worker task at a time. Resource limits in
profile_spec.py are configured ceilings, not benchmarked requirements. Do not guess real RAM usage from a README. Monitor
process RSS, disk and Docker container usage during actual tasks; reduce parallelism
before adding another heavy runtime. There is no local-GPU/model promise.

## Result states
INSTALLED: files/processes exist. READY: the specific acceptance test passed.
PENDING_AUTH/PENDING_HARNESS: precise external/setup gate.
FAILED: attempted and failed. NOT_TESTED: not run. SKIPPED: deliberately out of scope.
Do not collapse these into a green summary. Report the minimum missing gate and a
concrete recovery action without re-asking already answered architecture questions.

## OCI creation gates (new in v0.3)
Actual signed API read access, home-region check, intended compartment and free allowance,
new dedicated network or preserved existing subnet, managed tags/OCID reconciliation,
no duplicate instance on ambiguous response, expected ARM image, and control-plane host
fingerprint match. Capacity exhaustion is WAITING, not a reason to buy/resize/fallback.
Console-history capture/get/delete permissions are required for automatic host trust.

## Scope of automated probes
The worker marker test proves only delegation and a returned model answer. It does not
prove complete TDD behavior, prevention of all policy bypasses, artifact migration,
GBrain corrections/withdrawal, or Control UI delivery. Test those explicitly on a disposable
sample project and the real OpenClaw interface. A planner returns plans as text; it has no write
or shell tool. Only operations receives gbrain/gstack. A worker's output is untrusted data.
