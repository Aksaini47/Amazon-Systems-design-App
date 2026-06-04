"""Phase 3 end-to-end smoke test using synthetic fixtures.

This script generates 3 synthetic test orders that exercise each verdict path:

    SYNTHETIC-OK-001:        PK and RT photos are *identical* → expect OK
    SYNTHETIC-DAMAGED-001:   PK = pristine, RT = scuffed/cracked → expect DAMAGED
    SYNTHETIC-DIFFERENT-001: PK and RT are unrelated images     → expect DIFFERENT

Run:
    python -m tests.test_phase3_smoke

Outputs each order's composite under {storage_root}/orders/{order_id}/ and
prints a summary table to stdout. Sir can open the composite JPGs to visually
verify the layout + footer block render correctly.

NOTE: This is a smoke test, not a unit test. It exercises the *integration* —
not the per-layer numerics. Tight per-layer assertions belong in a fuller
pytest suite once Sir provides real evidence samples.
"""
from __future__ import annotations

import json
import random
import sys
from datetime import UTC, datetime
from pathlib import Path

# Allow running directly from `agent/` without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from mahika.config import settings  # noqa: E402
from mahika.services.pipeline import (  # noqa: E402
    OrderNotReady,
    asset_path,
    order_dir,
    process_order,
)

# ─── Fixture generator ───────────────────────────────────────────────────

IMG_SIZE = (2000, 2500)  # match spec §2.2 (2K)


def _make_phone_photo(
    base_color: tuple[int, int, int],
    label: str,
    fpc_code: str | None,
    *,
    seed: int,
    scuff: bool = False,
) -> Image.Image:
    """Synthesise a 2K phone-photo-like image with optional FPC code on the back.

    Not realistic, but enough texture for ORB to find keypoints and for SSIM
    to differentiate identical / damaged / different scenarios deterministically.
    """
    rng = random.Random(seed)
    img = Image.new("RGB", IMG_SIZE, base_color)
    draw = ImageDraw.Draw(img)

    # Sprinkle deterministic blobs to give the image high-frequency content
    # (otherwise ORB finds zero keypoints and the test is meaningless).
    for _ in range(500):
        cx = rng.randint(50, IMG_SIZE[0] - 50)
        cy = rng.randint(50, IMG_SIZE[1] - 50)
        radius = rng.randint(8, 24)
        colour = tuple(min(255, max(0, c + rng.randint(-30, 30))) for c in base_color)
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=colour)

    # Add a large rounded rectangle in the middle to anchor SSIM
    body_left = IMG_SIZE[0] * 0.18
    body_top = IMG_SIZE[1] * 0.15
    body_right = IMG_SIZE[0] * 0.82
    body_bot = IMG_SIZE[1] * 0.85
    body_colour = tuple(min(255, max(0, c - 30)) for c in base_color)
    draw.rounded_rectangle(
        (body_left, body_top, body_right, body_bot),
        radius=80,
        fill=body_colour,
    )

    if fpc_code is not None:
        # Render the FPC code in clear high-contrast text near the bottom of the body
        try:
            font = ImageFont.truetype("arialbd.ttf", 110)
        except OSError:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), fpc_code, font=font)
        tw = bbox[2] - bbox[0]
        draw.text(
            (IMG_SIZE[0] / 2 - tw / 2, IMG_SIZE[1] * 0.72),
            fpc_code,
            fill=(255, 255, 255),
            font=font,
        )

    if scuff:
        # Moderate damage overlay: scratches + a few discolouration patches —
        # tuned to drop SSIM into the 0.85–0.95 "damaged" band without crashing
        # below 0.85 (which would be "different product" territory).
        rng2 = random.Random(seed + 99)
        # Scratches across the body
        for _ in range(70):
            x1 = rng2.randint(int(body_left), int(body_right))
            y1 = rng2.randint(int(body_top), int(body_bot))
            x2 = x1 + rng2.randint(-350, 350)
            y2 = y1 + rng2.randint(-120, 120)
            draw.line((x1, y1, x2, y2), fill=(25, 25, 25), width=7)
        # Discolouration patches
        for _ in range(8):
            ox = rng2.randint(int(body_left), int(body_right))
            oy = rng2.randint(int(body_top), int(body_bot))
            ow = rng2.randint(100, 200)
            oh = rng2.randint(60, 130)
            draw.ellipse(
                (ox - ow, oy - oh, ox + ow, oy + oh),
                fill=(60, 50, 40),
            )

    # Label corner for human inspection
    try:
        label_font = ImageFont.truetype("arial.ttf", 60)
    except OSError:
        label_font = ImageFont.load_default()
    draw.text((40, 40), label, fill=(255, 255, 255), font=label_font)

    return img


