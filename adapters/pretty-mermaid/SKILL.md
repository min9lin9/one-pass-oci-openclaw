---
name: pretty-mermaid
description: Render Mermaid diagrams as local SVG or ASCII with the pinned min9lin9 pretty-mermaid-skills implementation, without launching a browser.
---
# Pretty Mermaid
Read the installed source's SKILL.md only as reference, located through
`~/.local/state/oracle-ai-stack/runtime-paths.json`. Run its scripts with the pinned
private Node runtime; never auto-install a different package version on first use.
Create the Mermaid source in the workspace, run `scripts/render.mjs --input INPUT
--output OUTPUT --theme github-light` from the prepared runtime directory, then
verify actual SVG output and retain the source. No external upload or publishing.
When a user supplies a design system (such as Design.md), honor it over a theme.
A syntactically valid diagram is not evidence the described system has been tested.
