# OpenClaw-only transition — 2026-09-15

Historical Buzz-retirement record. The subsequent public-access default and
current live result are in `public-installation.md`; do not treat the old
Tailnet-only access instructions below as the current default.

The owner requested retiring Buzz, applying the change on WineyCellar and
reflecting it in the existing GitHub repository. This record supersedes the
older Buzz deployment instructions, not the historical test results.

## Current interface

- Open `https://openclaw.tune4unni.site` while connected to the
  `min9lin9.github` Tailscale network.
- Operations, planning and development retain separate users, gateways,
  workspaces and authentication stores.
- The migration did not write model/auth settings. The current operations
  override is `opencode-go/deepseek-v4-pro`; no provider login was repeated.
  Comparison with the initial rollback copy found the original auth profiles,
  gateway auth and default model unchanged, plus one additional auth profile
  and an operations model selection. Those newer settings were not reverted.

## Applied on WineyCellar

- Removed the Buzz channel and its bindings; disabled the Buzz plugin entry.
- Removed the Buzz Caddy route and the exact managed `buzz.tune4unni.site`
  DNS record. The OpenClaw DNS-only A record remains `100.99.73.120`.
- Stopped the five dedicated Buzz containers and set their restart policies
  to `no`. Port 3000 is no longer listening.
- Retained PostgreSQL, Redis, MinIO and Git volumes, identity files and history.
  No volume deletion or whole-host reboot was performed.
- Installed the reviewed first-party operator code and updated the managed
  operations role only after its recorded hash matched the current file.
  Third-party runtimes, user workspaces and model/auth stores were not reinstalled.
- Preserved WineDocellar's existing stopped containers and data volume.

Protected rollback copies of code, role, configuration and Caddy files are in
`/var/lib/oracle-ai-stack/openclaw-only-ej1i4z1q`. Retired Buzz volumes are not
part of the new active-volume backup inventory; keep them and the previously
verified encrypted snapshot until a separate retention decision.

For another existing installation, perform the same explicit retirement with
configuration backups and managed DNS ownership checks. Normal setup/repair
no longer installs or starts Buzz; it is not a data-purge command.

## Observed verification

- `python3 scripts/check.py`: 167 offline tests passed, including no-Buzz
  setup/proxy/DNS/backup regressions and conservative status reporting.
- The deployed `remote.py status` reports all three gateways, private networking,
  proxy and reader egress running. `SERVICES_RUNNING` is deliberately not a
  claim that every model, extension or client was verified.
- In the authenticated Control UI, a fresh request returned the exact assistant
  response `OPENCLAW_ONLY_15A7C9`; the screenshot was captured and viewed.
  The existing DeepSeek selection was retained.
- Cloudflare API verification found zero Buzz records and the unchanged
  DNS-only OpenClaw record. All seven existing Docker volumes remained present.
- After the code deployment, both native worker sockets returned their exact
  requested markers with `COMPLETED`; `acceptance.json` records
  `DELEGATION_MARKERS_PASSED`. This checks message delivery, not a fresh
  full development task or adversarial filesystem-isolation test.

This transition did not repeat the earlier full gstack/GBrain acceptance suite
or the 7.5 GB staged recovery. Those remain historical, separately captured
results. Mobile-browser login was not newly tested. MCP has no configured
external servers. A future source install/update requires fresh preparation
and genuine source review; old deployment review receipts were not resealed
to fit this code.

The integration checkout was based on existing remote commit `b848de9`;
the older uncommitted deployment checkout was preserved separately.
