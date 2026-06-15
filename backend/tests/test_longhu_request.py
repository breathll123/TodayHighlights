"""
龙虎榜请求 + 全量结果测试

直接调用东方财富 push2 API，展示请求参数和完整返回数据。
"""

import json
import httpx


def fetch_longhu_full(limit: int = 20, date_str: str = "2026-06-16") -> list[dict]:
    """获取龙虎榜全量数据 — 东方财富 push2delay API

    date_str: 日期过滤，格式 YYYY-MM-DD（通过 f190 日期字段筛选）
    """
    url = "https://push2delay.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": 1,
        "pz": limit,
        "po": 1,
        "np": 1,
        "fltt": 2,
        "invt": 2,
        "fid": "f178",
        "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
        "fields": "f2,f3,f6,f8,f12,f14,f152,f174,f175,f176,f177,f178,f179,f190",
    }

    print(f"请求日期: {date_str}")
    print("=" * 70)

    print("=" * 70)
    print("请求参数:")
    print(f"  URL: {url}")
    print(f"  params: {json.dumps(params, indent=2)}")
    print()

    resp = httpx.get(
        url,
        params=params,
        headers={
            "User-Agent": "Mozilla/5.0 TodayHighlights/0.1",
            "Referer": "https://quote.eastmoney.com/",
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    # 打印全量原始返回（格式化）
    print("全量原始返回（data.diff）:")
    diff = data.get("data", {}).get("diff", [])
    print(json.dumps(diff, ensure_ascii=False, indent=2))
    print()

    # f190 是交易日偏移（0=今天, 3=3个交易日前），跳过非交易日
    # 不做日期过滤，展示全部数据并附带 f190 值方便自行筛选
    filtered = [item for item in diff if item.get("f152") == 2]
    print(f"  API 返回 {len(diff)} 条，龙虎榜(f152=2) 共 {len(filtered)} 条")
    print(f"  f190 含义: 0=最近交易日, 3=3个交易日前（跳过周末）")

    # 字段映射说明
    print()
    print("=" * 70)
    print("字段映射表:")
    field_map = {
        "f2": "最新价",
        "f3": "涨跌幅(%)",
        "f6": "成交额(元)",
        "f8": "换手率(%)",
        "f12": "股票代码",
        "f14": "股票名称",
        "f152": "上榜类型 (2=龙虎榜)",
        "f174": "买方金额(元)",
        "f175": "买方占比(%)",
        "f176": "卖方金额(元)",
        "f177": "卖方占比(%)",
        "f178": "净买额(元) — 正=净买入, 负=净卖出",
        "f179": "买入占总成交比(%)",
        "f190": "上榜日期偏移 (0=今天, 3=3天前)",
    }
    for key, label in sorted(field_map.items()):
        print(f"  {key:6s} = {label}")

    # 解析为业务对象
    print()
    print("=" * 70)
    print(f"解析结果（{date_str}，共 {len(filtered)} 条）:")
    print()

    for i, item in enumerate(filtered):
        code = item.get("f12", "?")
        name = item.get("f14", "?")
        change_pct = item.get("f3", 0)
        trade_amt = abs(item.get("f6", 0) or 0) / 1e8     # f6 = 成交额
        buy_amt = abs(item.get("f174", 0) or 0) / 1e8
        sell_amt = abs(item.get("f176", 0) or 0) / 1e8
        net_buy = (item.get("f178", 0) or 0) / 1e8         # f178 = 净买额(正=净买,负=净卖)
        buy_pct = item.get("f175", 0)
        sell_pct = item.get("f177", 0)

        f190 = item.get("f190", "?")
        print(f"  #{i+1} {name}({code}) 涨跌{change_pct:+.2f}%  f190={f190}")
        print(f"       成交{trade_amt:.1f}亿  净买{net_buy:+.1f}亿  买入{buy_amt:.1f}亿({buy_pct:.1f}%)  卖出{sell_amt:.1f}亿({sell_pct:.1f}%)")
        print()

    return diff


if __name__ == "__main__":
    import sys
    date = sys.argv[1] if len(sys.argv) > 1 else "2026-06-16"
    print(f"龙虎榜 {date} 请求 + 全量结果 测试")
    print("=" * 70)
    fetch_longhu_full(100, date_str=date)
