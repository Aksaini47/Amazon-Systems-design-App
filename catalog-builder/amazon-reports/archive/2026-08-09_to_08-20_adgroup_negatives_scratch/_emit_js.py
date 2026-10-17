"""Emit CDP Runtime.evaluate expression from inject group JS file."""
import json
import sys
from pathlib import Path

js = Path(sys.argv[1]).read_text(encoding="utf-8")
print(json.dumps(js))
