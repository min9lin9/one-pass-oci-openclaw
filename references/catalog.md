# Extension selection and future additions

## Scope of this review
The connected min9lin9 repository inventory and the official READMEs/selected
integration files were inspected on 2026-09-14. This is a targeted suitability
review, NOT a line-by-line security audit of every repository or transitive dependency.
All execution candidates are downloaded again at invocation, pinned and reviewed by
local Codex before installation. Private repositories and private metadata are not
included in this redistributable package.

## Included now

| Source | Why included | How hosted | Verification required |
|---|---|---|---|
| min9lin9/prompt-engineering-skills | Request decomposition, prompting and variation | Two directory skills | Recognized names + realistic prompt task |
| garrytan/gstack | Product problem framing, CEO review, diagnosis, retrospectives; advanced coding workflow | Four upstream native OpenClaw skills + separate full Codex-host installer | Methodology response; full host discovery/auth/browser/route separately |
| min9lin9/insane-search | Public URL retrieval when the normal fetcher is insufficient | Actual engine under clawfetch UID + adapter | Import/CLI, public URL, blocked metadata/Tailnet, timeout |
| min9lin9/self-learning-skills | Turn successful workflows into reusable knowledge | Proposal-only adaptation | No active skill/config write on example learning request |
| min9lin9/baoyu-skills | General-purpose diagrams | Only baoyu-diagram | Render actual SVG, preserve source, no publish |
| min9lin9/pretty-mermaid-skills | Local lightweight structured diagrams | Prepared Node dependencies | Valid SVG from Mermaid and readable labels |
| min9lin9/markitdown | Ingest source documents for grounded work | Separate Python venv, local conversion | DOCX/PDF fixtures; scanned input reported honestly |
| min9lin9/mcporter | Use declared MCP tools without adding a second agent product | Exact official npm runtime; fork retained as reference | CLI works; empty isolated imports; per-server auth/schema checks |
| restic/restic | Encrypted state preservation for a self-hosted stack | Operator-side distro package | Consistent stop/backup, separate copy, staged restore verify |
| gitleaks/gitleaks | Detect accidentally embedded credentials | Operator-side distro package | Redacted synthetic-secret test; no claim that a clean scan proves safety |

The native SKILL count and source-group count are different. In particular, one
gstack repository contributes four native skills. Do not market every Markdown file
as a separately installed and proven capability.

## Not in the default active bundle

- knowledge-manager: useful knowledge-management ideas, but the inspected workflow
  contains Claude-specific paths/tools and external integrations. It overlaps current
  memory/learning needs. No wholesale settings/hooks or permissive-mode copying.
- visualization-stack-skills / slides-grab / bananatape: possible future visual
  workbench, but require additional browser/runtime/auth work. The user's OpenClaw
  OAuth is not assumed to authorize another tool. Keep separate from core setup.
- All of baoyu-skills: upstream explicitly discourages bulk installation; select
  a fitting skill. Exclude social autoposting, reverse-API/cookie login routes and
  provider-priced image generation until specifically authorized.
- A second primary harness/agent platform, ERP, trading systems and specialized
  legal/medical/financial apps: not baseline personal OpenClaw infrastructure. Add
  a specific relevant read-only tool only when there is a task and verified scope.
- GPU/local-model stacks, large embedding databases, extra browser farms: do not
  automatically install them on a 2-OCPU VM. Measure needs before enlarging scope.

These are scope/compatibility decisions, not assertions that excluded projects are
malicious or low quality. Repository popularity alone was not used as approval.

## Autonomous discovery within the approved scope
1. Run `stack.py discover`; retain only public metadata in the candidate report.
2. Inspect the actual official repository, license, supported OS/arch, skill format,
   entry scripts, dependencies, writes, credentials and network destinations.
3. Choose a small non-duplicating capability. If it is a directory SKILL with no
   additional runtime, add it to the manifest using the same `skills` path pattern.
4. If a runtime is required, implement a bounded adapter + installer + smoke test.
   Do not list it as active merely because the source was cloned.
5. Use a NEW stage directory, review and seal the new source set, then install.
   Preserve local user edits and provide an uninstall/data-retention plan.
6. Record included/excluded/deferred reasons. New paid or broad-privilege actions
   require authorization, not an automatic interpretation of "add useful tools".

No future periodic scan or background installation is scheduled by this package.


## v0.3 assignment and auxiliary sources
All v0.2 curated extension installs now target only the operations workspace.
GBrain (garrytan/gbrain, latest-stable resolved at prepare) is additional keyless,
explicit, operations-only PGLite memory via a narrow CLI adapter. It is not a silent
replacement of OpenClaw memory or installation of the full personal-agent bootstrap.
ECC (affaan-m/ECC) supplies four licensed source reference files: planner/architect
for planning, tdd-guide/code-reviewer for development. Model labels/hooks are not
executable config in these profiles. OCI creator's launch logic is adapted in the
local SDK provisioner; its original shell is staged for review, not executed.
Exact input sources and role assignments: manifests/bootstrap-sources.json.
GBrain and gstack ownership is exclusive to operations; no duplicate global install
in the two worker profiles. Existing extensions remain installed, not discarded.
