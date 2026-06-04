"""One-off SP-API access probe — what endpoints return data with current .env creds."""
from __future__ import annotations

import json
import sys

import httpx

from mahika.config import settings
from mahika.sp_api.client import check_status, ping


def get_token() -> tuple[str | None, int, str]:
    r = httpx.post(
        "https://api.amazon.com/auth/o2/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": settings.sp_api_refresh_token,
            "client_id": settings.sp_api_lwa_client_id,
            "client_secret": settings.sp_api_lwa_client_secret,
        },
        timeout=25,
    )
    if r.status_code != 200:
        return None, r.status_code, r.text[:120]
    return r.json()["access_token"], 200, "OK"


def call(method: str, url: str, token: str, json_body: dict | None = None) -> tuple[int | str, str]:
    headers = {"x-amz-access-token": token, "Accept": "application/json"}
    try:
        if method == "GET":
            resp = httpx.get(url, headers=headers, timeout=25)
        else:
            headers["Content-Type"] = "application/json"
            resp = httpx.post(url, headers=headers, json=json_body, timeout=25)
        try:
            data = resp.json()
        except Exception:
            return resp.status_code, resp.text[:100]
        if "errors" in data:
            err = data["errors"][0]
            return resp.status_code, f"{err.get('code')}: {err.get('message', '')[:90]}"
        if "payload" in data:
            payload = data["payload"]
            if isinstance(payload, dict):
                parts = [f"keys={','.join(list(payload.keys())[:8])}"]
                if "Orders" in payload:
                    parts.append(f"orders={len(payload['Orders'])}")
                if "FinancialEvents" in payload:
                    parts.append("FinancialEvents=yes")
                if "reports" in payload:
                    parts.append(f"reports={len(payload['reports'])}")
                return resp.status_code, " | ".join(parts)
            return resp.status_code, "payload=yes"
        return resp.status_code, f"keys={','.join(list(data.keys())[:6])}"
    except Exception as exc:
        return "ERR", str(exc)[:90]


def main() -> None:
    mp = settings.sp_api_marketplace_id
    token, lwa_code, _ = get_token()
    out: dict = {
        "lwa": lwa_code,
        "marketplace": mp,
        "region": settings.sp_api_region,
        "sp_api_configured": settings.sp_api_configured,
        "tests": [],
    }
    if not token:
        print(json.dumps(out, indent=2))
        sys.exit(1)

    prod = "https://sellingpartnerapi-eu.amazon.com"
    sand = "https://sandbox.sellingpartnerapi-eu.amazon.com"

    cases: list[tuple[str, str, str, dict | None]] = [
        # Production — real Badeja attempt
        ("PROD Orders (7d)", "GET", f"{prod}/orders/v0/orders?MarketplaceIds={mp}&CreatedAfter=2026-05-13T00:00:00Z", None),
        ("PROD Finances", "GET", f"{prod}/finances/v0/financialEvents?PostedAfter=2026-05-01T00:00:00Z", None),
        ("PROD Reports list", "GET", f"{prod}/reports/2021-06-30/reports?reportTypes=GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL&marketplaceIds={mp}", None),
        ("PROD FBA inventory", "GET", f"{prod}/fba/inventory/v1/summaries?marketplaceIds={mp}&granularityType=Marketplace&granularityId={mp}", None),
        # Sandbox — static fixtures
        ("SANDBOX Orders TEST_CASE_200", "GET", f"{sand}/orders/v0/orders?MarketplaceIds=ATVPDKIKX0DER&CreatedAfter=TEST_CASE_200", None),
        ("SANDBOX Orders CA static", "GET", f"{sand}/orders/v0/orders?MarketplaceIds=A2EUQ1WTGCTBG2&CreatedAfter=2017-01-21T18:12:21.000Z", None),
        ("SANDBOX Finances", "GET", f"{sand}/finances/v0/financialEvents?PostedAfter=2017-01-01T00:00:00Z", None),
        (
            "SANDBOX Reports create",
            "POST",
            f"{sand}/reports/2021-06-30/reports",
            {"reportType": "GET_MERCHANT_LISTINGS_ALL_DATA", "marketplaceIds": ["ATVPDKIKX0DER"]},
        ),
    ]

    for label, method, url, body in cases:
        code, detail = call(method, url, token, body)
        out["tests"].append({"api": label, "status": code, "detail": detail})

    out["mahika_ping"] = ping()
    st = check_status()
    out["status"] = {
        "sandbox_mode": st.sandbox_mode,
        "lwa_ok": st.lwa_ok,
        "api_reachable": st.api_reachable,
        "detail": st.detail,
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
