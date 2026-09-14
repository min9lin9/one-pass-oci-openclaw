# Test report — 0.4.0-beta

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

A GitHub repository lookup returned 404 under the current connector. This session
does not expose a repository-create action or an authenticated local gh client.
The local publication helper is included and offline-tested; it was NOT applied.

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
