# Cursor rules — superseded 17 Jul 2026

These 5 `.mdc` files were the project's Cursor rules, living at `.cursor/rules/`.
They are archived, not deleted — git history is preserved (moved with `git mv`).

## Why archived

The project migrated from Cursor to Claude Code. Every rule here has a live successor:

| Archived rule | Replaced by |
|---|---|
| `seller-central-login.mdc` | `.claude/skills/seller-central-login/SKILL.md` |
| `create-seller-support-case.mdc` | `.claude/skills/create-seller-support-case/SKILL.md` |
| `shorebird-release-strategy.mdc` | `.claude/skills/shorebird-release/SKILL.md` |
| `short-clear-hindi.mdc` | `CLAUDE.md` — "Communication style (Sir)" |
| `cursor-glass-browser.mdc` | `CLAUDE.md` — "Browser — must be visible" |

`cursor-glass-browser.mdc` is the only one with **no** live equivalent by design: the Glass
browser mechanism it documents (`Ctrl+Shift+B`, `glass-browser-*` viewIds, the WebView mount
bug) does not exist outside Cursor. The rule that survived is the *intent* — Sir must be able
to see the browser window — now served by the Browser pane (`mcp__Claude_Browser__*`) or
Claude in Chrome (`mcp__claude-in-chrome__*`).

## Related

- Full Cursor chat history: `.claude/cursor-history/` (15 conversations + `INDEX.md`)
- Wider Cursor backup: `C:\CursorArchive\backup\dot-cursor\`
- Cursor-era specs left in place as historical record: `specs/cursor-browser-troubleshooting.md`,
  `specs/seller-central-flow/`

## Do not

Do not restore these to `.cursor/rules/`. If a rule here has content the live skill lacks,
port that content **into the skill** — do not revive the file.
