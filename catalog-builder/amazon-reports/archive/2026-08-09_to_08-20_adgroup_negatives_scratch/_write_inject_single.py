"""Write per-chunk JS append scripts (~80KB each)."""
import json
from pathlib import Path

ROOT = Path(__file__).parent
chunks = json.loads((ROOT / "_b64_chunks.json").read_text(encoding="utf-8"))
out_dir = ROOT / "_inject_single"
out_dir.mkdir(exist_ok=True)

(out_dir / "00_init.js").write_text("window.__b64 = '';", encoding="utf-8")
for i, chunk in enumerate(chunks):
    escaped = chunk.replace("\\", "\\\\").replace("'", "\\'")
    (out_dir / f"{i + 1:02d}_append.js").write_text(
        f"window.__b64 += '{escaped}';", encoding="utf-8"
    )

final = """
(async () => {
  const find = (root) => {
    for (const el of root.querySelectorAll('input[type=file], #kat-file-attachment')) return el;
    for (const el of root.querySelectorAll('*'))
      if (el.shadowRoot) { const f = find(el.shadowRoot); if (f) return f; }
    return null;
  };
  const input = find(document);
  if (!input) return { ok: false, err: 'no input' };
  const bin = atob(window.__b64 || '');
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  const blob = new Blob([bytes], { type: 'application/vnd.ms-excel.sheet.macroEnabled.12' });
  const file = new File([blob], 'PHONE_ACCESSORY (4).xlsm', { type: blob.type });
  const dt = new DataTransfer();
  dt.items.add(file);
  input.files = dt.files;
  input.dispatchEvent(new Event('change', { bubbles: true }));
  input.dispatchEvent(new Event('input', { bubbles: true }));
  return { ok: true, size: blob.size, files: input.files.length, name: input.files[0]?.name };
})()
""".strip()
(out_dir / "99_finalize.js").write_text(final, encoding="utf-8")
print(f"{len(chunks)} append scripts")
