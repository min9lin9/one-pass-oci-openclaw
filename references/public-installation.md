# Public installation status — 2026-09-15

## Maturity

This is an **operational beta with an agent-driven installer**, not a universally
verified zero-touch appliance. A repository URL plus an explicit installation
request lets a local coding agent inspect prerequisites and execute the workflow.
Account registration, domain ownership, provider entitlement, human OAuth/device
approval and cloud capacity remain real external conditions.

| Area | Observed level |
|---|---|
| Existing WineyCellar runtime | Three native profiles, authenticated web/model replies and worker delivery previously verified |
| Repository-driven installation | Machine-readable preflight/apply entry point; missing-input, trust, review and failure paths covered offline |
| Fresh source acquisition | Eight selected sources and core bootstrap sources prepared without executing upstream installers |
| New OCI instance from scratch | SDK/flow covered offline; complete fresh-instance installation not newly exercised |
| Public/private mode | Public default and explicit Tailscale paths implemented and tested; live state below |
| Star | Actual local gh PUT/GET for this repository confirmed; missing auth is nonblocking |
| Backup/recovery | Prior encrypted export and staged restore verified; no new in-place recovery/reboot test |

The source acquisition check exposed two real blockers rather than assuming the
old source package would work unchanged: gstack's `connect-chrome` alias and
Baoyu's license declaration in README instead of a LICENSE file. The exact alias
is materialized into ordinary files under the extraction budget; arbitrary links
remain rejected. The catalog records the explicitly inspected license document.
Preparation is not source-review approval or installation.

## Current WineyCellar network state

The earlier `references/openclaw-only.md` records the Tailscale-only Buzz retirement.
The latest requested default supersedes that access policy.

- Initial Tailnet HTTPS returned200 through `100.99.73.120`.
- Initial public `161.33.223.67:443` timed out.
- The host now has public Caddy binding and a TCP443-only managed exception ahead
  of the OCI image's pre-UFW INPUT rejection. Native Gateways remain loopback-only.
- Existing authentication, model settings, Tailnet membership and retired Buzz data
  were not replaced. No runtime reinstall or host reboot was performed.
- OCI's existing shared security list allowed only SSH22. A separate
  `openclaw-public-https` NSG now permits stateful TCP443 from `0.0.0.0/0` and is
  attached only to WineyCellar. The shared security list was not changed.
- The public-IP HTTPS probe returned200 after that attachment. DNS now points to
  `161.33.223.67`, DNS-only; ordinary hostname access also returned200 from that IP.
- An anonymous Gateway connection was rejected with `NOT_PAIRED` /
  `DEVICE_IDENTITY_REQUIRED`. Static UI/health access does not grant agent access.
- A fresh authenticated browser request returned `PUBLIC_ACCESS_QA_C18D4`.
  The screenshot was captured and viewed. During the exchange, the server's
  established HTTPS peers used its public-interface address `10.0.1.82` and the
  client's public address, not either Tailnet address.
- Gateway, agents and auth configuration compare unchanged with the protected
  pre-transition copy. All three profile services and all seven existing Docker
  volumes remain; Buzz stays inactive.

The owner completed OCI console sign-in; no credentials were exported.
Gateway authentication was not disabled and no extra tunnel was introduced.
Protected network/config/controller rollback files are retained under
`/var/lib/oracle-ai-stack/public-access.YixiZSyk`.

## What installation automation does not claim

`READY_TO_APPLY` is an input/source/trust preflight result, not live application
readiness. `INSTALLED_PENDING_ACCEPTANCE` requires the agent to continue model,
browser and client verification. A missing/stale review produces a review state,
not an invented receipt. Source downloads and tests do not prove a fresh OCI
launch, provider authentication, full gstack execution or new browser pairing.
