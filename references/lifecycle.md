# Operations, migration and explicit recovery

## Repair
Keep the existing reviewed source stage. Inspect state/health, restore missing
managed files, and rerun failed phases. Never erase local skill changes or Git reset
user content. Re-running setup may stop on an upstream/missing dependency; report
that phase instead of ignoring its exit code. Do not renew one-use Tailscale keys
when the existing Tailnet session is already running.

## v0.1/v0.2 migration is not zero base
v0.1 used /home/ubuntu and /opt/buzz, potentially sudo/docker access, a different
Compose project, and incomplete backups. v0.3 stops on old or unmanaged deployments. v0.2 used one OpenClaw identity; its state must not be copied into all three profiles.
Inventory actual project volume names and OAuth state, take a coherent backup of
ALL Buzz stores, confirm current networking, then migrate into the new dedicated
user/versioned paths. Never run a "fresh install" over existing data. Reauthenticate
where supported rather than blindly moving another application's credential files.

## Reviewed update
The CLI update guard performs source verification and backup, then stops. Codex must
execute this runbook; the helper is NOT an unattended upgrader.

1. Prepare a NEW stage; inspect diffs and release notes; lock exact versions and
   digests. A missing ghcr source-SHA tag must be resolved to a published matching
   source/image pair or built from that reviewed source, not silently main:latest.
2. Back up coherently and export it to another machine; record the snapshot ID and
   verify restore-to-staging BEFORE a risky schema change.
3. Update one component per step in a maintenance window. OpenClaw: use the official
   native installer/update flow for the chosen exact version, preserve config,
   verify CLI version/config validation and restart the known unit. Buzz: stage the
   new immutable source beside the previous source; render new private compose;
   pull/record digests; inspect migrations; switch only when rollback is prepared.
4. Do not delete the previous source, compose, `.env`, database/MinIO/Git snapshot or
   receipts. Image rollback does NOT undo database migrations; data rollback may
   require restoring the entire consistent snapshot.
5. Re-run TLS, auth, roles, actual Buzz roundtrip and extension smokes. Only then
   mark the change complete; otherwise preserve failure evidence and recover.

## Encrypted backup
`stack.py backup` refuses active delegated tasks, pauses both worker socket listeners,
locks worker execution, stops all three managed Gateway services and running
Buzz/proxy containers, snapshots state with restic, and resumes the original
running set in finally. Manually started writers outside these managed services
must also be stopped by the operator. It includes PostgreSQL, Redis, MinIO, Git and proxy volumes,
All three profile homes (including independent auth stores and the operations
GBrain PGLite database), identities, config, source/runtime files, units and sockets
are included. A Git clone is not a GBrain database backup.
Do not claim a hot pg_dump alone preserves object/Git consistency.

Repository: /var/backups/oracle-ai-stack/restic
Password: /etc/oracle-ai-stack/restic-password (root, 0600)

The repository is ENCRYPTED but its local presence is not off-site disaster recovery.
Export from a quiescent restic repository under the operations lock, using SSH's
stdout streamed directly to a local mode-0600 file, NOT an LLM-visible command
response. Copy the password separately to protected local recovery storage; never
print it. Avoid holding a potentially large archive in Python memory. Do not upload
backups to a new external service without permission. Verify the copied repository
with restic and retain both repository and recovery key independently of the VM.

## Restore (actual helper behavior)
`stack.py restore --snapshot EXACT_ID` resolves a unique stack-tagged snapshot,
restores with `--verify` into /var/lib/oracle-ai-restore/<full-id>, checks domain,
and returns the staging path. It does not overwrite live files or restart data
services from a different schema. This is a real restore-to-staging, NOT a live
recovery test or stub claiming success.

For an authorized IN-PLACE recovery, the Codex operator must first capture the
current-state backup and the exact intended snapshot and scope. Compare the backup
inventory to current mountpoints. Stop the managed writers; verify sufficient space;
restore each known volume and managed path from staging with ownership preserved;
retain rollback copies; use the snapshot's matching image digests and compose;
reload only the managed units; restart; validate the actual application data, owner
identity, authentication and message exchange. Do not copy arbitrary absolute paths
from an untrusted archive to /. Never overwrite unrelated Docker volumes, SSH,
Tailscale machine state, Oracle metadata, or another deployment.

If a validated restore driver does not yet exist for the actual deployed versions,
write and test the explicit plan in a disposable instance before overwriting the
only live copy. Say which stage is pending; do not say recovery is complete.

## Uninstall
`stack.py uninstall --confirm uninstall:<domain>` refuses active worker jobs, disables
the three managed Gateway services and worker sockets, and takes down
only managed containers, without `docker compose down -v`. It leaves data, backups,
users, credentials, DNS, SSH and Tailscale. Permanent purge, DNS removal and token
revocation are separate explicit destructive actions. Never disable the management
path during a remote uninstall.

OCI instances, VCNs, subnets, disks and retry/handoff records are NOT deleted by uninstall.
Do not interpret instance creation permission as authorization to terminate resources.
