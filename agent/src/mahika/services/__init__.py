"""Phase 3 — Evidence Processing services.

Public entry points (per mahika_capture_specs.md §7-§8):

    from mahika.services.pipeline import process_order
    result = process_order("407-1234567-1234567")

Sub-modules:
    ocr            — Tesseract wrapper for FPC code extraction
    diff_detector  — 4-layer SSIM + ORB + Histogram + OCR detector
    verdict        — auto-suggest OK / DAMAGED / DIFFERENT from diff scores
    composite      — 2x2 grid + header + footer renderer (Pillow)
    pipeline       — orchestrator (read evidence → OCR → diff → verdict → composite)

Mahika never auto-applies the suggested verdict — Sir's app collects the final
verdict from the human at capture time. Phase 3 modules only consume + enrich
that decision. See `mahika.md` §9 (forbidden behaviors).
"""
from __future__ import annotations
