# Graphify index — Create seller support case

**Last run:** 2026-06-04 · scope `agent/` · **841 nodes · 1745 edges**  
**Output (repo root):** `graphify-out/graph.json`, `graphify-out/GRAPH_REPORT.md`

**Tags:** `support-case`, `case-log`, `sp-api`, `seller-central`, `mahika`, `badeja-india`, `path-d`, `help-hub`

## God concepts (workflow)

- Case Log Path D — Help Hub → Create new issue → IP1 Hill
- **My issue is not listed** (`#issueNotListedButton`) → IP2 free-text
- SP-API production access + human-type variants (`support_case_text.py`)
- Prerequisite: `seller-login` + S7 Badeja → India
- IP3 contact → Email tab → Send

## Code hubs (AST graph)

- `support_case_flow.py`, `support_case_text.py`, `mahika.cli support-case`

## Related graph

- [seller-central-login/GRAPHIFY.md](../seller-central-login/GRAPHIFY.md)

## Regenerate

```powershell
cd "C:\Projects\Amazon Systems Design"
# /graphify agent   (AST + workflow semantic; graphify-out/ gitignored)
```
