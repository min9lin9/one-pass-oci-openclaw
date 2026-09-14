# Official sources and inspection scope

Checked 2026-09-14. These are source references, not an assertion of deployed version or
end-to-end compatibility. Source code and installer revisions must be resolved and reviewed
again by the local Codex `prepare`/`seal` workflow. Moving main/master links below are for
inspection; actual installation records resolved commit hashes separately.

## Core
- Codex skill structure and user discovery paths: https://developers.openai.com/codex/skills/
  (currently redirects to https://learn.chatgpt.com/docs/build-skills).
- OpenClaw skills: https://docs.openclaw.ai/tools/skills
- Native installer: https://docs.openclaw.ai/install/installer
  and https://openclaw.ai/install-cli.sh
- ChatGPT/OpenAI authentication: https://docs.openclaw.ai/providers/openai/setup
- OpenClaw Gateway configuration: https://docs.openclaw.ai/gateway/config-gateway
- OpenClaw security model: https://docs.openclaw.ai/gateway/security
- Native/ACP coding session differences: https://docs.openclaw.ai/tools/acp-agents
- Buzz channel, member and room role requirements, text/media limits:
  https://docs.openclaw.ai/channels/buzz
- Buzz production bundle: https://github.com/block/buzz/tree/main/deploy/compose
  Inspected README.md, compose.yml, .env.example, compose.caddy.yml and run.sh.
- Tailscale CLI and auth keys: https://tailscale.com/docs/reference/tailscale-cli
  and https://tailscale.com/docs/features/access-control/auth-keys
- Cloudflare DNS API: https://developers.cloudflare.com/api/resources/dns/subresources/records/
- Caddy automatic HTTPS/DNS challenge: https://caddyserver.com/docs/automatic-https
- Cloudflare Caddy module: https://github.com/caddy-dns/cloudflare

## Required gstack and insane-search
- https://github.com/garrytan/gstack/blob/main/README.md
- https://github.com/garrytan/gstack/blob/main/docs/OPENCLAW.md
- https://github.com/garrytan/gstack/tree/main/openclaw/skills
  Four native methodology skills are distinct from full coding-host skills.
  Full Codex-host setup is supported upstream; the actual OpenClaw route must still be tested.
- https://github.com/min9lin9/insane-search/blob/main/README.md
- https://github.com/min9lin9/insane-search/blob/main/skills/insane-search/SKILL.md
- https://github.com/min9lin9/insane-search/blob/main/skills/insane-search/engine/__main__.py
  Verified CLI flags, public-content scope, optional paid xAI path, plugin-root dependencies
  and optional Star prompt. The wrapper replaces host-specific entry instructions;
  it does not claim the whole Claude plugin is a native OpenClaw plugin.

## User repositories selected
- https://github.com/min9lin9/prompt-engineering-skills
  Inspected README and directory skill frontmatter; explicit owner fork is used.
- https://github.com/min9lin9/self-learning-skills
  Procedure learning and promotion rules; our deployment keeps new rules as proposals.
- https://github.com/min9lin9/baoyu-skills
  README discourages indiscriminate bulk installation; only baoyu-diagram is selected.
- https://github.com/min9lin9/pretty-mermaid-skills
  Inspected README and scripts/render.mjs. Node dependency resolution is prepared before use.
- https://github.com/min9lin9/markitdown
  Inspected README conversion/security/optional-dependency sections.
- https://github.com/min9lin9/mcporter
  Inspected README and CLI discovery behavior; runtime package is the official mcporter npm
  release, not a claim of compiling arbitrary fork changes.
- https://github.com/steipete/mcporter
  Official runtime publisher and usage reference.

## Additional operational OSS
- https://restic.readthedocs.io/en/stable/030_preparing_a_new_repo.html
- https://restic.readthedocs.io/en/stable/050_restore.html
  Encrypted repository and verified restore-to-directory; coherent application capture is
  our deployment procedure, not automatically guaranteed by choosing restic.
- https://gitleaks.io/
- https://github.com/gitleaks/gitleaks
  Secret detection is a supplementary check, not complete leak prevention.
- https://packages.ubuntu.com/noble/gitleaks
  Actual distro package versions are checked on the server. CLI differences must be inspected.

## Considered but not bulk-installed
- https://github.com/min9lin9/knowledge-manager
- https://github.com/min9lin9/visualization-stack-skills

The connected repository inventory was read to find candidates. Public/private metadata
visibility does not imply code review, installation or authorization to redistribute private
code. This package contains deployment-authored adapters, not vendored third-party projects.
No scientific or medical conclusions are derived from repository names or popularity.


## v0.3 additions — checked 2026-09-14
- OCI creator: https://github.com/min9lin9/oci-instance-creator (README and scripts/oci-create.sh)
- OCI Python SDK: https://docs.oracle.com/en-us/iaas/tools/python/latest/api/core/client/oci.core.ComputeClient.html
- OCI Free Tier: https://docs.oracle.com/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- OCI retry tokens: https://docs.oracle.com/en-us/iaas/Content/API/Concepts/usingapi.htm
- GBrain: https://github.com/garrytan/gbrain (README.md, package.json, src/core/config.ts)
- GBrain keyless guide: https://github.com/garrytan/gbrain/blob/master/docs/tutorials/connect-coding-agent.md
- ECC: https://github.com/affaan-m/ECC (agents/planner.md, architect.md, tdd-guide.md, code-reviewer.md)
- OpenClaw profiles: https://docs.openclaw.ai/gateway/multiple-gateways
- Agent config: https://docs.openclaw.ai/gateway/config-agents/entries-and-multi-agent
- Tool policy: https://docs.openclaw.ai/gateway/config-tools/tool-policy
- Agent CLI: https://docs.openclaw.ai/cli/agent
- Model CLI: https://docs.openclaw.ai/cli/models
- ChatGPT setup: https://docs.openclaw.ai/providers/openai/setup
- OpenCode: https://docs.openclaw.ai/providers/opencode
- OpenCode Go: https://docs.openclaw.ai/providers/opencode-go
- Codex authentication: https://developers.openai.com/codex/auth/

The package adapters are our implementation, not code delivered by those upstreams.
Readme/selected code review is not a full source security audit or a live integration test.