def _write_fixture(
    order_id: str,
    *,
    pk_color: tuple[int, int, int],
    rt_color: tuple[int, int, int],
    pk_fpc: str | None,
    rt_fpc: str | None,
    rt_scuff: bool,
    seed_offset: int = 0,
    pk_uses_pk_color_for_back: bool = True,
    rt_uses_rt_color_for_back: bool = True,
) -> None:
    """Write 4 JPGs + meta.json for an order folder."""
    folder = order_dir(order_id)
    folder.mkdir(parents=True, exist_ok=True)

    pk_front = _make_phone_photo(pk_color, f"PK FRONT {order_id}", None, seed=1 + seed_offset)
    pk_back = _make_phone_photo(
        pk_color if pk_uses_pk_color_for_back else (180, 180, 200),
        f"PK BACK {order_id}", pk_fpc, seed=2 + seed_offset,
    )
    rt_front = _make_phone_photo(rt_color, f"RT FRONT {order_id}", None, seed=3 + seed_offset, scuff=rt_scuff)
    rt_back = _make_phone_photo(
        rt_color if rt_uses_rt_color_for_back else (180, 180, 200),
        f"RT BACK {order_id}", rt_fpc, seed=4 + seed_offset, scuff=rt_scuff,
    )

    pk_front.save(asset_path(order_id, "PK_front"), quality=90)
    pk_back.save(asset_path(order_id, "PK_back"), quality=90)
    rt_front.save(asset_path(order_id, "RT_front"), quality=90)
    rt_back.save(asset_path(order_id, "RT_back"), quality=90)

    meta = {
        "order_id": order_id,
        "asin": "B0SYNTHETIC",
        "sku": "SYN-001",
        "awb": "SYNTH123456789",
        "dispatched_at": "2026-05-12T10:00:00",
        "returned_at": "2026-05-17T14:00:00",
        "created_at": datetime.now(UTC).isoformat(),
        "verdict": None,  # filled below per scenario
    }
    (folder / f"{order_id}_meta.json").write_text(
        json.dumps(meta, indent=2),
        encoding="utf-8",
    )


