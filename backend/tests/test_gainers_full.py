"""获取沪深A股全量涨幅榜数据，分页拉取后写入 JSON 文件。"""
import json
import time
from pathlib import Path

import httpx

OUTPUT = Path(__file__).resolve().parent / "gainers_full.json"
PAGE_SIZE = 100
FS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
FIELDS = "f2,f3,f4,f8,f9,f10,f12,f14,f20"
HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}


def fetch_all():
    # 第一页拿 total
    resp = httpx.get(
        "https://push2delay.eastmoney.com/api/qt/clist/get",
        params={"pn": 1, "pz": 1, "po": 1, "np": 1, "fltt": 2, "invt": 2, "fid": "f3", "fs": FS, "fields": FIELDS},
        headers=HEADERS, timeout=15,
    )
    total = resp.json()["data"]["total"]
    pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    print(f"total={total}  pages={pages}  page_size={PAGE_SIZE}")

    all_items = []
    for p in range(1, pages + 1):
        resp = httpx.get(
            "https://push2delay.eastmoney.com/api/qt/clist/get",
            params={"pn": p, "pz": PAGE_SIZE, "po": 1, "np": 1, "fltt": 2, "invt": 2, "fid": "f3", "fs": FS, "fields": FIELDS},
            headers=HEADERS, timeout=15,
        )
        items = resp.json()["data"]["diff"]
        all_items.extend(items)
        print(f"  page {p}/{pages}  got {len(items)}  total={len(all_items)}")
        if p < pages:
            time.sleep(1.5)

    # 按涨跌幅排好
    all_items.sort(key=lambda x: float(x["f3"]) if isinstance(x.get("f3"), (int, float)) and x.get("f3") != "-" else 0, reverse=True)

    # 统计
    sh = sum(1 for i in all_items if i["f12"].startswith(("60", "68")))
    sz = sum(1 for i in all_items if i["f12"].startswith(("00", "30")))
    print(f"\n沪市: {sh}  深市: {sz}  合计: {len(all_items)}")

    # 写文件
    OUTPUT.write_text(json.dumps(all_items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已写入: {OUTPUT}  ({OUTPUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    fetch_all()
