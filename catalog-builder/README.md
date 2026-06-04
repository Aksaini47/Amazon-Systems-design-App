# Amazon Catalogue & Store Builder

Local-first web app for managing **Amazon India** listings of generic, non-branded **mobile screen / phone replacement parts**. Built for the Tier 2-4 repair-technician audience with no Brand Registry.

## What it does

Six modules, each independently usable:

1. **SKU Catalog** — mobile-screen-aware schema (brand, model, model numbers, screen type, quality grade, frame status, compatibility list), CSV import/export, clone-to-variant.
2. **Listing Copy Studio** — title + 5 bullets + plain-text description + backend keywords, all enforcing 2026 Amazon India rules live (200-char title, 255-char/bullet with 1000-byte indexing cliff, 200-byte India backend, no emojis / ALL CAPS / promo words / refund guarantees). Hinglish keyword suggester. Amazon mobile preview.
3. **Carousel Designer** ⭐ — Konva canvas, 9 slots at 2000×2000 RGB JPG, 7 pre-built infographic templates (compatibility chart, quality comparison, specs grid, feature callouts, box contents, install steps, trust strip). Pure `#FFFFFF` enforcer on slot 1. 24px-min text on overlays. **This is the "fake A+" canvas for non-branded sellers.**
4. **HTML Page Builder** — drag-drop modules → self-contained interactive HTML file for **off-Amazon use only** (own site, Shopify, WhatsApp catalog).
5. **Bulk Operations** — apply one template to N SKUs, Amazon India Flat File CSV generator.
6. **Export Center** — per-SKU ZIP bundle (9 images + 4 text files + landing HTML + upload checklist), bulk ZIP-of-ZIPs, JSON project backup.

## Stack

Vite + React 18 + TypeScript + Tailwind CSS v4 + Zustand + Dexie (IndexedDB) + konva.js + dnd-kit + papaparse + JSZip + pica + react-easy-crop + lucide-react.

No backend. No auth. No SP-API. Local-only data (IndexedDB) — use Dashboard "Backup project" before machine changes.

## Setup

```bash
npm install
npm run dev      # opens http://localhost:5173
npm run build    # type-check + production build
```

## Critical Amazon India rules baked in

- Title 200 chars, mobile preview shows first 80
- 5 bullets × 255 char hard cap, **1000-byte combined indexing limit** (anything past is shown but not searchable)
- Description: 2000 chars plain text (HTML banned since July 2021)
- Backend keywords: **200 bytes (India)** — 1 byte over silently de-indexes ALL backend
- Main image: pure `#FFFFFF`, 85% frame fill, no text/watermarks, ≥1600×1600
- 9 image slots total (main + 8 alts)
- No emojis, ALL CAPS, promotional words ("best", "#1"), refund guarantees, brand stories — Amazon's AI auto-removes since August 2024

## Why no A+ Content / Brand Store?

User has no Amazon Brand Registry (no registered trademark). The 9-image carousel is the proven workaround: same information density as A+ Content, mobile-readable, fully under the seller's control.
