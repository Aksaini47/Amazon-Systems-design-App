"""Execute Glass CDP chunked plan steps via stdin/stdout helper for agent MCP calls.

Prints each step as JSON line; agent runs browser_cdp then passes fetch response to save.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

OUT_DIR = Path(r"c:\Projects\Amazon Systems Design\data\mahika\amazon-seller-invoices")
SCRIPT_DIR = Path(__file__).resolve().parent


def load_plan(num: int) -> dict:
    path = OUT_DIR / f"_cdp_chunked_super_{num:03d}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def save_response(num: int, value: list) -> dict:
    resp_path = OUT_DIR / f"_cdp_super_{num:03d}_response.json"
    resp_path.write_text(
        json.dumps({"result": {"value": value}}, ensure_ascii=False),
        encoding="utf-8",
    )
    subprocess.check_call([
        sys.executable,
        str(SCRIPT_DIR / "save_superbatch_response.py"),
        str(resp_path),
    ])
    (OUT_DIR / f"_cdp_super_{num:03d}_done.marker").write_text(
        datetime.now(UTC).isoformat(), encoding="utf-8",
    )
    return {
        "downloaded": sum(1 for x in value if x.get("ok")),
        "failed": sum(1 for x in value if not x.get("ok")),
        "errors": [x for x in value if not x.get("ok")][:5],
    }


def store_batch_expr(num: int) -> str:
    """Single CDP expression to load entire superbatch into sessionStorage."""
    batch = json.loads(
        (OUT_DIR / "_cdp_superbatches" / f"super_{num:03d}.json").read_text(encoding="utf-8")
    )
    batch_json = json.dumps(batch, ensure_ascii=False)
    return (
        f"sessionStorage.setItem('__inv_batch__', {json.dumps(batch_json)}); "
        f"JSON.parse(sessionStorage.getItem('__inv_batch__')).length"
    )


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
    parser.add_argument("--print-store", action="store_true")
    parser.add_argument("--print-fetch", action="store_true")
    parser.add_argument("--save-response", type=Path)
    args = parser.parse_args()

    if args.print_store:
        print(store_batch_expr(args.num))
        return

    if args.print_fetch:
        print(FETCH_EXPR.strip())
        return

    if args.save_response:
        data = json.loads(args.save_response.read_text(encoding="utf-8"))
        value = data.get("result", {}).get("value", data)
        stats = save_response(args.num, value)
        print(json.dumps(stats, indent=2))
        return

    raise SystemExit("Use --print-store, --print-fetch, or --save-response")


if __name__ == "__main__":
    main()
