# Retired Buzz deployment reference

The current user-approved design is OpenClaw-only. This document describes the
former setup for historical recovery context, not an active installation workflow.
Do not run its bootstrap or binding steps as part of current setup/repair.
Existing Buzz volumes, protected keys and earlier encrypted backups are retained;
their deletion or reactivation requires a separate explicit request.

Official sources: block/buzz deploy/compose; docs.openclaw.ai/channels/buzz.
The production backend is the relay with Postgres, Redis, MinIO and Git data. A
working relay URL is not evidence that a web front end, owner login, bot room role
or model-backed message exchange is already working.

## Private identities
The server creates separate owner/relay/OpenClaw-bot keys using a maintained
secp256k1 implementation. Owner public key can instead be supplied by an existing
user. The owner PRIVATE key stays root-only and is exported through SSH directly
into the PC's protected `state/buzz-owner.secret.json` (never printed). OpenClaw
receives ONLY its dedicated bot key. Do not copy the owner secret into its workspace.
A locally generated owner key needs secure recovery storage outside this VM.

## Complete first room creation without inventing CLI syntax
The installed OpenClaw plugin cannot create rooms or automatically grant approvals.
The LOCAL Codex operator may perform those actions with the owner's explicit account
authority, using the official Buzz CLI, without granting owner rights to OpenClaw.

1. Inspect the prepared Buzz version's `crates/buzz-cli` README/help and available
   packaged binaries. Detect the actual `buzz` or `buzz-cli` name rather than guessing
   an npm package. If the relay image contains only buzz-admin, obtain/build the
   matching official CLI in an operator context. Record any extra build dependency.
2. Connect an official Buzz client to `wss://buzz.<domain>` while on Tailscale. Import
   the owner key in the PRIVATE client setup. Do not paste it into a chat message.
3. Use the actual CLI's documented channel-create/list command as owner. Parse the
   returned UUID, and make a single private working room (default name can be personal).
   Do not invent an HTTP endpoint, edit SQL tables directly or declare a room exists
   after a failed CLI call. If the version offers only interactive creation, guide
   that one owner step and resume immediately afterward.
4. Relay membership is added by the infrastructure worker. Grant room Bot role via
   the documented owner command, using protected environment/file references:

   `buzz channels add-member --channel ROOM_UUID --pubkey BOT_PUBLIC_KEY --role bot`

   The public key is safe to show; the owner's private key is not. Room role is distinct
   from relay membership. The official docs warn the desktop client cannot reliably
   assign the external OpenClaw identity this Bot role.
5. Save UUID as BUZZ_ROOM_ID in the local secret/config file; `stack.py bind-buzz`.
   It sets owner-only sender allowlist and the exact room, not wildcard access.
6. Probe the recorded operations binary with `--profile operations channels status --channel buzz --probe`. A shell process/HTTP 200
   does not prove authenticated room access.
7. Send a unique harmless challenge from the human owner in Buzz; observe the actual
   OpenClaw answer in the SAME room/thread. Keep message IDs and timestamps, not
   just a screenshot saying "online". This is the required acceptance test.

## Current connector boundaries
Official docs currently list group text/Markdown/structured diffs, not native file
uploads/downloads, DMs, reactions, room creation or automated owner approval. Do not
promise that uploading a PDF to Buzz automatically gives OpenClaw the file. For
this release, place permitted documents into the OpenClaw workspace through an
operator-approved transfer and refer to their path in Buzz, until file transport is
implemented and tested independently.

## v0.3 routing
Only operations connects to Buzz and holds the dedicated bot identity. planning and
development do not log into Buzz or share its room token. Operations dispatches tasks
through the two restricted Unix sockets and returns their reviewed result to the room.
The private web proxy exposes only operations, not the worker Gateways.
