"""Generate CDP evaluate expression for a superbatch (for Glass browser MCP)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

OUT_DIR = Path(r"c:\Projects\Amazon Systems Design\data\mahika\amazon-seller-invoices")
SUPER_DIR = OUT_DIR / "_cdp_superbatches"

JS = r"""
async (invoices) => {
  const enc = (s) => encodeURIComponent(s);
  const fetchOne = async (inv) => {
    const payload = {
      fileType: enc(inv.file_type), vatInvoiceNumber: enc(inv.invoice_id),
      endDate: enc(inv.end_date), payeeRegistrationNumber: enc(inv.payee_registration),
      filterName: enc(inv.filter_name),
    };
    const rar = (inv.rar_id || '').trim(); const shed = (inv.shed_document_name || '').trim();
    if (rar && shed && rar !== 'null' && shed !== 'null') {
      payload.rarId = enc(rar); payload.shedDocumentName = enc(shed);
    } else { payload.documentVersionId = enc(inv.document_version_id); }
    try {
      const execResp = await fetch('/tax/view-seller-fee-invoice-execute', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        credentials: 'include', body: JSON.stringify(payload),
      });
      if (!execResp.ok || execResp.url.includes('/ap/signin')) {
        return { invoice_id: inv.invoice_id, ok: false, error: execResp.url || String(execResp.status) };
      }
      const data = await execResp.json();
      const pdfResp = await fetch(data.url, { credentials: 'include' });
      if (!pdfResp.ok) return { invoice_id: inv.invoice_id, ok: false, error: 'pdf ' + pdfResp.status };
      const buf = await pdfResp.arrayBuffer(); const bytes = new Uint8Array(buf);
      let binary = '';
      for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
      return { invoice_id: inv.invoice_id, ok: true, b64: btoa(binary), size: bytes.length };
    } catch (e) { return { invoice_id: inv.invoice_id, ok: false, error: String(e) }; }
  };
  const limit = 8; const out = [];
  for (let i = 0; i < invoices.length; i += limit) {
    out.push(...await Promise.all(invoices.slice(i, i + limit).map(fetchOne)));
  }
  return out;
}
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("num", type=int)
    args = parser.parse_args()
    invoices = json.loads((SUPER_DIR / f"super_{args.num:03d}.json").read_text(encoding="utf-8"))
    payload = {
        "method": "Runtime.evaluate",
        "params": {
            "awaitPromise": True,
            "expression": f"({JS.strip()})({json.dumps(invoices, ensure_ascii=False)})",
            "returnByValue": True,
        },
        "viewId": "glass-browser-71d0f2d2-60a2-44dc-a206-daf7d1f4dd8a",
    }
    out = OUT_DIR / f"_cdp_super_{args.num:03d}_request.json"
    out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {out} ({len(invoices)} invoices, {out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
