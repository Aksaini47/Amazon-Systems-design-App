"""Build super-batches (40 invoices) for CDP parallel fetch."""
from __future__ import annotations

import json
from pathlib import Path

OUT_DIR = Path(r"c:\Projects\Amazon Systems Design\data\mahika\amazon-seller-invoices")
MANIFEST = OUT_DIR / "invoice_manifest_2021plus.json"
SUPER_DIR = OUT_DIR / "_cdp_superbatches"
SUPER_SIZE = 40


def existing_ids() -> set[str]:
    return {p.stem.split("_")[-1] for p in OUT_DIR.glob("*.pdf")}


def main() -> None:
    invoices = json.loads(MANIFEST.read_text(encoding="utf-8"))
    invoices = [i for i in invoices if i.get("end_date_iso", "") >= "2021-01-01"]
    skip = existing_ids()
    pending = [i for i in invoices if i["invoice_id"] not in skip]
    SUPER_DIR.mkdir(parents=True, exist_ok=True)
    batches = [pending[i : i + SUPER_SIZE] for i in range(0, len(pending), SUPER_SIZE)]
    for n, batch in enumerate(batches):
        (SUPER_DIR / f"super_{n:03d}.json").write_text(
            json.dumps(batch, ensure_ascii=False), encoding="utf-8"
        )
    print(json.dumps({
        "pending": len(pending),
        "superbatch_count": len(batches),
        "super_size": SUPER_SIZE,
    }, indent=2))


if __name__ == "__main__":
    main()
