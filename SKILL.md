---
name: one-pass-oci-openclaw
description: Provision Oracle ARM from OCI account variables and operate private Buzz plus native OpenClaw with isolated operations/planning/development profiles; operations owns GBrain and gstack; support ChatGPT OAuth or OpenCode Go/Zen API credentials.
---
# One-pass OCI OpenClaw — local Codex deployment controller v0.4-beta

Read REVIEW.md and SECURITY.md first. Then read README.md, references/profiles-and-auth.md and references/oci-provisioning.md.
This is a LOCAL Codex skill; the target does not need OpenClaw or even an existing
VM. The user approved Oracle A1 2 OCPU/12GB, Ubuntu24.04ARM, Buzz production Docker,
native OpenClaw, Tailscale-only buzz.<domain>/openclaw.<domain>, Cloudflare DNS-01,
local secrets, GBrain/gstack owned by operations, and distinct planner/developer.
Do not ask these same decisions again. No Kimaki or Discord migration.

## Authority and secret handling
The user supplies ~/.config/oracle-ai-stack/secrets.env. Do NOT cat it into chat,
log it, source it, commit it, send it to research tools or ask for plaintext keys.
Use the provided Python parser and stdin transports. A missing value can be
requested by variable name and local file path. Ask only for genuinely missing
non-discoverable values or mandatory login/owner approval. Account creation,
API-key registration, domain purchase, Tailscale account membership and model
subscription cannot be invented from cloud IPs.

Read-only plan/discovery is not permission to execute unreviewed repository hooks.
For a user-requested setup, reviewed standard provisioning and curated installs
are authorized. Do not enable paid shape fallback, change account billing,
create global IAM policies, disclose personal data, or delete pre-existing state.
API keys/cert secrets go only to their intended execution scopes. OCI signing
private keys and passphrases stay on the local PC and are never uploaded to the VM.

## Execution workflow
1. Inspect local tools and load secret presence without printing values. Python3.11+,
   Git and OpenSSH are needed. Use WSL2 for Windows. Check local file600 permissions.
2. Run `python3 scripts/stack.py plan`.
3. `prepare`: stage sources and exact revisions; no upstream install scripts run.
4. Review `references/source-review.md` and all added auxiliary source contracts:
   OCI creator shell, GBrain package/postinstall/init/config paths, and ECC selected
   agents. Read primary upstream files. Missing license, source mismatch, changed
   unsafe installer, unknown ARM dependency: stop or adapt before deployment.
   Record substantive review notes outside the repo and call `seal`.
5. `oci-plan`: official SDK read-only cloud discovery. Verify home region, 2/12,
   boot50, compartment, image ARM compatibility and initial SSH source CIDR.
   Check existing free allowance/cost in the user's console; size caps alone are
   not a billing guarantee. Do not pretend account credentials solve capacity.
6. `setup`: creates managed network/VM if ORACLE_HOST absent, or uses matching
   private handoff from prior run. Uses tags/OCID/stable retry tokens, bounded
   attempts; no cron or silent larger shape. Obtains hostkey from signed console
   history, compares with SSH scan, then waits for cloud-init before configuring.
7. Install Buzz, three isolated native profiles, private TLS, curated extensions,
   operations GBrain memory-only. Run each installer through scripts/stack.py,
   not ad hoc curl piped to root. Preserve existing configuration and user edits.
8. Authentication: API workers are configured/probed with the explicit key/mode.
   For each selected ChatGPT profile call `oauth --profile <name>` in an interactive
   user-visible terminal, then `models --profile <name>`. Never copy local
   ~/.codex/auth.json or duplicate refreshing OAuth caches across profiles.
9. gstack native four methods are ops-only. If using full host features, run
   `gstack-full`, then authenticate its separate Codex home and verify its actual
   read-only harness route/browser support. Do not assume OpenCode API key logs
   into Codex or a Claude subscription exists. Preserve pending state otherwise.
10. Buzz identity: export owner privately, create/select a room as the human owner,
    authorize dedicated bot's room role, set BUZZ_ROOM_ID, then `bind-buzz`.
