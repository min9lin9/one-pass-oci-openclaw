# Nondeveloper onboarding rehearsal — 2026-09-15

Scope: documentation and agent execution instructions only; no runtime Python,
provisioning, auth or live WineyCellar configuration was changed.
Independent agents were instructed to use only isolated repository snapshots,
not prior conversation, personal configuration or credentials.
The host already had Python 3.12.12, Git and OpenSSH; this was not an empty-OS test.

| Scenario | Observed result | Evidence boundary |
|---|---|---|
| Before: absent settings file | Actual exit2, `INPUT_REQUIRED`, route `unknown`, only `secrets_file` requested | Real local preflight |
| Revised: agent prepares template | Exact template copy, directory0700/file0600; actual exit2, package `VALID`, route `new_oci_host`, eight missing settings identified | Real isolated local preparation/preflight; no credentials invented |
| Only OCI signup, no domain | Agent gives a concrete provider screen, one human action and return phrase; maps OCI preview fields itself | Dialogue rehearsal, not account/console execution |
| Login completed | Agent recovers paths/login type, reconciles model policy and uses pending checks instead of setup; identifies token/device and backup handoffs | Dialogue rehearsal, not actual OAuth/browser/restore |
| Unknown domain ownership | Initial revised reply prematurely advised purchase; parent review caught it, guidance was corrected, a new independent reply asked ownership first | Dialogue rehearsal; both existing/no-domain branches then passed |

The unknown-ownership correction is not hidden behind the earlier agent's overall
PASS verdict. Missing configuration does not establish absence of a user's resource.
The final tested first question asks whether a domain is already owned; purchase
is proposed only after an explicit no.

`python3 scripts/check.py` passed **215 tests** after the onboarding edits.
Internal Markdown link targets exist and both new Bash examples pass `bash -n`;
neither device command was executed against a server. Markdown LSP is unavailable,
so no Markdown diagnostic pass is claimed. Package hashes were regenerated for
reviewed documentation, and the before/after snapshots remained manifest-valid.
The QA environment lacked an `apply_patch` executable; the QA agent copied only
the permitted blank template and reported that tooling limitation.

No new full OCI launch, provider-console operation, source installation, OAuth,
model response, browser pairing, backup export or restore was run in this rehearsal.
No human novice usability study or guarantee for every agent/tool environment is
claimed. Browser and secret-transfer capability remain actual completion
requirements; missing capability must be reported rather than bypassed.
These findings validate a more actionable staged workflow, not an unattended
one-command deployment product. See `references/first-install.md` and
`references/resume-install.md`.

# Public mode and bootstrap — 2026-09-15

`python3 scripts/check.py` passed **215 tests** on macOS ARM64. Changed Python
diagnostics were clean; the agent YAML parsed successfully with Psych.
The YAML language server is not installed, so no YAML LSP result is claimed.

Failing-first checks covered default Tailscale downloads, structured Star status,
existing Tailnet reuse, reviewed alias extraction, explicit license evidence and
the OCI pre-UFW rejection. The initial direct bootstrap test command used macOS's
symlinked temporary directory; the packaged checker and focused replays use
`TMPDIR=/private/tmp` rather than weakening filesystem checks.
Final review also covered interrupted initial installation: the chosen bootstrap
mode is recorded before host mutation and reused only while bootstrapping.
A completed host with lost network metadata still requires an explicit mode.
The environment parser retains its string-value type contract.

Fresh source preparation completed for all eight catalog sources and core
bootstraps; no upstream installer ran in that test and no review was fabricated.
Gitleaks scanned all four existing Git commits without leaks. GitHub visibility
is public and an unauthenticated API request confirmed `private:false`.
The actual repository Star was verified through the authenticated GitHub API.

