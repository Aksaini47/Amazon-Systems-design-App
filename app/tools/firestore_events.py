#!/usr/bin/env python
"""Read RF Logger's Firestore action tracker as a plain-text timeline.

The app mirrors every ActivityLogService event to
device_events/{androidId}/events/{autoId} (app/lib/services/analytics_service.dart).
Firestore rules deny every client read, so reading needs an admin credential: a
service-account key kept OUTSIDE the repo at
    ~/.config/rf-logger/firebase-service-account.json
(override with the RF_FIREBASE_SA env var). Never commit that file.

    python app/tools/firestore_events.py devices
    python app/tools/firestore_events.py events --since "2026-10-09 16:00" --until "2026-10-09 17:00"
    python app/tools/firestore_events.py events --limit 100 --event video
    python app/tools/firestore_events.py incident "2026-10-09 16:47" --before 20 --after 10

All times typed and printed are IST. Needs: pip install google-auth requests
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
PROJECT = "rf-logger"
BASE = f"https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/(default)/documents"
KEY_PATH = os.environ.get(
    "RF_FIREBASE_SA",
    os.path.join(os.path.expanduser("~"), ".config", "rf-logger", "firebase-service-account.json"),
)


def _session():
    try:
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2 import service_account
    except ImportError:
        sys.exit("Missing dependency: pip install google-auth requests")
    if not os.path.isfile(KEY_PATH):
        sys.exit(
            f"Service-account key not found at {KEY_PATH}\n"
            "Firebase console > rf-logger > Project settings > Service accounts > "
            "Generate new private key, then save the JSON at that path (or set RF_FIREBASE_SA)."
        )
    creds = service_account.Credentials.from_service_account_file(
        KEY_PATH, scopes=["https://www.googleapis.com/auth/datastore"]
    )
    return AuthorizedSession(creds)


def _decode(v):
    if "stringValue" in v:
        return v["stringValue"]
    if "integerValue" in v:
        return int(v["integerValue"])
    if "doubleValue" in v:
        return v["doubleValue"]
    if "booleanValue" in v:
        return v["booleanValue"]
    if "timestampValue" in v:
        return v["timestampValue"]
    if "nullValue" in v:
        return None
    if "mapValue" in v:
        return {k: _decode(x) for k, x in v["mapValue"].get("fields", {}).items()}
    if "arrayValue" in v:
        return [_decode(x) for x in v["arrayValue"].get("values", [])]
    return str(v)


def _parse_ist(text):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=IST)
        except ValueError:
            pass
    sys.exit(f'Bad time "{text}" - use "YYYY-MM-DD HH:MM" (IST).')


def _rfc3339(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _row_time(row):
    raw = row.get("ts")
    if raw:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(IST)
    client = row.get("client_ts")
    if client:
        return datetime.fromisoformat(client).replace(tzinfo=IST)
    return None


def _devices(sess):
    r = sess.get(f"{BASE}/device_events", params={"pageSize": 300, "showMissing": "true"})
    r.raise_for_status()
    return [d["name"].rsplit("/", 1)[-1] for d in r.json().get("documents", [])]


def _query(sess, device, since, until, limit):
    bounds = []
    if since:
        bounds.append({"fieldFilter": {"field": {"fieldPath": "ts"}, "op": "GREATER_THAN_OR_EQUAL",
                                       "value": {"timestampValue": _rfc3339(since)}}})
    if until:
        bounds.append({"fieldFilter": {"field": {"fieldPath": "ts"}, "op": "LESS_THAN_OR_EQUAL",
                                       "value": {"timestampValue": _rfc3339(until)}}})
    ranged = bool(bounds)
    q = {
        "from": [{"collectionId": "events"}],
        "orderBy": [{"field": {"fieldPath": "ts"}, "direction": "ASCENDING" if ranged else "DESCENDING"}],
        "limit": limit,
    }
    if len(bounds) == 1:
        q["where"] = bounds[0]
    elif bounds:
        q["where"] = {"compositeFilter": {"op": "AND", "filters": bounds}}
    r = sess.post(f"{BASE}/device_events/{device}:runQuery", json={"structuredQuery": q})
    r.raise_for_status()
    rows = []
    for item in r.json():
        doc = item.get("document")
        if not doc:
            continue
        row = {k: _decode(v) for k, v in doc.get("fields", {}).items()}
        row["_device"] = device
        rows.append(row)
    if not ranged:
        rows.reverse()
    return rows


def _fetch(args, since, until):
    sess = _session()
    devices = [args.device] if args.device else _devices(sess)
    rows = []
    for dev in devices:
        rows.extend(_query(sess, dev, since, until, args.limit))
    rows.sort(key=lambda r: _row_time(r) or datetime.min.replace(tzinfo=IST))
    if args.event:
        rows = [r for r in rows if args.event.lower() in str(r.get("event", "")).lower()]
    if args.mode:
        rows = [r for r in rows if str(r.get("mode", "")).lower() == args.mode.lower()]
    return rows, len(devices)


def _print(rows, ndev, raw):
    if raw:
        print(json.dumps(rows, indent=2, default=str))
        return
    last_day = None
    for r in rows:
        t = _row_time(r)
        day = t.strftime("%d %b %Y") if t else "?"
        if day != last_day:
            print(f"\n=== {day} (IST) ===")
            last_day = day
        parts = [t.strftime("%H:%M:%S") if t else "??:??:??", f"{r.get('event', '?'):<26}"]
        if ndev > 1:
            parts.append(f"dev={str(r['_device'])[:6]}")
        for key in ("mode", "order_id", "awb", "qc"):
            if r.get(key):
                parts.append(f"{key}={r[key]}")
        if r.get("patch_number") is not None:
            parts.append(f"p{r['patch_number']}")
        for k, v in (r.get("extra") or {}).items():
            parts.append(f"{k}={v}")
        print("  ".join(parts))
    print(f"\n{len(rows)} event(s).")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("devices", help="list device ids that have logged events")
    for name in ("events", "incident"):
        s = sub.add_parser(name)
        s.add_argument("--device")
        s.add_argument("--event", help="substring filter on the event name")
        s.add_argument("--mode", choices=["pk", "rt"])
        s.add_argument("--limit", type=int, default=1000)
        s.add_argument("--raw", action="store_true", help="dump JSON instead of the timeline")
        if name == "events":
            s.add_argument("--since")
            s.add_argument("--until")
        else:
            s.add_argument("at", help='incident time, e.g. "2026-10-09 16:47"')
            s.add_argument("--before", type=int, default=20, help="minutes before (default 20)")
            s.add_argument("--after", type=int, default=10, help="minutes after (default 10)")
    args = p.parse_args()

    if args.cmd == "devices":
        sess = _session()
        for dev in _devices(sess):
            newest = _query(sess, dev, None, None, 1)
            when = _row_time(newest[0]).strftime("%d %b %H:%M") if newest else "-"
            print(f"{dev}  last event {when} IST")
        return
    if args.cmd == "events":
        since = _parse_ist(args.since) if args.since else None
        until = _parse_ist(args.until) if args.until else None
    else:
        at = _parse_ist(args.at)
        since, until = at - timedelta(minutes=args.before), at + timedelta(minutes=args.after)
    rows, ndev = _fetch(args, since, until)
    _print(rows, ndev, args.raw)


if __name__ == "__main__":
    main()