def _seed_three_scenarios() -> list[tuple[str, str, str]]:
    """Return [(order_id, scenario_name, expected_verdict), ...]"""

    # Scenario 1 — Identical product (same colour, same FPC). PK_front uses
    # seed S; RT_front uses the *same* seed S so the two images are essentially
    # identical → SSIM ≈ 1.0, ORB matches well, FPC matches.
    ok_id = "SYNTHETIC-OK-001"
    folder = order_dir(ok_id)
    folder.mkdir(parents=True, exist_ok=True)
    pk_color = (60, 80, 130)
    fpc = "ABC123XYZ"
    pk_front = _make_phone_photo(pk_color, f"PK FRONT {ok_id}", None, seed=1)
    pk_back = _make_phone_photo(pk_color, f"PK BACK {ok_id}", fpc, seed=2)
    pk_front.save(asset_path(ok_id, "PK_front"), quality=90)
    pk_back.save(asset_path(ok_id, "PK_back"), quality=90)
    # RT uses identical seeds → same images as PK
    rt_front = _make_phone_photo(pk_color, f"RT FRONT {ok_id}", None, seed=1)
    rt_back = _make_phone_photo(pk_color, f"RT BACK {ok_id}", fpc, seed=2)
    rt_front.save(asset_path(ok_id, "RT_front"), quality=90)
    rt_back.save(asset_path(ok_id, "RT_back"), quality=90)
    (folder / f"{ok_id}_meta.json").write_text(
        json.dumps({
            "order_id": ok_id, "asin": "B0SYNTHETIC", "verdict": "OK",
            "dispatched_at": "2026-05-12T10:00:00", "returned_at": "2026-05-17T14:00:00",
        }, indent=2),
        encoding="utf-8",
    )

    # Scenario 2 — Damaged: same product but RT has scuff overlay (same colour,
    # same FPC, but high-freq differences from scratches). Should land in
    # SSIM 0.85–0.95 band → DAMAGED.
    dmg_id = "SYNTHETIC-DAMAGED-001"
    folder = order_dir(dmg_id)
    folder.mkdir(parents=True, exist_ok=True)
    color2 = (90, 110, 130)
    fpc2 = "DAMAGED01"
    pk_front2 = _make_phone_photo(color2, f"PK FRONT {dmg_id}", None, seed=5)
    pk_back2 = _make_phone_photo(color2, f"PK BACK {dmg_id}", fpc2, seed=6)
    pk_front2.save(asset_path(dmg_id, "PK_front"), quality=90)
    pk_back2.save(asset_path(dmg_id, "PK_back"), quality=90)
    rt_front2 = _make_phone_photo(color2, f"RT FRONT {dmg_id}", None, seed=5, scuff=True)
    rt_back2 = _make_phone_photo(color2, f"RT BACK {dmg_id}", fpc2, seed=6, scuff=True)
    rt_front2.save(asset_path(dmg_id, "RT_front"), quality=90)
    rt_back2.save(asset_path(dmg_id, "RT_back"), quality=90)
    (folder / f"{dmg_id}_meta.json").write_text(
        json.dumps({
            "order_id": dmg_id, "asin": "B0SYNTHETIC", "verdict": "DAMAGED",
            "dispatched_at": "2026-05-12T10:00:00", "returned_at": "2026-05-17T14:00:00",
        }, indent=2),
        encoding="utf-8",
    )

    # Scenario 3 — Different: PK and RT are *structurally* unrelated images.
    # Different colour, different shape (rectangle vs ellipse), different seed
    # patterns, completely different FPC codes. SSIM should fall well below
    # 0.85 to trigger DIFFERENT verdict from the SSIM rule alone (since the
    # OCR layer is off without Tesseract).
    diff_id = "SYNTHETIC-DIFFERENT-001"
    folder = order_dir(diff_id)
    folder.mkdir(parents=True, exist_ok=True)
    # PK: green phone body (rounded rect) — uses standard generator
    pk_front3 = _make_phone_photo((40, 120, 60), f"PK FRONT {diff_id}", None, seed=7)
    pk_back3 = _make_phone_photo((40, 120, 60), f"PK BACK {diff_id}", "REAL999A", seed=8)
    pk_front3.save(asset_path(diff_id, "PK_front"), quality=90)
    pk_back3.save(asset_path(diff_id, "PK_back"), quality=90)
    # RT: a totally different visual — solid red background with an off-centre
    # ELLIPSE in cream, no rounded-rect body. Replaces the entire structure.
    def _make_different_photo(seed: int, label: str, fpc: str | None) -> Image.Image:
        rng = random.Random(seed)
        img = Image.new("RGB", IMG_SIZE, (200, 70, 70))
        d = ImageDraw.Draw(img)
        # Scattered noise circles for keypoint variability
        for _ in range(700):
            cx = rng.randint(0, IMG_SIZE[0])
            cy = rng.randint(0, IMG_SIZE[1])
            r = rng.randint(4, 18)
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(rng.randint(160, 230), rng.randint(50, 120), rng.randint(50, 120)))
        # Big cream ellipse offset from centre
        d.ellipse(
            (300, 800, IMG_SIZE[0] - 700, IMG_SIZE[1] - 300),
            fill=(230, 210, 180),
        )
        if fpc:
            try:
                f = ImageFont.truetype("arialbd.ttf", 110)
            except OSError:
                f = ImageFont.load_default()
            d.text((500, 1800), fpc, fill=(40, 40, 40), font=f)
        try:
            lf = ImageFont.truetype("arial.ttf", 60)
        except OSError:
            lf = ImageFont.load_default()
        d.text((40, 40), label, fill=(255, 255, 255), font=lf)
        return img

    rt_front3 = _make_different_photo(seed=15, label=f"RT FRONT {diff_id}", fpc=None)
    rt_back3 = _make_different_photo(seed=16, label=f"RT BACK {diff_id}", fpc="FAKE111B")
    rt_front3.save(asset_path(diff_id, "RT_front"), quality=90)
    rt_back3.save(asset_path(diff_id, "RT_back"), quality=90)
    (folder / f"{diff_id}_meta.json").write_text(
        json.dumps({
            "order_id": diff_id, "asin": "B0SYNTHETIC", "verdict": "DIFFERENT",
            "dispatched_at": "2026-05-12T10:00:00", "returned_at": "2026-05-17T14:00:00",
        }, indent=2),
        encoding="utf-8",
    )

    return [
        (ok_id, "Identical (OK)", "OK"),
        (dmg_id, "Scuffed (DAMAGED)", "DAMAGED"),
        (diff_id, "Unrelated (DIFFERENT)", "DIFFERENT"),
    ]


# ─── Smoke runner ────────────────────────────────────────────────────────


def main() -> int:
    print("=== Phase 3 smoke test ===")
    print(f"Storage root: {settings.storage_root}")
    print()

    scenarios = _seed_three_scenarios()
    print("Fixtures created. Running pipeline on each scenario...")
    print()

    print(f"{'Scenario':25s} {'Expected':12s} {'Suggested':12s} {'Conf':>6s}  {'SSIM':>6s}  Composite")
    print("-" * 110)

    pass_count = 0
    for order_id, scenario, expected in scenarios:
        try:
            result = process_order(order_id, write_db=False)
        except OrderNotReady as exc:
            print(f"{scenario:25s} {expected:12s}  FAILED — {exc}")
            continue
        suggested = result.suggested.verdict.value
        conf = result.suggested.confidence
        ssim = result.scores.mean_ssim
        composite_short = str(result.composite_path).replace(str(settings.storage_root), "...")
        marker = "✓" if suggested == expected else "✗"
        print(
            f"{scenario:25s} {expected:12s} {suggested:12s} {conf:6.1%}  {ssim:6.3f}  "
            f"{marker} {composite_short}"
        )
        if suggested == expected:
            pass_count += 1

    print()
    print(f"=== {pass_count}/{len(scenarios)} scenarios produced expected verdict ===")
    return 0 if pass_count == len(scenarios) else 1


if __name__ == "__main__":
    raise SystemExit(main())
