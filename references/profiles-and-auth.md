# Profiles, credentials and orchestration contract — v0.4

## Native vs package-provided
Native OpenClaw: --profile config/state scoping, distinct Gateway ports, agents.entries,
tool allow/deny, native embedded provider runtime, provider authentication and agent CLI.
Package-provided: Linux UID/service ownership, Unix socket bridge, job receipts,
role instruction templates, ECC adaptation and GBrain CLI wrapper. No claim that
OpenClaw `sessions_send` crosses profile boundaries or that a role label provides isolation.

| profile | UID account | private state | listener | sources |
|---|---|---|---|---|
| operations | openclaw | /home/openclaw/.openclaw-operations | 127.0.0.1:18789 | GBrain/gstack + curated bundle |
| planning | clawplan | /home/clawplan/.openclaw-planning | 127.0.0.1:19789 | ECC planner/architect |
| development | clawdev | /home/clawdev/.openclaw-development | 127.0.0.1:20789 | ECC tdd-guide/code-reviewer |

Workers are in clawworkers for a single global execution lock, not each other's home group.
Task sockets are destination-owned, group openclaw 0660 and verify SO_PEERCRED.
No operator API or arbitrary subprocess interface is exposed. `approved_plan` is text,
not a cryptographic human-approval artifact. Config/Unix boundaries do not make LLM
intent reliable: external text must still be treated as untrusted task data.

## Credentials
OCI signing material: local Codex only. SSH private key: local PC only.
Cloudflare DNS token: local DNS management; certificate token: root-protected proxy.
Tailscale auth key: temporary root file, removed after enrollment.
Buzz human owner private key: local protected export/root state, not given to model.
Buzz bot key: operations only. Worker profiles don't receive a messaging identity.
OpenCode API key: chosen profile service environment loaded from root600 EnvironmentFile;
not baked into unit strings or printed subprocess args. A process with exec can read its own
environment; this is not protection from that profile's own malicious code.
OAuth: separate private store per profile. Do not replicate refresh-token caches.
GBrain: operations keyless memory, no API keys/connector/embedding/dream dependencies enabled.

Modes: chatgpt -> provider openai; opencode -> Zen; opencode-go -> Go.
OPENCODE_CATALOG controls the derived worker default, not subscription entitlement.
No fallback silently changes costs. Explicit model override must be in that profile's
refreshed catalog; live auth probe and agent-task execution are distinct evidence.
Direct `models status --probe` owns temporary state: stop only the target Gateway,
acquire the shared worker lock, probe, then restore the original service/socket state. No probing into concurrently-owned SQLite state.

## Role material
ECC files are installed in each worker's `workspace/references/ecc/` with license.
Local AGENTS.md chooses the workflow and actual OpenClaw policies. Source model labels
opus/sonnet are not used; no Claude provider is implicitly configured. No ECC MCP fleet,
autonomous learning hooks, cross-tool config importer or whole plugin install.

## GBrain
Install reviewed GitHub source using Bun >=1.3.11. `npm install gbrain` is wrong for
this project. Use GBRAIN_HOME in operations state; PGLite is single-owner. Wrapper
remember/recall calls lock one store and receive no provider key environment.
No full agent bootstrap, identity replacement, new private repo, cloud ingestion,
paid embeddings, cron or all bundled skills. Remember only explicit durable facts.
CLI smoke does not prove native tool use/new-session recall. Corrections/withdrawal
must be verified against the installed current CLI before extending the wrapper.

## Resource plan (limits, not measurements)
One delegated worker job at a time; each profile maxConcurrent=1. Three services share
an oracle-agents.slice ceiling 7GiB, each Gateway MemoryMax3GiB. These are policy caps,
not measured requirements or a guarantee that Buzz + browser + builds fit 12GB.
If OOM occurs, observe logs/load and reduce work; do not automatically resize OCI.
Large builds/full GBrain background enrichment are not part of this profile.

## Data handoff
Small plans, necessary excerpts, acceptance criteria and patches pass as structured text.
No implicit sharing of home directories. For an existing codebase, operations can provide
a public project reference and scope; development checks out only inside its workspace.
Private repository credentials or large artifact exports require explicit scoped setup.
A worker's absolute path is not automatically readable from another profile.

Changing auth policy, OAuth account or model invalidates prior PASS receipts before
configuration/probing. A failed catalog/probe leaves the task gate closed.

## v0.4 verification change
The packaged model check now refreshes/list the catalog with supported flags,
checks auth/runtime metadata, then runs a small actual Gateway marker turn.
It requires recognized assistant payloads and matching provider/model metadata.
Unknown/error/in_flight responses do not open worker readiness. This proves only
that narrow turn, not full coding capability or arbitrary access-control safety.
Configuration changes still invalidate previous readiness.
