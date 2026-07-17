# Graphify semantic chunk 1

- **Subtitle:** You are a graphify extraction subagent. Read these files and…
- **Project:** `c:\Projects\Amazon Systems Design`
- **Created:** 2026-06-17 08:41
- **Updated:** 
- **Status:** aborted
- **Model:** composer-2.5-fast
- **Messages:** 1
- **Composer ID:** `b3303cf5-6ade-45b1-8e72-3d5ced5cca71`

---
### User — 2026-06-17 08:41

You are a graphify extraction subagent. Read these files and write graphify-out/.graphify_chunk_01.json with valid JSON only (no markdown fences):

Files (Mahika agent + workflows):
- c:\Projects\Amazon Systems Design\AGENTS.md
- c:\Projects\Amazon Systems Design\WORKSPACE.md
- c:\Projects\Amazon Systems Design\agent\README.md
- c:\Projects\Amazon Systems Design\agent\docs\CHANGELOG.md
- c:\Projects\Amazon Systems Design\agent\docs\LAUNCH_READINESS.md
- c:\Projects\Amazon Systems Design\agent\docs\RUNBOOK.md
- c:\Projects\Amazon Systems Design\agent\docs\SETUP_QUICK.md
- c:\Projects\Amazon Systems Design\agent\Graphs & workflows\README.md
- c:\Projects\Amazon Systems Design\agent\Graphs & workflows\create-seller-support-case\BROWSER.md
- c:\Projects\Amazon Systems Design\agent\Graphs & workflows\create-seller-support-case\FLOW.md
- c:\Projects\Amazon Systems Design\agent\Graphs & workflows\create-seller-support-case\FORM.md
- c:\Projects\Amazon Systems Design\agent\Graphs & workflows\create-seller-support-case\GRAPHIFY.md
- c:\Projects\Amazon Systems Design\agent\Graphs & workflows\seller-central-login\FLOW.md
- c:\Projects\Amazon Systems Design\agent\Graphs & workflows\seller-central-login\GRAPHIFY.md
- c:\Projects\Amazon Systems Design\agent\Graphs & workflows\seller-reports\GUIDE.md

Schema: {"nodes":[{"id":"...","label":"...","file_type":"document|rationale","source_file":"relative/path",...}],"edges":[{"source":"...","target":"...","relation":"...","confidence":"EXTRACTED|INFERRED","confidence_score":1.0,"source_file":"...","weight":1.0}],"hyperedges":[],"input_tokens":0,"output_tokens":0}

Focus on: Mahika CLI commands, seller-login, support-case, Shorebird/RF Logger, workflows, OTP, Badeja account switcher, Case Log path D.

Write file to: c:\Projects\Amazon Systems Design\graphify-out\.graphify_chunk_01.json
Return summary: node count, edge count.
