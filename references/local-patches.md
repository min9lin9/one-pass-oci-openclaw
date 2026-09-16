# Local compatibility patches for the installed OpenClaw bundle

The deployment applies reviewed, minimal edits to OpenClaw's shipped minified
`dist/*.mjs` bundles. A package update replaces these files, so each patch is
recorded here with its exact anchor text and a re-apply/verify helper. These are
local compatibility fixes, not upstream source changes; do not describe the
patched files as stock.

## Helper

`scripts/local_patches.py` runs on the server against the live dist directory.
It resolves hashed bundle names by glob, verifies every replacement matches
exactly once, backs up the original file plus its SHA-256 under
`/var/lib/oracle-ai-stack/local-patches-<timestamp>/`, and only then writes.

```sh
# status only (no writes)
sudo python3 scripts/local_patches.py \
  --dist /home/openclaw/.local/lib/openclaw-cli/tools/node-*/lib/node_modules/openclaw/dist \
  --check

# apply any patch whose upstream anchor still matches
sudo python3 scripts/local_patches.py \
  --dist /home/openclaw/.local/lib/openclaw-cli/tools/node-*/lib/node_modules/openclaw/dist \
  --apply
sudo systemctl restart oracle-openclaw-operations.service
```

Statuses: `ALREADY_APPLIED`, `APPLIED`, `UPSTREAM_CHANGED`, `NOT_FOUND`.
`UPSTREAM_CHANGED` means the exact anchor text was not found — the patch was NOT
applied and must be re-reviewed against the new source. Never force-apply.

## Patch 1: plugins-route (applied 2026-09-16)

- File: `control-ui-share-*.mjs` (`classifyControlUiRequest`)
- Bug: direct load/refresh of `/plugins` returned a bare `404 Not Found` even
  though the client route table registers `plugins:{path:'/plugins'}` and the
  sidebar link points there. The server excluded the whole `/plugins` namespace
  from Control UI serving to keep it free for plugin-owned HTTP routes.
- Fix: narrow the exclusion to `/plugins/*` only, so bare `/plugins` serves the
  SPA. Plugin-owned routes under `/plugins/*` are still handled by the earlier
  plugin request stage, so they are unaffected.
- Live evidence: original SHA `f81f6f8d…`, patched SHA `08d2549f…`; after
  restart `curl -H 'Accept: text/html' /plugins` returns 200 and the Plugins
  page renders. Backup: `/var/lib/oracle-ai-stack/installation-review.plugins-route-1789527587/`.

## Patch 2: clawhub-versions-5xx-fallback (applied earlier, 2026-09-16)

- File: `management-service-*.mjs` (ClawHub plugin detail fetch)
- Bug: ClawHub `GET /api/v1/packages/<name>/versions` returned HTTP 500, which
  made the whole plugin detail page fail.
- Fix: catch a 5xx on the versions-list call only, fall back to the
  independently fetched selected release, and surface a README warning plus a
  `versionHistoryError` field. Auth/4xx and selected-release failures still
  throw; package and release checks are not bypassed.
- Live evidence: original SHA `2c8925d4…`, patched SHA `f7242704…`; detail page
  shows versions 2026.9.3 → 2026.7.2-beta.2. Backup:
  `/var/lib/oracle-ai-stack/installation-review.1c0kGxUJ/management-service.before.mjs`.

## Remaining upstream bugs (not patched — client router, report upstream)

These live in the minified client router and are risky to patch locally; they
should be reported to OpenClaw upstream rather than edited in the bundle.

- In-app navigation never updates the URL (no `pushState` on page-level nav),
  so refresh/back/bookmark lose the current page. Combined with the fixed
  `/plugins` 404 this made the Plugins page un-bookmarkable.
- Bare `/settings` and `/dashboard` (and other unregistered bare routes) render
  the Home session view with a 200 instead of redirecting to a real section or
  showing a not-found state. `/dashboards` and `/settings/<section>` work.

## Re-apply after a package update

1. Update OpenClaw through the reviewed update runbook (`references/lifecycle.md`).
2. Run `local_patches.py --check` against the new dist directory.
3. For each `APPLYABLE` patch, run `--apply` and restart the gateway unit.
4. For any `UPSTREAM_CHANGED`, re-review the new source; the bug may be fixed
   upstream (drop the patch) or need a re-based edit (update the anchor text).
