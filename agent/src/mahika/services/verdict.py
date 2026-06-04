"""Auto-verdict suggestion engine.

Implements `mahika_capture_specs.md §8.3` rules:

    High match  (SSIM >0.95, FPC match)              → OK
    Medium      (SSIM 0.85–0.95)                     → DAMAGED
    Low         (SSIM <0.85 or FPC mismatch)         → DIFFERENT

The FPC mismatch is the KILLER signal (per spec §8.2 layer 4). When the OCR
extracts FPC codes from BOTH back-of-product photos AND they differ, we override
the SSIM-based suggestion and report DIFFERENT regardless of similarity score.

This module produces decision SUPPORT — Sir's app already collected the human
verdict at capture time. Mahika never silently overrides a human verdict.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from mahika.services.diff_detector import DiffScores


class Verdict(str, Enum):  # noqa: UP042
    """Outcome categories — match the values stored in Postgres `evidence.verdict`.

    Inherits from (str, Enum) rather than enum.StrEnum (Py3.11+) so this enum
    can be JSON-serialised + Postgres-cast identically across the codebase
    without per-call .value lookups. The behaviour is equivalent for our use.
    """

    OK = "OK"
    DAMAGED = "DAMAGED"
    DIFFERENT = "DIFFERENT"
    DAMAGED_AND_DIFFERENT = "DAMAGED_AND_DIFFERENT"
    UNKNOWN = "UNKNOWN"


# ─── Threshold knobs (spec §8.3) ─────────────────────────────────────────
SSIM_OK_THRESHOLD = 0.95
SSIM_DIFFERENT_THRESHOLD = 0.85

# Sanity floors for secondary layers — used for confidence assessment, not gating.
ORB_RATIO_OK_FLOOR = 0.30
HISTOGRAM_OK_FLOOR = 0.85


@dataclass(frozen=True)
class VerdictSuggestion:
    """Output of `suggest_verdict()`.

    Attributes
    ----------
    verdict:    Enum value to surface to Sir.
    confidence: 0.0–1.0. How sure are we? Combines all 4 layer signals.
    reasoning:  Bullet list of human-readable explanations. Used in the
                composite footer block + audit log.
    """

    verdict: Verdict
    confidence: float
    reasoning: list[str]


def suggest_verdict(scores: DiffScores) -> VerdictSuggestion:
    """Apply spec §8.3 rules + FPC override.

    The function is pure — same DiffScores → same VerdictSuggestion every time.
    """
    reasoning: list[str] = []

    mean_ssim = scores.mean_ssim
    fpc_match = scores.fpc_match  # True / False / None
    orb_ratio = scores.mean_orb_match_ratio
    hist_corr = scores.mean_histogram_corr

    reasoning.append(
        f"SSIM front={scores.front.ssim:.3f}, back={scores.back.ssim:.3f} (mean {mean_ssim:.3f})"
    )
    reasoning.append(
        f"ORB match ratio front={scores.front.orb_match_ratio:.3f}, "
        f"back={scores.back.orb_match_ratio:.3f} (mean {orb_ratio:.3f})"
    )
    reasoning.append(
        f"Histogram correlation front={scores.front.histogram_corr:.3f}, "
        f"back={scores.back.histogram_corr:.3f} (mean {hist_corr:.3f})"
    )
    if scores.pk_ocr.available and scores.rt_ocr.available:
        pk_fpc = scores.pk_ocr.fpc_code or "(not detected)"
        rt_fpc = scores.rt_ocr.fpc_code or "(not detected)"
        reasoning.append(f"FPC sent={pk_fpc} | FPC received={rt_fpc}")
        if fpc_match is True:
            reasoning.append("→ FPC codes MATCH")
        elif fpc_match is False:
            reasoning.append("→ FPC codes DIFFER (killer signal)")
        else:
            reasoning.append("→ FPC comparison inconclusive (OCR partial)")
    else:
        reasoning.append("FPC OCR layer unavailable (Tesseract not installed)")

    # ─── Decision tree ────────────────────────────────────────────────
    # Rule 1: FPC mismatch is conclusive → DIFFERENT regardless of SSIM
    if fpc_match is False:
        reasoning.insert(
            0,
            "VERDICT: DIFFERENT — back-of-product FPC codes are different "
            "between sent and received. This is near-definitive proof of swap.",
        )
        return VerdictSuggestion(
            verdict=Verdict.DIFFERENT,
            confidence=_blend_confidence(mean_ssim, orb_ratio, hist_corr, fpc_signal=-1.0),
            reasoning=reasoning,
        )

    # Rule 2: SSIM-based primary rule (spec §8.3)
    if mean_ssim >= SSIM_OK_THRESHOLD and fpc_match is not False:
        reasoning.insert(
            0,
            f"VERDICT: OK — SSIM {mean_ssim:.3f} ≥ {SSIM_OK_THRESHOLD} "
            f"and FPC {'matches' if fpc_match is True else 'inconclusive'}.",
        )
        return VerdictSuggestion(
            verdict=Verdict.OK,
            confidence=_blend_confidence(mean_ssim, orb_ratio, hist_corr, fpc_signal=1.0 if fpc_match else 0.0),
            reasoning=reasoning,
        )

    if mean_ssim < SSIM_DIFFERENT_THRESHOLD:
        reasoning.insert(
            0,
            f"VERDICT: DIFFERENT — SSIM {mean_ssim:.3f} < {SSIM_DIFFERENT_THRESHOLD}; "
            "received item appears materially distinct from sent.",
        )
        return VerdictSuggestion(
            verdict=Verdict.DIFFERENT,
            confidence=_blend_confidence(mean_ssim, orb_ratio, hist_corr, fpc_signal=0.0),
            reasoning=reasoning,
        )

    # Default: medium SSIM (0.85–0.95) → DAMAGED
    reasoning.insert(
        0,
        f"VERDICT: DAMAGED — SSIM {mean_ssim:.3f} in damaged band "
        f"({SSIM_DIFFERENT_THRESHOLD}–{SSIM_OK_THRESHOLD}); "
        "same product appears physically altered (scuffs, scratches, cracks).",
    )
    return VerdictSuggestion(
        verdict=Verdict.DAMAGED,
        confidence=_blend_confidence(mean_ssim, orb_ratio, hist_corr, fpc_signal=0.0),
        reasoning=reasoning,
    )


def _blend_confidence(
    ssim: float, orb_ratio: float, hist_corr: float, fpc_signal: float
) -> float:
    """Combine four signals into a 0.0–1.0 confidence value.

    Weights chosen so that:
    - SSIM is the dominant gating signal (50%)
    - ORB + histogram together corroborate (35%)
    - FPC signal sharpens (±15%)
    """
    # Normalise histogram_corr from [-1,1] → [0,1]
    hist_norm = max(0.0, (hist_corr + 1.0) / 2.0)
    orb_norm = min(1.0, max(0.0, orb_ratio))
    ssim_norm = min(1.0, max(0.0, ssim))

    base = 0.50 * ssim_norm + 0.20 * orb_norm + 0.15 * hist_norm
    # fpc_signal ∈ {-1.0, 0.0, +1.0} — scale ±0.15
    fpc_term = max(-0.15, min(0.15, 0.15 * fpc_signal))
    return max(0.0, min(1.0, base + fpc_term + 0.15))  # +0.15 base since we always have some signal
