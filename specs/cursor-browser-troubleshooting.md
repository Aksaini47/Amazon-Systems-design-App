# Cursor Glass browser — troubleshooting (Amazon Systems Design)

**Symptom:** Agent says browser opened / Amazon page loaded, but Sir sees nothing on the side.

**Verified on this machine (May 2026):** `glassMode: true`, Windows, Cursor Glass/Agents window.

---

## Black browser panel but tab visible (Screenshot pattern)

**Symptom:** Right side shows Browser tab + URL bar "Search or enter URL" but **content area is black/empty**.

**Cause:** Browser **tab is open** but **no URL was pushed to the visible WebView** — MCP was driving a hidden backend tab OR navigate ran without `position: "side"`.

**Fix (agent — use this first when panel is black):**

```json
browser_navigate({
  "url": "https://sellercentral.amazon.in/signin?ref_=INscwp_signin_n&mons_sel_locale=en_IN&ld=SCINWPDirect",
  "newTab": true,
  "position": "side",
  "take_screenshot_afterwards": true
})
```

Do **NOT** pass old `viewId` (e.g. `glass-browser-...`) — that tab is detached from Sir's visible panel.

Creates fresh viewId (e.g. `5fcedf`) wired to the side panel. Verified working after black-screen bug.

**Fix (Sir if still black after agent navigate):**

Working state (afternoon): panel showed `sellercentral.amazon.in/home` — tab + navigate were connected.

**Log file:** `%APPDATA%\Cursor\logs\...\1-Cursor IDE Browser Automation.log`

```
Failed to inject browser UI script: The WebView must be attached to the DOM
and the dom-ready event emitted before this method can be called.
```

Plus: `Timed out waiting for glass browser view` on new browser tabs.

**Meaning:** Glass Agents window has a **broken/disconnected browser WebView**. Agent MCP still drives a hidden backend tab; Sir's UI never mounts the panel. **Not fixable by navigate/position alone.**

---

## Fix (Sir — in order)

### Step 1 — Glass Browser tab shortcut (try first)

**`Ctrl+Shift+B`** — Glass command `glass.openBrowserTab` (Browser tab)

NOT the same as Command Palette "Simple Browser". Use this exact shortcut while focus is on Cursor Agents window.

### Step 2 — Editor Window (most reliable)

**`Ctrl+Shift+N`** → **Open Editor Window**

OR menu: **File → Open Editor Window**

In the **Editor** window (not Agents-only Glass), open Browser via Command Palette → **Simple Browser: Show** or agent navigate with `position: side`.

### Step 3 — Reload Cursor (if Step 1–2 fail)

1. **`Ctrl+Shift+P`** → **Developer: Reload Window**
2. Retry **`Ctrl+Shift+B`**

### Step 4 — Classic Cursor window (nuclear)

Close Agents-only window. From PowerShell:

```powershell
& "C:\Program Files\cursor\Cursor.exe" --classic -n "c:\Projects\Amazon Systems Design"
```

Classic layout = browser panel works; use agent chat from that window.

---

## Fix (Sir — old steps, if Glass WebView healthy)

### Option A — Open Browser tab (fastest)

1. **`Ctrl+Shift+P`** (Command Palette)
2. Type **`New Browser`** or **`Browser`**
3. Run **`New Browser`** (Glass command: `glass.newBrowser`)

OR menu: **File → New Browser**

### Option B — Switch to Browser layout

1. **`Ctrl+Alt+Tab`** — cycle layouts until **Browser** shows
2. If Windows steals shortcut: **Keyboard Shortcuts** → find **View: Switch Layout** → bind e.g. `Ctrl+Shift+Tab`

### Option C — Editor window (most reliable)

1. **File → Open Editor Window** (`Ctrl+Shift+N`)
2. In that window, open Browser tab from Command Palette

---

## After Sir opens panel

Tell agent: **"browser panel khula, navigate karo"**

Agent will use:

```
browser_navigate(url, position: "side")
```

Seller Central sign-in (correct URL):

```
https://sellercentral.amazon.in/signin?ref_=INscwp_signin_n&mons_sel_locale=en_IN&ld=SCINWPDirect
```

---

## What agent must NOT do

- Open external Chrome (`Start-Process https://...`) when Sir asked for Cursor browser
- Retry navigate 4+ times without Sir opening Browser panel
- Use bare `/ap/signin` (shows "Looking for Something?" 404)

---

## Persistent fix in repo

Project rule: `.cursor/rules/cursor-glass-browser.mdc` (`alwaysApply: true`)

All future agent sessions load this protocol automatically.

---

## Related Cursor forum issues

- Glass browser invisible in Agents window while MCP `locked: true` — known
- `Ctrl+Alt+Tab` layout switch — Windows may conflict; rebind **View: Switch Layout**
- Editor Browser Tab shows "Take Control"; Agents overlay may not — use Editor window if stuck
