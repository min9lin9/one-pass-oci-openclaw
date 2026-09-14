# Repository working contract

This repository is `min9lin9/one-pass-oci-openclaw` (spelling intentional).
It contains a local Codex deployment skill, not a deployed Oracle instance.

Read SKILL.md for deployment, REVIEW.md for known findings, and SECURITY.md before
changing privileges or inputs. Preserve operations/planning/development isolation,
Buzz, Tailscale-only access, and explicit ChatGPT/OpenCode authentication choices.

Run `python3 scripts/check.py` after edits. Tests are offline unless individually
and explicitly authorized. Never run OCI creation, OAuth, network installs, source
hooks, publish, or star operations just to make a unit test pass. No secrets in Git.

Any modification invalidates PACKAGE-MANIFEST.json. Re-review selected content and
regenerate it with the documented package_manifest.build function; never regenerate
it to hide an unexplained mismatch. Keep existing source/data/operator-state schema
separate from the package version. Do not rewrite user-owned role files silently.

Report source review, local tests, live integration, and publication as separate
facts. Never invent successful deployment logs, identity values, tests or commits.