Live public HTTPS now returns200 both through the forced public-IP path and normal
DNS after a WineyCellar-only TCP443 NSG was attached. Anonymous Gateway connect was
rejected with `NOT_PAIRED` / `DEVICE_IDENTITY_REQUIRED`. These transport/auth checks
are separate from the source suite; see `references/public-installation.md`.
A fresh authenticated web turn returned `PUBLIC_ACCESS_QA_C18D4`, with public
HTTPS peers observed during the exchange and the resulting screenshot viewed.

# Historical OpenClaw-only transition — 2026-09-15

On macOS ARM64, `python3 scripts/check.py` passed **167 tests**. Python, shell
and JSON checks passed; changed Python files had no LSP errors.
The readiness regression first failed with `READY != SERVICES_RUNNING`, then
passed after status stopped claiming complete client verification.

WineyCellar verification is recorded in `references/openclaw-only.md`, including
an actual authenticated Control UI response after Buzz retirement. These live
checks are separate from the offline suite and the historical report below.

# Historical test report — 0.4.0-beta

Date: 2026-09-14. Environment: this session's Linux container, not Oracle A1.

## Observed executions

| Check | Result | Scope |
|---|---|---|
| Original v0.3 baseline | 104 tests passed | Existing offline tests |
| Reviewed code | **159 tests passed** | Existing 104 + 55 new regression tests |
| Python syntax | 30 scripts parsed, test modules parsed | AST validation, not live dependencies |
| Bash syntax | 1 script passed bash -n | No actual iptables mutation |
| JSON | Package JSON parsed | Syntax only |

Executed command:

```bash
python3 scripts/check.py
```

The tests exercise real temporary-file/symlink/hardlink/FIFO protection and real
local child-process output/time budgets. OCI, maintenance restart, identity,
publication and model behavior use synthetic responses/mocks. Tests include
failed acceptance receipts, echoed markers, in-flight/error responses, source
permission changes, missing backup passwords, snapshot-success/resume-failure,
pre-upload rejection, and immutable distribution files. They are not all unit
tests of external services and are not an independent security audit.

## Not executed

Actual signed OCI API requests, ARM installation, live models/OAuth, Buzz room
roundtrip, full gstack harness, GBrain new-conversation retrieval, service cgroups,
ipv4/ipv6 egress enforcement, actual restic recovery, and GitHub create/push.
No performance, token-cost, free-tier billing or multi-tenant safety claim.

At original package authoring, repository lookup returned 404 and publication was
not performed. After the owner created the private repository, the reviewed 71-file
tree was published through the GitHub connector as commit
`d4d61e9932fa0516277a2c047bb9e20f12f23f07`. Its tree matched the local ZIP exactly.
This publication is separate from live OCI/model/Buzz execution.

## Publication-time CI follow-up

The first GitHub Actions run reached the tests but failed one backup fixture:
`Path.exists()` attempted to stat `/etc/sudoers.d/oracle-public-reader` on an
unprivileged runner. The fixture now limits existence checks to its temporary
state tree; no sudo is added to CI and no production permission check is weakened.

A local non-root replay also exposed an obsolete mock in the secret-redaction test:
it patched `subprocess.run` although the implementation calls `run_bounded`.
The mock now targets the real boundary and asserts the expected nonzero-exit path,
without looking up a real `tool` executable in PATH.

After these two test-only changes, **all 159 tests passed as the unprivileged
`nobody` account** in the local container. Deployment scripts are unchanged. The
package manifest was regenerated for the reviewed test/report changes. The latest
GitHub Actions run, not this local result, is the evidence for remote CI status.

## Re-run and integrity

```bash
python3 scripts/check.py
python3 scripts/publish.py  # no-network manifest verification + publication plan
```

The published-source file list is PACKAGE-MANIFEST.json. Its hashes detect accidental
changes, not malicious substitution by someone who can rewrite the manifest too.
Review changes before regenerating it. CI uses a verified checkout commit pin and
contents:read; it does not run provisioning or authenticate model services.

See REVIEW.md for findings, mitigations and residual limitations.
