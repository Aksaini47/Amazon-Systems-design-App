"""Emit Help Hub CDP steps as JSON for Cursor browser (variant 1 short text)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mahika.playwright.support_case_text import get_case_text_variant

v = get_case_text_variant(1)
payload = {
    "help": v.help_with,
    "steps": v.steps_taken,
    "subject": v.subject,
    "phone": "7015436711",
}
print(json.dumps(payload))
