# Third-party materials

This package's MIT license covers its own deployment code, adapters and documentation.
The source repositories named by `manifests/*.json` are fetched at deployment time;
they are not bundled in this release. Each dependency retains its own original
copyright and license. Keep upstream LICENSE files with copied skill directories.

- `min9lin9/oci-instance-creator`: workflow reference; the OCI SDK adapter is an
  explicitly modified implementation with different quotas/retry/network policies.
- `garrytan/gbrain`, `garrytan/gstack`: distinct upstream projects. Only approved
  profile-scoped integrations are enabled. No upstream endorsement is implied.
- `affaan-m/ECC`: selected role methodologies; retain their license and original
  reference files; do not import model bindings/hooks as active configuration.
- User-named prompt/search/document/diagram repositories: source IDs, origin and
  expected subpaths are recorded in `manifests/extensions.json`.
- OpenClaw, Buzz, Caddy and its Cloudflare provider, Tailscale, Bun, OCI SDK, restic,
  Gitleaks and other dependencies have separate distribution terms.

A source reference, GitHub star, or package install is not a license review.
The deployment source review must check the specific pinned version before use
or redistribution. No font assets, user credentials, lecture documents or private
repository contents are included in this public-source package.
