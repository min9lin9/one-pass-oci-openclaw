# OCI-instance-creator integration

Requested source: https://github.com/min9lin9/oci-instance-creator
Read sources: README.md and scripts/oci-create.sh (reviewed via GitHub).

Upstream supplies an OCI launch workflow and repeat scheduling examples. Its shell
hardcodes 4 OCPU/24GB, boot200, AD/subnet/image/SSH public key and a Discord webhook.
The v0.3 adapter deliberately changes these properties:

| property | package |
|---|---|
| execution | local Python official OCI SDK, not upstream cron shell |
| resources | A1 2 OCPU/12GB, boot50 default |
| discovery | tenancy home region/AD/Ubuntu24.04 image + A1 compatibility |
| network | existing public subnet preserved, or dedicated tagged VCN/IGW/route/SL/subnet |
| ingress | specified SSH CIDR:22; public mode adds TCP443, Tailscale mode does not; no native Gateway ports |
| SSH identity | API-signed console-history fingerprint -> keyscan comparison |
| retries | bounded exponential backoff/jitter; no hidden cron/GitHub Action |
| idempotency | deployment tags + OCID + stable request token + intent hash |
| uncertainty | reconcile same AD/token; never launch a new shape after timeout |
| price | no free-tier guarantee from shape size; aggregate usage must be checked |
| cleanup | do not delete cloud resources on local failure/uninstall |

OCI API signer and SSH key are different. The former is pre-registered to an OCI
user; the latter can be generated locally by this skill and its public key is used
for the instance. Credentials are not put into cloud-init. Cloud-init prints only
the server's SSH public fingerprint to authenticated console output.

Local files: state/oci.json (managed resources/tokens/intent), state/oci-plan.json,
state/oci-handoff.json, state/ssh/oracle_ed25519, state/known_hosts, state/oci-sdk-venv.
Keep this state together and private. Deleting it is NOT a safe reset/retry procedure.
Use a different --state for another domain/tenancy/region. The handoff checks identity.

Capacity is not guaranteed. Three attempts are a retry policy, not assurance of allocation.
An ambiguous request token older than 23 hours requires operator reconciliation before
state reset. An explicit capacity rejection may retry another AD with a fresh rejected
request token; a timeout or transport failure does not justify rotating the request.
Quota/IAM/configuration failures stop. Never turn a free-only account into paid as a repair.

The package does not calculate authoritative tenancy-wide bills or create IAM users/policies.
API permissions may be restricted by compartment. Provide an authorized existing subnet
to avoid new network writes. Existing subnet routing/NSG/SL is inspected only to the extent
needed for a public VNIC; inaccessible SSH fails closed, never broadens SSH access.
Public HTTPS also needs TCP443 in the existing subnet/NSG. The operator checks that
prerequisite or applies a scoped authorized rule; shared existing lists are not
silently rewritten. Host firewall and OCI network ingress are separate layers.

Source acquisition, SDK dependencies and host installers need network access on the user's
PC. The embedded ZIP contains no OCI SDK wheel or third-party source archive. prepare pins
source revisions and SDK top-level version; the SDK venv records resolved transitives.
This is not a complete hash-locked binary supply chain for Ubuntu/pip/npm/system packages.
