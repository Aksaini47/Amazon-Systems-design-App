"""Initialize the NVMe folder hierarchy that Mahika expects.

Per `mahika_capture_specs.md §1.2`, the NVMe is the active runner's
storage. The folder layout is:

    {MAHIKA_STORAGE_ROOT}/
        orders/         — synced from the mobile camera app; one folder per order_id
        sync_inbox/     — temporary landing zone for fresh mobile syncs before
                          they're moved to orders/ (atomic-rename pattern)
        processed/      — orders where Phase 3 composite generation + claim
                          filing is complete (cold storage)
        backups/        — daily Postgres snapshots taken by the agent
        logs/           — structured agent logs (one file per day)

Run this once per machine after the NVMe is plugged in. Idempotent —
safe to re-run; existing files/folders are not touched.

CLI:
    python -m scripts.setup_nvme_folders
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow running directly from `agent/` without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# Force UTF-8 on stdout/stderr so warning emojis don't trip Windows' default
# cp1252 encoding. Python 3.7+ supports reconfigure; older versions silently
# inherit the parent shell encoding, which is what we want anyway.
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

from mahika.config import settings  # noqa: E402


def ensure_dir(p: Path) -> bool:
    """Create a directory if missing. Returns True if created, False if existed."""
    if p.exists():
        return False
    p.mkdir(parents=True, exist_ok=True)
    return True


def main() -> int:
    root = settings.storage_root
    print(f"Mahika storage root: {root}")
    print(f"  Runner ID:           {settings.runner_id}")

    if not root.exists():
        # Could be an unplugged NVMe — be loud, don't silently create on C:.
        print()
        print(f"WARNING: Storage root {root} does NOT exist.")
        print("   This usually means:")
        print("     - The NVMe SSD is not connected via USB-C")
        print("     - The drive letter changed (check Disk Manager)")
        print("     - You're on a different machine and MAHIKA_STORAGE_ROOT")
        print("       in .env doesn't match this machine's NVMe path")
        print()
        if os.environ.get("MAHIKA_SETUP_NONINTERACTIVE") == "1":
            print(f"  Non-interactive mode: creating {root}")
            root.mkdir(parents=True, exist_ok=True)
        else:
            confirm = input(f"Create it anyway at {root}? [y/N] ").strip().lower()
            if confirm != "y":
                print("Aborted.")
                return 1
            root.mkdir(parents=True, exist_ok=True)

    created: list[str] = []
    skipped: list[str] = []
    for sub in [
        settings.orders_dir,
        settings.sync_inbox_dir,
        settings.processed_dir,
        settings.backups_dir,
        settings.logs_dir,
    ]:
        if ensure_dir(sub):
            created.append(str(sub))
        else:
            skipped.append(str(sub))

    print()
    print(f"Created: {len(created)} folder(s)")
    for c in created:
        print(f"  + {c}")
    print(f"Existed (skipped): {len(skipped)} folder(s)")
    for s in skipped:
        print(f"  - {s}")

    # Write a marker file so we can detect runner-environment changes later.
    marker = root / ".mahika_runner_marker"
    marker.write_text(
        f"runner_id: {settings.runner_id}\n"
        f"hostname: {os.environ.get('COMPUTERNAME', 'unknown')}\n"
        f"initialized_by: setup_nvme_folders.py\n",
        encoding="utf-8",
    )
    print(f"\nOK: Marker written: {marker}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
