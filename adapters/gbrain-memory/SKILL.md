---
name: gbrain-memory
description: Operations-only explicit persistent memory with GBrain; keyless recall and remember, provenance, and serialized local PGLite access.
---
# GBrain memory — operations owner
Use the real installed runtime through the fixed wrapper:
```sh
python3 /opt/oracle-ai-stack/scripts/memory_cli.py recall projects/<name>
python3 /opt/oracle-ai-stack/scripts/memory_cli.py remember --entity projects/<name> --provenance '<source and date>' --text-file ./explicit-memory.txt
```
Only save explicitly requested durable facts or decisions. No automatic conversation
capture, bulk imports, email/calendar connectors, embeddings, synthesis or dream
workers. No other provider API key is needed for this memory-only mode.
The wrapper serializes access to the operations PGLite database. Do not start a
separate MCP `gbrain serve` process on that same database or remove its live lock.
Preserve the existing native OpenClaw memory and identity. Do not create a GitHub
repository or run GBrain personal-agent bootstrap.

Recall the named entity before answering questions about saved decisions. Cite
its provenance and distinguish facts from proposals. Verify every write using
an independent recall. To test durable recall, use a new conversation; current
chat context is not evidence.

Correction/withdrawal requires the current GBrain `forget`/correction contract.
The wrapper deliberately offers read/remember only. For deletion or correction,
request the human operator to inspect the installed CLI and retire the old fact,
then verify recall. Do not merely append a contradictory fact and call it fixed.
History/backups may retain withdrawn data. Never save tokens or secret values.
