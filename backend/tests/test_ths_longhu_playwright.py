"""用 Playwright 打开同花顺龙虎榜页面，抓取 API 请求和 Cookie。"""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUTPUT = Path(__file__).resolve().parent / "ths_longhu_api_capture.json"
URL = "https://data.10jqka.com.cn/market/longhu/"


def main():
    api_calls = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        page.on("request", lambda req: api_calls.append({
            "url": req.url,
            "method": req.method,
            "headers": dict(req.headers),
            "post_data": req.post_data,
        }))

        print("打开同花顺龙虎榜页面...")
        page.goto(URL, wait_until="domcontentloaded", timeout=30000)
        try:
            page.wait_for_selector("table tbody tr", timeout=15000)
        except Exception:
            pass
        page.wait_for_timeout(5000)

        cookies = {c["name"]: c["value"] for c in context.cookies()}
        browser.close()

    # Filter API calls
    data_calls = [c for c in api_calls if "api" in c["url"].lower() or "json" in c["url"].lower() or "getData" in c["url"] or "longhu" in c["url"].lower()]

    print(f"\n总共 {len(api_calls)} 个请求")
    print(f"数据 API 请求: {len(data_calls)} 个\n")

    print("=" * 100)
    print("API 端点列表:")
    print("=" * 100)
    for c in data_calls:
        print(f"\n  {c['method']} {c['url'][:200]}")
        if "?" in c["url"]:
            for p in c["url"].split("?")[1].split("&")[:8]:
                print(f"    {p[:150]}")

    print("\n" + "=" * 100)
    print("Cookie:")
    print("=" * 100)
    cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
    print(f"  {cookie_str[:500]}")

    result = {
        "cookies": cookies,
        "cookie_string": cookie_str,
        "api_endpoints": [{"method": c["method"], "url": c["url"]} for c in data_calls],
        "all_requests": [{"method": c["method"], "url": c["url"]} for c in api_calls],
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完整抓包已写入: {OUTPUT}")


if __name__ == "__main__":
    main()
