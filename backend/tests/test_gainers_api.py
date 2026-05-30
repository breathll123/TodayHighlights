"""测试东方财富涨幅榜 API，打印返回的原始数据和字段映射。"""
import httpx


def test_gainers():
    resp = httpx.get(
        "https://push2delay.eastmoney.com/api/qt/clist/get",
        params={
            "pn": 1, "pz": 6000, "po": 1, "np": 1, "fltt": 2, "invt": 2, "fid": "f3",
            "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
            "fields": "f2,f3,f4,f12,f14,f20,f8,f9,f10,f15,f16,f17,f18",
        },
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"},
        timeout=15,
    )

    data = resp.json()
    print(data["data"])
    items = data["data"]["diff"]

    sh = [i for i in items if i["f12"].startswith(("60", "68"))]
    sz = [i for i in items if i["f12"].startswith(("00", "30"))]
    bj = [i for i in items if i["f12"].startswith(("92"))]


    print(f"rc={data['rc']}  total={data['data']['total']}  returned={len(items)}")
    print(f"沪市: {len(sh)}  深市: {len(sz)}")
    print()

    # 字段说明
    print("字段映射:")
    print("  f2=当前价  f3=涨跌幅%  f4=涨跌额  f8=换手率%  f9=市盈率(动态)")
    print("  f10=量比  f12=代码  f14=名称  f15=最高  f16=最低")
    print("  f17=开盘  f18=昨收  f20=总市值")
    print()

    header = f"{'名称':<10s} {'代码':<8s} {'当前价':>8s} {'涨跌幅':>8s} {'换手':>6s} {'市盈率':>8s} {'市值(亿)':>10s}"
    print(header)
    print("-" * len(header))

    for i in items:
        name = i["f14"]
        code = i["f12"]
        price = f"{i['f2']:.2f}"
        pct = f"{i['f3']:+.2f}%"
        turnover = f"{i.get('f8', 0):.1f}%" if i.get("f8") else "-"
        pe = f"{i.get('f9', 0):.1f}" if i.get("f9") and i.get("f9") > 0 else "-"
        cap = f"{i.get('f20', 0) / 1e8:.0f}亿" if i.get("f20") else "-"
        print(f"{name:<10s} {code:<8s} {price:>8s} {pct:>8s} {turnover:>6s} {pe:>8s} {cap:>10s}")


if __name__ == "__main__":
    test_gainers()
