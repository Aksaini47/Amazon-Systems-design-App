"""Orchestrate browser CDP invoice batch downloads (helper for save step).

After each CDP batch JSON is written to OUT_DIR/_batch_N.json, run:
    python scripts/save_invoice_batch.py OUT_DIR/_batch_N.json
"""
from __future__ import annotations

import json
from pathlib import Path

OUT_DIR = Path(r"c:\Projects\Amazon Systems Design\data\mahika\amazon-seller-invoices")
MANIFEST = OUT_DIR / "invoice_manifest_2021plus.json"
BATCH_SIZE = 40


def existing_ids() -> list[str]:
    return [p.stem.split("_")[-1] for p in OUT_DIR.glob("*.pdf")]


def batch_plan() -> list[dict]:
    invoices = json.loads(MANIFEST.read_text(encoding="utf-8"))
    total = len(invoices)
    skip = set(existing_ids())
    batches = []
    for start in range(0, total, BATCH_SIZE):
        end = min(start + BATCH_SIZE, total)
        batches.append({"start": start, "count": end - start, "end": end, "total": total})
    return batches, skip, total


if __name__ == "__main__":
    batches, skip, total = batch_plan()
    print(json.dumps({
        "total": total,
        "existing": len(skip),
        "remaining": total - len(skip),
        "batch_size": BATCH_SIZE,
        "batches": batches,
        "skip_ids": sorted(skip),
    }, indent=2))
