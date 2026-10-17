"""Run remaining invoice CDP batches — prints batch payloads for browser fetch."""
from __future__ import annotations

import json
from pathlib import Path

OUT_DIR = Path(r"c:\Projects\Amazon Systems Design\data\mahika\amazon-seller-invoices")
MANIFEST = OUT_DIR / "invoice_manifest_2021plus.json"
BATCH_SIZE = 8


def existing_ids() -> set[str]:
    ids: set[str] = set()
    for p in OUT_DIR.glob("*.pdf"):
        ids.add(p.stem.split("_")[-1])
    return ids


def pending_invoices(from_year: int = 2021) -> list[dict]:
    invoices = json.loads(MANIFEST.read_text(encoding="utf-8"))
    cutoff = f"{from_year}-01-01"
    invoices = [i for i in invoices if i.get("end_date_iso", "") >= cutoff]
    skip = existing_ids()
    return [i for i in invoices if i["invoice_id"] not in skip]


def make_batches(invoices: list[dict]) -> list[list[dict]]:
    return [invoices[i : i + BATCH_SIZE] for i in range(0, len(invoices), BATCH_SIZE)]


if __name__ == "__main__":
    pending = pending_invoices()
    batches = make_batches(pending)
    plan = {
        "pending": len(pending),
        "batch_count": len(batches),
        "batch_size": BATCH_SIZE,
    }
    print(json.dumps(plan, indent=2))
    batch_dir = OUT_DIR / "_cdp_batches"
    batch_dir.mkdir(parents=True, exist_ok=True)
    for i, batch in enumerate(batches):
        (batch_dir / f"pending_{i:03d}.json").write_text(
            json.dumps(batch, ensure_ascii=False), encoding="utf-8"
        )
