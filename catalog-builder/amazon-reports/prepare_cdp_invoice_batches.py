"""Orchestrate CDP parallel invoice downloads via Glass browser session."""
from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path

OUT_DIR = Path(r"c:\Projects\Amazon Systems Design\data\mahika\amazon-seller-invoices")
MANIFEST = OUT_DIR / "invoice_manifest_2021plus.json"
BATCH_JS_FILE = OUT_DIR / "_cdp_batch_fetch.js"
RESULTS_DIR = OUT_DIR / "_cdp_batches"


def _slug_type(invoice_type: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", invoice_type.strip())
    return re.sub(r"_+", "_", slug).strip("_")


def _existing_for_invoice(invoice_id: str) -> Path | None:
    matches = list(OUT_DIR.glob(f"*_{invoice_id}.pdf"))
    return matches[0] if matches else None


BATCH_FETCH_JS = r"""
async (invoices) => {
  const enc = (s) => encodeURIComponent(s);
  const fetchOne = async (inv) => {
    const payload = {
      fileType: enc(inv.file_type),
      vatInvoiceNumber: enc(inv.invoice_id),
      endDate: enc(inv.end_date),
      payeeRegistrationNumber: enc(inv.payee_registration),
      filterName: enc(inv.filter_name),
    };
    const rar = (inv.rar_id || '').trim();
    const shed = (inv.shed_document_name || '').trim();
    if (rar && shed && rar !== 'null' && shed !== 'null') {
      payload.rarId = enc(rar);
      payload.shedDocumentName = enc(shed);
    } else {
      payload.documentVersionId = enc(inv.document_version_id);
    }
    try {
      const execResp = await fetch('/tax/view-seller-fee-invoice-execute', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        credentials: 'include',
        body: JSON.stringify(payload),
      });
      if (!execResp.ok) {
        return { invoice_id: inv.invoice_id, ok: false, status: execResp.status, url: execResp.url, error: await execResp.text().catch(()=>'') };
      }
      if (execResp.url.includes('/ap/signin')) {
        return { invoice_id: inv.invoice_id, ok: false, session_expired: true, url: execResp.url };
      }
      const data = await execResp.json();
      const pdfResp = await fetch(data.url, { credentials: 'include' });
      if (!pdfResp.ok) {
        return { invoice_id: inv.invoice_id, ok: false, status: pdfResp.status, url: pdfResp.url, error: 'pdf fetch failed' };
      }
      const buf = await pdfResp.arrayBuffer();
      const bytes = new Uint8Array(buf);
      let binary = '';
      const chunk = 0x8000;
      for (let i = 0; i < bytes.length; i += chunk) {
        binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
      }
      return { invoice_id: inv.invoice_id, ok: true, b64: btoa(binary), size: bytes.length };
    } catch (e) {
      return { invoice_id: inv.invoice_id, ok: false, error: String(e) };
    }
  };
  return Promise.all(invoices.map(fetchOne));
}
"""


def prepare_batches(workers: int = 8, from_year: int = 2021) -> dict:
    invoices = json.loads(MANIFEST.read_text(encoding="utf-8"))
    cutoff = f"{from_year}-01-01"
    invoices = [i for i in invoices if i.get("end_date_iso", "") >= cutoff]

    pending = []
    skipped = []
    for inv in invoices:
        existing = _existing_for_invoice(inv["invoice_id"])
        if existing:
            skipped.append({
                "invoice_id": inv["invoice_id"],
                "skipped": True,
                "path": str(existing),
            })
        else:
            pending.append(inv)

    batches = [pending[i : i + workers] for i in range(0, len(pending), workers)]
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    BATCH_JS_FILE.write_text(BATCH_FETCH_JS, encoding="utf-8")

    meta = {
        "created_at": datetime.now(UTC).isoformat(),
        "total": len(invoices),
        "pending": len(pending),
        "skipped_upfront": len(skipped),
        "batch_count": len(batches),
        "workers": workers,
        "skipped": skipped,
        "batches": [
            {"index": i, "file": str(RESULTS_DIR / f"batch_{i:03d}_input.json"), "count": len(b)}
            for i, b in enumerate(batches)
        ],
    }
    meta_path = OUT_DIR / "_cdp_download_plan.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    for i, batch in enumerate(batches):
        (RESULTS_DIR / f"batch_{i:03d}_input.json").write_text(
            json.dumps(batch, ensure_ascii=False), encoding="utf-8"
        )

    return meta


if __name__ == "__main__":
    meta = prepare_batches(workers=8, from_year=2021)
    print(json.dumps({k: meta[k] for k in ("total", "pending", "skipped_upfront", "batch_count", "workers")}, indent=2))
