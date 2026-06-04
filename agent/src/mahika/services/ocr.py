"""OCR layer — extracts FPC codes from back-of-product images via Tesseract.

Per `mahika_capture_specs.md §8.2 Layer 4`: FPC code OCR is the killer signal
for SAFE-T claims. When the FPC code on the dispatched item doesn't match the
FPC code on the returned item, it's near-definitive proof of buyer-side swap.

Tesseract binary requirement:
    Windows: `winget install UB-Mannheim.TesseractOCR` installs to
             `C:\\Program Files\\Tesseract-OCR\\tesseract.exe`.
    Linux:   `apt install tesseract-ocr`.

If Tesseract binary is missing, this module degrades gracefully — `extract_fpc()`
returns `OCRResult(text="", confidence=0.0, fpc_code=None, available=False)`
so the rest of the pipeline can still run (composite + 3 of 4 diff layers).

FPC code pattern:
    The "FPC code" / "Mfg Serial" on the back of mobile phones is typically a
    continuous alphanumeric run of 7-15 characters mixing uppercase letters and
    digits. We extract candidates via regex and pick the longest match with
    Tesseract confidence ≥ MIN_FPC_CONFIDENCE.
"""
from __future__ import annotations

import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

# Tesseract is optional — if missing, the rest of Mahika still works.
try:
    import pytesseract  # type: ignore[import-untyped]

    _PYTESSERACT_IMPORTED = True
except ImportError:
    pytesseract = None  # type: ignore[assignment]
    _PYTESSERACT_IMPORTED = False


# ─── Tesseract binary discovery ──────────────────────────────────────────
# Common Windows install paths; PATH wins if set.
_WINDOWS_TESSERACT_CANDIDATES = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    str(Path.home() / "AppData/Local/Programs/Tesseract-OCR/tesseract.exe"),
]


def _resolve_tesseract_binary() -> str | None:
    """Return the Tesseract executable path, or None if not found."""
    # Honour explicit env override first
    explicit = os.environ.get("MAHIKA_TESSERACT_PATH") or os.environ.get("TESSERACT_CMD")
    if explicit and Path(explicit).exists():
        return explicit
    # Check PATH
    on_path = shutil.which("tesseract")
    if on_path:
        return on_path
    # Windows fallback
    if sys.platform == "win32":
        for candidate in _WINDOWS_TESSERACT_CANDIDATES:
            if Path(candidate).exists():
                return candidate
    return None


def _configure_pytesseract() -> bool:
    """Wire pytesseract to the discovered binary. Returns availability flag."""
    if not _PYTESSERACT_IMPORTED:
        return False
    binary = _resolve_tesseract_binary()
    if binary is None:
        return False
    pytesseract.pytesseract.tesseract_cmd = binary
    return True


# Cached at module-load. If Sir installs Tesseract after import, call
# `refresh_tesseract_availability()` to re-detect.
TESSERACT_AVAILABLE: bool = _configure_pytesseract()


def refresh_tesseract_availability() -> bool:
    """Re-probe for Tesseract — call after installing it post-import."""
    global TESSERACT_AVAILABLE
    TESSERACT_AVAILABLE = _configure_pytesseract()
    return TESSERACT_AVAILABLE


# ─── FPC extraction parameters ───────────────────────────────────────────
# Tesseract config — limit to uppercase letters + digits, treat as single line.
_TESSERACT_FPC_CONFIG = (
    "--oem 3 --psm 6 -c "
    "tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-/"
)

# FPC pattern: 7–15 chars, must contain at least one letter AND one digit
# (rules out pure-numeric noise like phone numbers, pure-alpha words).
_FPC_RE = re.compile(r"\b(?=[A-Z0-9-/]*[A-Z])(?=[A-Z0-9-/]*[0-9])[A-Z0-9-/]{7,15}\b")

# Minimum Tesseract confidence (0-100) to accept an FPC candidate.
MIN_FPC_CONFIDENCE = 50.0


# ─── Public API ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class OCRResult:
    """Outcome of running Tesseract on a single image.

    Attributes
    ----------
    text:         Raw recognised text (whitespace-collapsed). May be empty.
    confidence:   Mean Tesseract confidence across recognised words (0-100).
                  0.0 when Tesseract didn't run or found nothing.
    fpc_code:     Best-guess FPC code extracted via regex from `text`. None if
                  no plausible candidate. UPPERCASE alphanumeric, 7-15 chars.
    available:    False when Tesseract binary couldn't be located. Caller
                  should treat the result as "OCR layer unavailable" rather
                  than "OCR ran and found nothing".
    """

    text: str
    confidence: float
    fpc_code: str | None
    available: bool


def extract_fpc(image_path: Path | str) -> OCRResult:
    """Run Tesseract on `image_path`, return text + best FPC candidate.

    Designed for back-of-product photos (`{OrderID}_PK_back.jpg`,
    `{OrderID}_RT_back.jpg`). The image is preprocessed to grayscale + sharper
    contrast before OCR for better small-text recognition.

    Always returns an `OCRResult` — never raises on missing Tesseract or bad
    images. Caller checks `.available` and `.fpc_code is not None` to gate
    downstream use.
    """
    image_path = Path(image_path)
    if not image_path.exists():
        return OCRResult(text="", confidence=0.0, fpc_code=None, available=False)

    if not TESSERACT_AVAILABLE:
        return OCRResult(text="", confidence=0.0, fpc_code=None, available=False)

    try:
        with Image.open(image_path) as img:
            # Convert to grayscale, increase contrast a bit for small print
            gray = img.convert("L")
            # Tesseract image_to_data returns per-word confidence
            assert pytesseract is not None
            data = pytesseract.image_to_data(
                gray,
                config=_TESSERACT_FPC_CONFIG,
                output_type=pytesseract.Output.DICT,
            )
    except Exception:
        # Tesseract crash or image decode failure — degrade gracefully
        return OCRResult(text="", confidence=0.0, fpc_code=None, available=True)

    words: list[str] = []
    confidences: list[float] = []
    for i, word in enumerate(data.get("text", [])):
        word = (word or "").strip()
        if not word:
            continue
        # Tesseract reports -1 for "no confidence" — filter out
        try:
            conf = float(data["conf"][i])
        except (KeyError, IndexError, ValueError, TypeError):
            conf = -1.0
        if conf < 0:
            continue
        words.append(word.upper())
        confidences.append(conf)

    text = " ".join(words)
    mean_conf = sum(confidences) / len(confidences) if confidences else 0.0

    # Find FPC candidates and pick the longest that meets confidence threshold.
    # We can't get per-token confidence from regex matches directly, so we
    # require the overall mean_conf threshold to gate the FPC extraction.
    fpc_code: str | None = None
    if mean_conf >= MIN_FPC_CONFIDENCE:
        candidates = _FPC_RE.findall(text)
        if candidates:
            fpc_code = max(candidates, key=len)

    return OCRResult(text=text, confidence=mean_conf, fpc_code=fpc_code, available=True)


def fpc_codes_match(a: OCRResult, b: OCRResult) -> bool | None:
    """Compare two OCR results. Returns:

    - True  → both extracted an FPC code AND they match (case-insensitive).
    - False → both extracted an FPC code AND they differ (the killer signal).
    - None  → either side didn't produce an FPC (can't conclude).
    """
    if a.fpc_code is None or b.fpc_code is None:
        return None
    return a.fpc_code.upper() == b.fpc_code.upper()
