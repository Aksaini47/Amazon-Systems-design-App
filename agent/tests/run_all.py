"""Run every phase smoke test sequentially with a summary line.

Usage:
    python -m tests.run_all

Each test is a separate subprocess so a hang in one doesn't poison the others.
Total runtime ~2-3 minutes against the live Oracle DB.

This is a smoke-test orchestrator, not a pytest replacement — it's intentional
that each phase test is self-contained and runnable standalone.
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = REPO_ROOT / ".venv" / "Scripts" / "python.exe"


SUITES = [
    ("Phase 3 — Evidence Processing", "tests.test_phase3_smoke"),
    ("Phase 4 — Mahika Core",         "tests.test_phase4_smoke"),
    ("Phase 5 — Playwright SAFE-T",   "tests.test_phase5_smoke"),
    ("Phase 6 — Cockpit",             "tests.test_phase6_smoke"),
]


def run_one(label: str, module: str, timeout_s: int = 180) -> tuple[bool, float, str]:
    """Run one test module. Returns (passed, duration_sec, tail_output)."""
    start = time.monotonic()
    try:
        proc = subprocess.run(
            [str(PYTHON), "-m", module],
            cwd=str(REPO_ROOT),
            env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"},
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        duration = time.monotonic() - start
        # Capture the last 5 lines of stdout for the summary
        stdout_tail = "\n".join(proc.stdout.strip().splitlines()[-5:])
        return (proc.returncode == 0, duration, stdout_tail)
    except subprocess.TimeoutExpired:
        return (False, time.monotonic() - start, f"TIMEOUT after {timeout_s}s")
    except Exception as exc:
        return (False, time.monotonic() - start, f"{type(exc).__name__}: {exc}")


def main() -> int:
    if not PYTHON.exists():
        print(f"ERROR: venv python not found at {PYTHON}")
        print("       Run scripts\\mahika-setup.bat first.")
        return 1

    print("=" * 72)
    print("  Mahika — run all phase smoke tests")
    print("=" * 72)
    print()

    results: list[tuple[str, bool, float, str]] = []
    for label, module in SUITES:
        print(f"[ RUN  ] {label}  ({module})")
        passed, duration, tail = run_one(label, module)
        results.append((label, passed, duration, tail))
        marker = "[ PASS ]" if passed else "[ FAIL ]"
        print(f"{marker} {label}  ({duration:.1f}s)")
        if not passed:
            print("  --- tail ---")
            for line in tail.splitlines():
                print(f"    {line}")
        print()

    pass_count = sum(1 for _, p, _, _ in results if p)
    total = len(results)
    total_duration = sum(d for _, _, d, _ in results)
    print("=" * 72)
    print(f"  {pass_count}/{total} suites passed  —  total runtime {total_duration:.1f}s")
    print("=" * 72)
    return 0 if pass_count == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
