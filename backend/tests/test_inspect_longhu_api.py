"""Inspect the raw Eastmoney daily billboard detail API response.

Run directly:
    python tests/test_inspect_longhu_api.py
    python tests/test_inspect_longhu_api.py --limit 100 --output longhu_response.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import httpx

API_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
PAGE_URL = "https://data.eastmoney.com/stock/tradedetail.html"


def build_request_params(*, page: int, page_size: int) -> dict[str, Any]:
    return {
        "reportName": "RPT_DAILYBILLBOARD_DETAILSNEW",
        "columns": "ALL",
        "pageNumber": page,
        "pageSize": page_size,
        "sortTypes": "-1",
        "sortColumns": "TRADE_DATE",
        "source": "WEB",
        "client": "WEB",
    }


def fetch_payload(*, page: int, page_size: int, timeout: float) -> dict[str, Any]:
    response = httpx.get(
        API_URL,
        params=build_request_params(page=page, page_size=page_size),
        headers={
            "User-Agent": "Mozilla/5.0 TodayHighlights/0.1",
            "Referer": PAGE_URL,
            "Accept": "application/json,text/plain,*/*",
        },
        timeout=timeout,
        follow_redirects=True,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("API response is not a JSON object")
    return payload


def summarize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    result = payload.get("result") or {}
    items = result.get("data") or []
    first = items[0] if items and isinstance(items[0], dict) else {}
    return {
        "success": payload.get("success"),
        "message": payload.get("message"),
        "code": payload.get("code"),
        "total_pages": result.get("pages"),
        "total_count": result.get("count"),
        "returned_count": len(items),
        "item_fields": sorted(first.keys()),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="查看东方财富龙虎榜明细接口的原始 JSON 返回值",
    )
    parser.add_argument("--page", type=int, default=1, help="页码，默认 1")
    parser.add_argument("--limit", type=int, default=5, help="请求并打印的记录数量，默认 5")
    parser.add_argument("--timeout", type=float, default=20, help="请求超时秒数，默认 20")
    parser.add_argument("--output", type=Path, help="可选：把完整原始响应保存为 JSON 文件")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.page < 1:
        raise SystemExit("--page 必须大于等于 1")
    if not 1 <= args.limit <= 500:
        raise SystemExit("--limit 必须在 1 到 500 之间")

    params = build_request_params(page=args.page, page_size=args.limit)
    print("请求地址:")
    print(f"  {API_URL}")
    print("请求参数:")
    print(json.dumps(params, ensure_ascii=False, indent=2))

    payload = fetch_payload(page=args.page, page_size=args.limit, timeout=args.timeout)
    print("\n接口概况:")
    print(json.dumps(summarize_payload(payload), ensure_ascii=False, indent=2))

    print("\n当前页原始记录:")
    items = (payload.get("result") or {}).get("data") or []
    print(json.dumps(items, ensure_ascii=False, indent=2, default=str))

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        print(f"\n完整响应已保存到: {args.output.resolve()}")


def test_inspect_longhu_uses_daily_billboard_detail_report() -> None:
    params = build_request_params(page=2, page_size=30)

    assert params["reportName"] == "RPT_DAILYBILLBOARD_DETAILSNEW"
    assert params["columns"] == "ALL"
    assert params["pageNumber"] == 2
    assert params["pageSize"] == 30


def test_summarize_payload_lists_all_record_fields() -> None:
    payload = {
        "success": True,
        "result": {
            "pages": 3,
            "count": 85,
            "data": [
                {
                    "SECURITY_CODE": "301526",
                    "SECURITY_NAME_ABBR": "国际复材",
                    "BILLBOARD_NET_AMT": 268777357.14,
                }
            ],
        },
    }

    summary = summarize_payload(payload)

    assert summary["success"] is True
    assert summary["total_count"] == 85
    assert summary["returned_count"] == 1
    assert summary["item_fields"] == [
        "BILLBOARD_NET_AMT",
        "SECURITY_CODE",
        "SECURITY_NAME_ABBR",
    ]


if __name__ == "__main__":
    main()
