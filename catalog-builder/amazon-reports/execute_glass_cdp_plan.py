"""Execute Glass CDP chunked plan by reading step JSON files.

Agent helper: prints step index and result path after each fetch.
Run fetch step via browser_cdp MCP, then:
  python execute_glass_cdp_plan.py save 0 <cdp_response.json>
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

OUT_DIR = Path(r"c:\Projects\Amazon Systems Design\data\mahika\amazon-seller-invoices")
SCRIPT_DIR = Path(__file__).resolve().parent


def step_path(batch: int, step: int) -> Path:
    return OUT_DIR / f"_cdp_steps_{batch:03d}" / f"step_{step:02d}.json"


def load_step(batch: int, step: int) -> dict:
    return json.loads(step_path(batch, step).read_text(encoding="utf-8"))


def save_fetch(batch: int, response_path: Path) -> dict:
    data = json.loads(response_path.read_text(encoding="utf-8"))
    value = data.get("result", {}).get("value", data)
    resp_path = OUT_DIR / f"_cdp_super_{batch:03d}_response.json"
    resp_path.write_text(json.dumps({"result": {"value": value}}, ensure_ascii=False), encoding="utf-8")
    subprocess.check_call([
        sys.executable,
        str(SCRIPT_DIR / "save_superbatch_response.py"),
        str(resp_path),
    ])
    (OUT_DIR / f"_cdp_super_{batch:03d}_done.marker").write_text(
        datetime.now(UTC).isoformat(), encoding="utf-8",
    )
    ok = sum(1 for x in value if x.get("ok"))
    fail = sum(1 for x in value if not x.get("ok"))
    return {"downloaded": ok, "failed": fail, "errors": [x for x in value if not x.get("ok")][:3]}


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_expr = sub.add_parser("expr")
    p_expr.add_argument("batch", type=int)
    p_expr.add_argument("step", type=int)

    p_save = sub.add_parser("save")
    p_save.add_argument("batch", type=int)
    p_save.add_argument("response", type=Path)

    p_info = sub.add_parser("info")
    p_info.add_argument("batch", type=int)

    args = parser.parse_args()

    if args.cmd == "expr":
        step = load_step(args.batch, args.step)
        print(json.dumps(step["params"]))
    elif args.cmd == "save":
        stats = save_fetch(args.batch, args.response)
        print(json.dumps(stats, indent=2))
    elif args.cmd == "info":
        plan = json.loads((OUT_DIR / f"_cdp_chunked_super_{args.batch:03d}.json").read_text())
        print(json.dumps({"steps": len(plan["steps"]), "count": plan["count"]}, indent=2))


if __name__ == "__main__":
    main()
