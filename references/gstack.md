# gstack: two execution levels, both explicit

Official: garrytan/gstack README and docs/OPENCLAW.md.

## Native OpenClaw (default mandatory; operations only)
Install the actual upstream folders, not renamed Claude Code workflows:
- gstack-openclaw-office-hours
- gstack-openclaw-ceo-review
- gstack-openclaw-investigate
- gstack-openclaw-retro

These are conversational/methodology skills. Test them with a problem-framing,
review, diagnosis or retrospective request. They do not implement a browser runtime,
worktree pipeline, shipping or a full Claude/Codex host by themselves.

## Full Codex host (requested; additional mandatory acceptance item)
`stack.py gstack-full` installs an exact official Codex package in a separate prefix,
a reviewed Bun bootstrap and the reviewed gstack snapshot using `./setup --host codex`.
It records generated skill count and the specific CODEX_HOME in a root-only receipt.
The helper does not auto-publish, bypass approvals or assume a Claude subscription.

The operator must then:
1. Check the installed Codex CLI's real auth options. Run its ChatGPT device/browser
   login in the user's private terminal with the RECORDED CODEX_HOME. Do not copy
   OpenClaw's OAuth files or the PC's auth.json. OAuth identity is not automatically
   shared between independent harness homes.
2. Inspect gstack setup output and actual resolved browser/Bun dependencies. Verify
   read-only browser work on a harmless public test page and an untracked local test
   project. Generated files alone are not success.
3. Determine the installed OpenClaw version's harness integration: native Codex
   app-server and explicit ACP are different paths. Official ACP supports explicit
   Codex harness use, while native Codex has its own plugin/state. Read the CURRENT
   official Codex harness/ACP setup docs, discover its configured home/command fields,
   and route to the intended Codex instance. Do not guess a config key or turn on
   `approve-all`/permission bypass to hide a mismatch.
4. If using ACP, grant only the intended Codex target, keep concurrent coding jobs
   at one initially and test a one-shot session with a disposable project. Read-only
   planning must not mutate a live repository. Buzz may lack the same binding support
   as other chat channels; verify actual delivery rather than assuming thread parity.
5. Mark FULL_GSTACK_READY only when the target harness discovers the skill, runs it
   and returns an actual result through the intended OpenClaw/Buzz workflow.

A no-route/no-auth state is PENDING_HARNESS, not "gstack failed" and not READY.
Do not substitute Kimaki/Discord or Claude account requirements to make it pass.

Keep `/ship`, push/PR creation and deployment behind the specific user's write
request. Calling a planning skill does not authorize publishing a project.

## v0.3 owner and worker contract
Both native and full-host gstack assets belong to operations, not planning/development.
Operations uses gstack to frame/review the task and sends a bounded brief/approved plan
through the package's task socket. Workers run their own OpenClaw profiles using ECC
methodology. Native cross-profile ACP is NOT assumed. No direct gstack runtime access
is granted to workers. Full-host automation still requires a verified harness route;
its absence never blocks the four native conversational methods from being tested.
