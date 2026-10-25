"""Send ONE short alert to Sir's own Telegram chat (the project's out-of-band channel, bot from .env MAHIKA_TELEGRAM_*).

  python agent/scripts/notify_sir.py "Samvaad: 3 cases need you (Himani, Rajat, Md.abusaid)"

Prints TELEGRAM_SENT or TELEGRAM_NOT_SENT (then the caller falls back to the Windows toast). Never prints the token. Keep the text under ~300 characters,
order ids / first names / codes only, no buyer message text, no personal data.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agent" / "src"))


def main() -> int:
    text = " ".join(sys.argv[1:]).strip()
    if not text:
        print("usage: notify_sir.py <text>"); return 2
    from mahika.services.notifier import send_plain_message
    ok = send_plain_message(text[:900])
    print("TELEGRAM_SENT" if ok else "TELEGRAM_NOT_SENT")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