11. Run `profiles --probe` (actual short inference), `memory-smoke`, `acceptance`, and the real client
    checks in references/acceptance.md. Confirm new-conversation memory, plan→dev
    execution, a sample regression test, and Buzz response. Config/CLI tests are
    not proof of actual chat integration. Report blockers precisely.
12. Back up, export offsite, restore into staging and verify. Do not call staged
    restore a completed live disaster-recovery test.

A planned source download that cannot complete must not be reported as installed.
No Oracle credentials available here means deliver code/plan only, not a claim of
remote execution. Mark tested evidence separately from source review/assumptions.

## Profile ownership
- operations / openclaw / 18789 / .openclaw-operations: user-facing Buzz, GBrain,
  gstack, selected skills, final approval/review/dispatch. Not administrative root.
- planning / clawplan / 19789 / .openclaw-planning: ECC planner+architect references;
  OpenClaw read-only tools. Returns a plan, not code mutations.
- development / clawdev / 20789 / .openclaw-development: ECC TDD+review references;
  own workspace code/test execution only. No production/cloud credentials.
No shared agentDir, auth store, workspace or service. gbrain/gstack not globally
copied to workers. ECC model/tool frontmatter and hooks are source text, not actual
configuration. Actual provider is per-profile OpenClaw config+auth.

## Cross-profile orchestration contract
The packaged dispatch.py/worker_bridge.py implement a Linux Unix-socket adapter;
it is NOT native cross-profile sessions_send/sessions_spawn. Operations can call
planning/development sockets; workers cannot call operations or each other's socket.
A task is a UUID + bounded prompt + development approved_plan. This approved_plan
field is a workflow check, not proof of human consent. Role instructions still
require human approval for privileged/irreversible actions.
Jobs are serialized globally. Persist input hashes/results. On uncertain timeout,
use status and inspect actual execution; never rerun a changed/destructive task with
an arbitrary new UUID. Each profile sees its own files. Small patches/briefs return
as text. Bulk filesystem sync/export remains an explicit operator operation.

## Additions / lifecycle
Maintain the curated extensions manifest. Review and pin useful additions in the
already-approved scope; do not mass-copy a user's public/private repositories.
No global plugin hook installation, secret imports, remote posts or auto-stars.
Only min9lin9/prompt-engineering-skills has explicit Star authorization; use local gh
and confirm via GET, leaving pending if unauthenticated.

setup and repair reuse reviewed versions; they don't delete user modifications.
update and live restore require references/lifecycle.md, not a false all-green
receipt. uninstall requires exact token uninstall:<domain> and retains OCI
resources/data/access. Never terminate an OCI VM as an implicit cleanup action.

## Output
Return phase receipts and local private paths, URLs (without tokens), and exact
observed status. Distinguish OCI_CREATED, RUNTIME_INSTALLED, AUTH_PROBED,
DELEGATION_TESTED, MEMORY_CLI_TESTED, MEMORY_CHAT_TESTED, BUZZ_CHAT_TESTED.
No passwords, model tokens, owner private keys or raw OAuth callback contents.

## v0.4 review and repository publishing
Run `python3 scripts/check.py` before packaging. `scripts/install_skill.py` installs
to ~/.agents/skills/one-pass-oci-openclaw and refuses user-edit overwrites.
The GitHub publication target is exactly min9lin9/one-pass-oci-openclaw.
`python3 scripts/publish.py` is a no-network plan. `--apply` requires the user's
local gh login as min9lin9 and creates a private repository by default. Public
visibility needs explicit --public. Existing nonempty repositories need a normal
read-first branch/PR review; never force-push. Publication status must come from
actual remote verification, not from the presence of the publisher or a ZIP.
Never publish local state, .env, OCI keys, auth caches, stages or review-note text.

The command compatibility/readiness fixes are in REVIEW.md. Source changes require
a new prepare/review/seal. A passing metadata check is not model inference; only
a recognized assistant response with the expected marker and model identity
opens the model-ready gate. An unknown JSON schema stays unverified. Backup
service-resume errors are failures even when a snapshot was created.
