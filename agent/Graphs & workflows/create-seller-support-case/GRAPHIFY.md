# Graphify — create-seller-support-case

**Tags:** `support-case`, `case-log`, `sp-api`, `path-d`, `help-hub`, `badeja-india`, `nil`, `ip2`

| Doc | Role |
|-----|------|
| [FLOW.md](FLOW.md) | Master tree + Playwright |
| [BROWSER.md](BROWSER.md) | Cursor browser lane |
| [FORM.md](FORM.md) | Case text + typing |

## Graph outputs (project root)

`graphify-out/` on repo root — regenerate:

```powershell
cd "C:\Projects\Amazon Systems Design"
# full: /graphify agent
# incremental: /graphify agent --update
```

| File | Kya |
|------|-----|
| `graphify-out/graph.html` | Interactive graph |
| `graphify-out/graph.json` | Raw graph |
| `graphify-out/GRAPH_REPORT.md` | Audit report |

## Path D nodes (semantic)

- `browser_path_d` → Help Hub → NIL → IP2 → Send
- `help_hub_case_flow` → `_ensure_help_hub_once`, `_wait_ip2_expand`, label-based IP2 fill
- `no_fallback_rule` → no Case Lobby / developer portal on fail
