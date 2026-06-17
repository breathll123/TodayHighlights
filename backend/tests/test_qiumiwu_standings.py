from app.services.adapters.qiumiwu import _sort_standings


def test_sort_standings_uses_fixed_league_order() -> None:
    items = [
        {"league": "中超", "rank": 1, "team": "上海申花"},
        {"league": "西甲", "rank": 2, "team": "巴萨"},
        {"league": "英超", "rank": 1, "team": "阿森纳"},
        {"league": "西甲", "rank": 1, "team": "皇马"},
    ]

    sorted_items = _sort_standings(items)

    assert [(item["league"], item["rank"]) for item in sorted_items] == [
        ("英超", 1),
        ("西甲", 1),
        ("西甲", 2),
        ("中超", 1),
    ]
