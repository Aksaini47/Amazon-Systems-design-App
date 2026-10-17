# Graphify — bulk-listing-create (PHONE_ACCESSORY)

**Tags:** `bulk-upload`, `phone-accessory`, `listing-create`, `seller-central`, `mahika`, `stock-vs-listings`

**Canonical flow:** [FLOW.md](FLOW.md)

**Progress snapshot (counts / gaps):**  
`graphify-out/raw/progress-2026-07-17/PROGRESS_SNAPSHOT.md`

## Key deliverables

| Role | Path |
|------|------|
| Generator | `catalog-builder/amazon-reports/create_bulk_new_listings.py` |
| Images | `fill_phone_accessory_bulk_images.py` + `generated_images/` |
| Upload | `upload_bulk_to_sc.py` |
| Status | `check_bulk_upload_status.py`, `poll_bulk_upload_status.py` |
| Batch | `bulk_create_25_quality.xlsm` · Batch ID `50001020639` |
| Stock match | `stock_vs_listings_match.py` → **84 OK / 16 WRONG_QUALITY / 0 missing** |

## Open gaps

- Amazon listing/status Done for batch 50001020639 (last seen In Progress)
- 16 WRONG_QUALITY listings still to create/fix
- Import Hub Ecom invoices = separate unfinished task (not Badeja folder)

## Regenerate

```powershell
cd "C:\Projects\Amazon Systems Design"
# /graphify --update .
```

Output: repo-root `graphify-out/` (gitignored).
