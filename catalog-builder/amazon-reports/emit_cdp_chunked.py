"""Chunked CDP store — 8 invoices per small sessionStorage append call."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT_OUT = Path(r"c:\Projects\Amazon Systems Design\data\mahika\amazon-seller-invoices")
CHUNK = 8

FETCH_EXPR = r"""
(async () => {
  const invoices = JSON.parse(sessionStorage.getItem('__inv_batch__'));
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
})()
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("num", type=int)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    out_dir = args.out_dir
    super_dir = out_dir / "_cdp_superbatches"
    invoices = json.loads((super_dir / f"super_{args.num:03d}.json").read_text(encoding="utf-8"))
    chunks = [invoices[i : i + CHUNK] for i in range(0, len(invoices), CHUNK)]
    steps = [{"method": "Runtime.evaluate", "params": {"expression": "sessionStorage.setItem('__inv_batch__','[]'); 'reset'", "returnByValue": True}}]
    for i, chunk in enumerate(chunks):
        chunk_json = json.dumps(chunk, ensure_ascii=False)
        expr = (
            "(() => { const cur = JSON.parse(sessionStorage.getItem('__inv_batch__') || '[]'); "
            f"const chunk = {chunk_json}; "
            "sessionStorage.setItem('__inv_batch__', JSON.stringify(cur.concat(chunk))); "
            "return cur.length + chunk.length; })()"
        )
        steps.append({"method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True}})
    steps.append({
        "method": "Runtime.evaluate",
        "params": {"awaitPromise": True, "expression": FETCH_EXPR, "returnByValue": True},
    })
    out = {"viewId": "glass-browser-71d0f2d2-60a2-44dc-a206-daf7d1f4dd8a", "steps": steps, "count": len(invoices)}
    path = out_dir / f"_cdp_chunked_super_{args.num:03d}.json"
    path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(path, len(steps), "steps")


if __name__ == "__main__":
    main()
