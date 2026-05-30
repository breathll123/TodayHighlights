"""获取 A 股龙虎榜数据（按 f178 成交额降序），写入 JSON。"""
import json
import time
from pathlib import Path

import httpx

OUTPUT = Path(__file__).resolve().parent / "longhu_full.json"
FS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
FIELDS = "f2,f3,f8,f12,f14,f152,f174,f175,f176,f177,f178,f179"
HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://data.eastmoney.com/"}


def v(key, item):
    val = item.get(key, 0)
    return float(val) if val is not None and val != "-" else 0


def fetch_all():
    all_items = []
    for p in range(1, 21):  # max 20 pages
        resp = httpx.get(
            "https://push2delay.eastmoney.com/api/qt/clist/get",
            params={"pn": p, "pz": 100, "po": 1, "np": 1, "fltt": 2, "invt": 2, "fid": "f178", "fs": FS, "fields": FIELDS},
            headers=HEADERS, timeout=15,
        )
        items = resp.json()["data"]["diff"]
        longhu_count = sum(1 for i in items if i.get("f152") == 2)
        all_items.extend(items)
        print(f"  page {p}  got {len(items)}  f152=2: {longhu_count}")
        if longhu_count == 0:  # no more longhu stocks
            break
        time.sleep(0.5)

    # Filter f152=2
    longhu = [i for i in all_items if i.get("f152") == 2]
    longhu.sort(key=lambda x: abs(v("f178", x)), reverse=True)

    print(f"\n龙虎榜上榜: {len(longhu)} 只\n")
    print("=" * 100)

    for i in longhu:
        name = i["f14"]
        code = i["f12"]
        pct = v("f3", i)
        f174 = v("f174", i) / 1e8
        f176 = v("f176", i) / 1e8
        f178 = abs(v("f178", i)) / 1e8
        print(f"  {name}({code})  {pct:+.2f}%  换手{i.get('f8',0)}%")
        print(f"    f174={f174:+.1f}亿  f176={f176:+.1f}亿  f178={f178:+.1f}亿")
        print(f"    f175={i.get('f175','?')}%  f177={i.get('f177','?')}%  f179={i.get('f179','?')}%")
        print()

    # Also save raw A-share data for the non-longhu items (for comparison)
    raw = sorted(all_items, key=lambda x: abs(v("f178", x)), reverse=True)
    OUTPUT.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"全量 {len(raw)} 条已写入: {OUTPUT}  ({OUTPUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    fetch_all()
