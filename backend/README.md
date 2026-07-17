# backend — DORMANT

> **Status: DORMANT since May 2026.** The RF Logger app went local-only in
> 2.0.0 patch 8 (commit `ea343c1`) and deleted its sync client — nothing
> calls this server anymore. Its only consumer was `dashboard/`, itself
> dormant. Kept as reference for the SP-API service code
> (`src/services/spapi.js`); do not build new features here.

Node/Express + SQLite server that used to receive order media uploads from
the phone over WiFi and expose orders/returns/FBA routes to the dashboard.

Reviving it would require: recreating the app-side sync layer (deleted in
`ea343c1`), refreshing the SP-API refresh token env vars, and re-checking
`src/services/spapi.js` endpoint config (sandbox vs production).
