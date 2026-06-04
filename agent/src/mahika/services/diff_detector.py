"""4-layer image difference detector for SAFE-T evidence.

Per `mahika_capture_specs.md §8.2`, we run four independent comparisons between
the PK (dispatched) photos and the RT (returned) photos:

    Layer 1 — SSIM (Structural Similarity Index)
    Layer 2 — ORB feature matching
    Layer 3 — Color histogram comparison
    Layer 4 — OCR on FPC code / Mfg serial (handled by services.ocr)

The combined `DiffScores` object is consumed by `services.verdict` to produce
an auto-suggested verdict. Sir's app has already collected a human verdict at
capture time — Mahika's suggestion is decision support, not autonomous.

Image preparation:
    Each pair is resized to a common 512×512 working canvas before comparison.
    Source images are 2K (~2000×2500) — the downscale is necessary to make ORB
    and histogram comparisons tractable, and SSIM is well-behaved at 512px.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim_func

from mahika.services.ocr import OCRResult, extract_fpc, fpc_codes_match

# ─── Tunable thresholds (per spec §8.3) ──────────────────────────────────
# These are the defaults — the verdict module is the SINGLE place where these
# thresholds are interpreted. Detector itself just emits raw scores.
WORK_SIZE = 512  # pixels — common downscale canvas for both images
ORB_MAX_FEATURES = 1000


# ─── Public dataclasses ──────────────────────────────────────────────────


@dataclass(frozen=True)
class PairScores:
    """Diff scores for a single PK/RT image pair (front-vs-front, back-vs-back)."""

    ssim: float
    """Structural Similarity Index, 0.0 (different) → 1.0 (identical)."""

    orb_match_ratio: float
    """Good-match keypoints / max(features in either image). 0.0–1.0."""

    histogram_corr: float
    """Histogram correlation (cv2.HISTCMP_CORREL). -1.0–1.0. Higher = more similar."""


@dataclass(frozen=True)
class DiffScores:
    """Combined diff scores for an entire order (front pair + back pair + OCR)."""

    front: PairScores
    """Scores for PK_front vs RT_front."""

    back: PairScores
    """Scores for PK_back vs RT_back."""

    pk_ocr: OCRResult
    """OCR result on PK_back (sent product's FPC code)."""

    rt_ocr: OCRResult
    """OCR result on RT_back (returned product's FPC code)."""

    @property
    def fpc_match(self) -> bool | None:
        """True if FPC codes match, False if they differ, None if either OCR failed."""
        return fpc_codes_match(self.pk_ocr, self.rt_ocr)

    @property
    def mean_ssim(self) -> float:
        """Average of front + back SSIM — primary single-number signal."""
        return (self.front.ssim + self.back.ssim) / 2.0

    @property
    def mean_orb_match_ratio(self) -> float:
        return (self.front.orb_match_ratio + self.back.orb_match_ratio) / 2.0

    @property
    def mean_histogram_corr(self) -> float:
        return (self.front.histogram_corr + self.back.histogram_corr) / 2.0


# ─── Image loading + preprocessing ───────────────────────────────────────


def _load_and_resize(path: Path) -> np.ndarray:
    """Load an image as BGR and resize to WORK_SIZE × WORK_SIZE."""
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Could not read image: {path}")
    return cv2.resize(img, (WORK_SIZE, WORK_SIZE), interpolation=cv2.INTER_AREA)


# ─── Layer 1 — SSIM ──────────────────────────────────────────────────────


def _ssim(a_bgr: np.ndarray, b_bgr: np.ndarray) -> float:
    """Compute SSIM on grayscale versions of both images."""
    a_gray = cv2.cvtColor(a_bgr, cv2.COLOR_BGR2GRAY)
    b_gray = cv2.cvtColor(b_bgr, cv2.COLOR_BGR2GRAY)
    score, _ = ssim_func(a_gray, b_gray, full=True)
    return float(score)


# ─── Layer 2 — ORB feature matching ──────────────────────────────────────


def _orb_match_ratio(a_bgr: np.ndarray, b_bgr: np.ndarray) -> float:
    """ORB keypoint matching with ratio test.

    Returns the fraction of good matches relative to the smaller keypoint set.
    Range 0.0 (totally different) → ~1.0 (same image). Real "same product"
    photos taken minutes apart typically score 0.4–0.7 due to lighting/pose
    variation; "different product" scores typically <0.15.
    """
    a_gray = cv2.cvtColor(a_bgr, cv2.COLOR_BGR2GRAY)
    b_gray = cv2.cvtColor(b_bgr, cv2.COLOR_BGR2GRAY)

    orb = cv2.ORB_create(nfeatures=ORB_MAX_FEATURES)
    kp_a, desc_a = orb.detectAndCompute(a_gray, None)
    kp_b, desc_b = orb.detectAndCompute(b_gray, None)

    if desc_a is None or desc_b is None or len(kp_a) < 10 or len(kp_b) < 10:
        return 0.0

    # KNN match + Lowe's ratio test
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    try:
        knn = bf.knnMatch(desc_a, desc_b, k=2)
    except cv2.error:
        return 0.0

    good = [m for pair in knn if len(pair) == 2 for m, n in [pair] if m.distance < 0.75 * n.distance]
    denom = min(len(kp_a), len(kp_b))
    return len(good) / denom if denom else 0.0


# ─── Layer 3 — Color histogram comparison ────────────────────────────────


def _histogram_correlation(a_bgr: np.ndarray, b_bgr: np.ndarray) -> float:
    """HSV histogram correlation (cv2.HISTCMP_CORREL).

    HSV is more robust to lighting changes than BGR. We use 50 H-bins × 60
    S-bins (no V to discount brightness shifts).
    """
    a_hsv = cv2.cvtColor(a_bgr, cv2.COLOR_BGR2HSV)
    b_hsv = cv2.cvtColor(b_bgr, cv2.COLOR_BGR2HSV)
    hist_a = cv2.calcHist([a_hsv], [0, 1], None, [50, 60], [0, 180, 0, 256])
    hist_b = cv2.calcHist([b_hsv], [0, 1], None, [50, 60], [0, 180, 0, 256])
    cv2.normalize(hist_a, hist_a, alpha=0.0, beta=1.0, norm_type=cv2.NORM_MINMAX)
    cv2.normalize(hist_b, hist_b, alpha=0.0, beta=1.0, norm_type=cv2.NORM_MINMAX)
    return float(cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_CORREL))


# ─── Pair-level + order-level scoring ────────────────────────────────────


def score_pair(pk_path: Path | str, rt_path: Path | str) -> PairScores:
    """Run layers 1–3 on a single PK/RT image pair."""
    pk = _load_and_resize(Path(pk_path))
    rt = _load_and_resize(Path(rt_path))
    return PairScores(
        ssim=_ssim(pk, rt),
        orb_match_ratio=_orb_match_ratio(pk, rt),
        histogram_corr=_histogram_correlation(pk, rt),
    )


def score_order(
    pk_front: Path | str,
    pk_back: Path | str,
    rt_front: Path | str,
    rt_back: Path | str,
) -> DiffScores:
    """Run all 4 layers on a full PK/RT image set."""
    front = score_pair(pk_front, rt_front)
    back = score_pair(pk_back, rt_back)
    pk_ocr = extract_fpc(pk_back)
    rt_ocr = extract_fpc(rt_back)
    return DiffScores(front=front, back=back, pk_ocr=pk_ocr, rt_ocr=rt_ocr)
