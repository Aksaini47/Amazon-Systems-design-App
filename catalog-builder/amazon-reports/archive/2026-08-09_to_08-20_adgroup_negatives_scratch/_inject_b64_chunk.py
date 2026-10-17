"""Print one base64 chunk escaped for JS (stdin: chunk index)."""
import json
import sys
from pathlib import Path

CHUNKS = json.loads(
    Path(__file__).with_name("_b64_chunks.json").read_text(encoding="utf-8")
)
idx = int(sys.argv[1])
chunk = CHUNKS[idx].replace("\\", "\\\\").replace("'", "\\'")
print(chunk)
