"""用 Playwright 打开东方财富龙虎榜页面，抓取所有 API 请求和 Cookie。"""
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

OUTPUT = Path(__file__).resolve().parent / "longhu_api_capture.json"

URL = "https://data.eastmoney.com/stock/lhb.html"


def main():
    api_calls = []
    cookies = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Capture ALL XHR/fetch requests
        page.on("request", lambda req: api_calls.append({
            "url": req.url,
            "method": req.method,
            "headers": dict(req.headers),
            "post_data": req.post_data,
        }))

        print("打开龙虎榜页面...")
        page.goto(URL, wait_until="domcontentloaded", timeout=30000)
        # Wait for table to appear
        try:
            page.wait_for_selector("table tbody tr", timeout=15000)
        except Exception:
            pass
        page.wait_for_timeout(5000)  # extra wait for lazy API data

        # Get cookies
        cookies = {c["name"]: c["value"] for c in context.cookies()}

        browser.close()

    # Filter relevant API calls
    data_api_calls = [c for c in api_calls if "/api/" in c["url"] or "getData" in c["url"]]
    xhr_calls = [c for c in api_calls if c["method"] == "POST" or "json" in c["url"].lower() or "api" in c["url"].lower()]

    print(f"\n总共 {len(api_calls)} 个请求")
    print(f"数据 API 请求: {len(data_api_calls)} 个\n")

    print("=" * 100)
    print("API 端点列表:")
    print("=" * 100)
    seen = set()
    for c in data_api_calls:
        url = c["url"]
        # Remove query params for dedup
        base = url.split("?")[0]
        if base not in seen:
            seen.add(base)
            # Print the full URL with params for the first occurrence
            method = c["method"]
            print(f"\n  {method} {url[:200]}")
            # Show key query params
            if "?" in url:
                params = url.split("?")[1].split("&")
                for p in params[:10]:
                    print(f"    {p[:120]}")

    print("\n" + "=" * 100)
    print("Cookie (用于 httpx 后续请求):")
    print("=" * 100)
    cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
    print(f"  {cookie_str[:500]}")

    # Save to JSON
    result = {
        "cookies": cookies,
        "cookie_string": cookie_str,
        "api_endpoints": [
            {"method": c["method"], "url": c["url"]}
            for c in data_api_calls
        ],
        "all_requests": [
            {"method": c["method"], "url": c["url"]}
            for c in api_calls
        ],
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完整抓包数据已写入: {OUTPUT}")


if __name__ == "__main__":
    main()
