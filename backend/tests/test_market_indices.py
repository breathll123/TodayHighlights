import logging

import pytest

from app.services.adapters import eastmoney
from app.sources import eastmoney as source_eastmoney


class _TrendResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "data": {
                "preClose": 3000,
                "trends": [
                    "2026-06-08 09:30,3000,3005,3010,2998,100,200,3003",
                    "2026-06-08 09:31,3005,3004,3008,2990,100,200,3004",
                ],
            }
        }


class _SinaResponse:
    status_code = 200

    def raise_for_status(self) -> None:
        return None

    @property
    def content(self) -> bytes:
        return (
            b'var hq_str_s_sh000001="\xc9\xcf\xd6\xa4\xd6\xb8\xca\xfd,4031.51,44.50,1.12,743131092,1537401519424.7";\n'
            b'var hq_str_s_sz399001="\xc9\xee\xd6\xa4\xb3\xc9\xd6\xb8,14963.41,111.43,0.75,792336422,167754822";\n'
            b'var hq_str_s_sz399006="\xb4\xb4\xd2\xb5\xb0\xe5\xd6\xb8,3830.35,19.11,0.50,43564051,34726190";\n'
            b'var hq_str_s_sh000688="\xbf\xc6\xb4\xb450,1663.22,0.79,0.05,210185,17582024";\n'
            b'var hq_str_s_sz399673="\xb4\xb4\xd2\xb5\xb0\xe550,4123.73,19.57,0.48,30774295,27477932";\n'
            b'var hq_str_s_sh000300="\xbb\xa6\xc9\xee300,4777.32,54.91,1.16,3359220,87147733";\n'
        )


class _IndexResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "data": {
                "diff": [
                    {
                        "f2": 4031.51,
                        "f3": 1.12,
                        "f4": 44.5,
                        "f5": 743131092,
                        "f6": 1537401519424.7,
                        "f12": "000001",
                        "f13": 1,
                        "f14": "上证指数",
                    }
                ]
            }
        }


class _LonghuDatacenterResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "success": True,
            "result": {
                "data": [
                    {
                        "TRADE_DATE": "2026-06-15 00:00:00",
                        "TRADE_ID": 100348255,
                        "SECURITY_CODE": "301526",
                        "SECURITY_NAME_ABBR": "国际复材",
                        "CLOSE_PRICE": 34.13,
                        "CHANGE_RATE": 20.007,
                        "TURNOVERRATE": 13.5605,
                        "BILLBOARD_DEAL_AMT": 2327447269.88,
                        "BILLBOARD_BUY_AMT": 1298112313.51,
                        "BILLBOARD_SELL_AMT": 1029334956.37,
                        "BILLBOARD_NET_AMT": 268777357.14,
                        "DEAL_AMOUNT_RATIO": 37.8615,
                        "FREE_MARKET_CAP": 47931930461.99,
                        "EXPLANATION": "日涨幅达到15%的前5只证券",
                        "EXPLAIN": "4家机构买入，成功率35.09%",
                        "D1_CLOSE_ADJCHRATE": None,
                        "D2_CLOSE_ADJCHRATE": None,
                        "D5_CLOSE_ADJCHRATE": None,
                        "D10_CLOSE_ADJCHRATE": None,
                    },
                    {
                        "TRADE_DATE": "2026-06-14 00:00:00",
                        "TRADE_ID": 100348100,
                        "SECURITY_CODE": "000001",
                        "SECURITY_NAME_ABBR": "旧交易日",
                        "BILLBOARD_NET_AMT": 999999999,
                    },
                ]
            },
        }


def test_fetch_one_trend_uses_intraday_high_low_fields(monkeypatch) -> None:
    def fake_get(*args, **kwargs):
        return _TrendResponse()

    monkeypatch.setattr(eastmoney._http, "get", fake_get)

    trend = eastmoney._fetch_one_trend({"em_secid": "1.000001"})

    assert trend is not None
    assert trend["high"] == 3010
    assert trend["low"] == 2990
    assert trend["points"] == [
        {"time": "09:30", "price": 3005.0},
        {"time": "09:31", "price": 3004.0},
    ]


def test_fetch_indices_uses_eastmoney_delay_snapshot_api(monkeypatch, caplog) -> None:
    caplog.set_level(logging.INFO)

    def fake_get(url, *, params=None, **kwargs):
        assert url == "https://push2delay.eastmoney.com/api/qt/ulist.np/get"
        assert params["secids"].startswith("1.000001,0.399001")
        assert params["fields"] == "f2,f3,f4,f5,f6,f12,f13,f14"
        return _IndexResponse()

    eastmoney.fetch_indices.cache_clear()
    monkeypatch.setattr(eastmoney._http, "get", fake_get)

    result = eastmoney.fetch_indices({}, 6)

    assert len(result) == 1
    first = result[0]
    assert first["title"] == "上证指数"
    assert first["current"] == 4031.51
    assert first["percent"] == 1.12
    assert first["symbols"] == ["000001"]
    assert first["source"] == "eastmoney_indices"
    assert first["em_secid"] == "1.000001"
    event = next(
        record
        for record in caplog.records
        if getattr(record, "event", "") == "upstream.completed"
    )
    assert event.event_fields["provider"] == "eastmoney"
    assert event.event_fields["operation"] == "indices"


def test_fetch_indices_labels_transport_failure_as_request_stage(monkeypatch, caplog) -> None:
    caplog.set_level(logging.INFO)

    def fail_get(*args, **kwargs):
        raise TimeoutError("offline")

    eastmoney.fetch_indices.cache_clear()
    monkeypatch.setattr(eastmoney._http, "get", fail_get)

    assert eastmoney.fetch_indices({}, 6) == []

    adapter_event = next(
        record
        for record in caplog.records
        if getattr(record, "event", "") == "adapter.failed"
    )
    assert adapter_event.event_fields["provider"] == "eastmoney"
    assert adapter_event.event_fields["operation"] == "indices"
    assert adapter_event.event_fields["stage"] == "request"


def test_source_indices_use_eastmoney_snapshot_api(monkeypatch) -> None:
    def fail_sina_request(*args, **kwargs):
        raise AssertionError("source index snapshots must not use hq.sinajs.cn")

    def fake_push2_get(path: str, params: dict):
        assert path == "/api/qt/ulist.np/get"
        assert params["secids"].startswith("1.000001,0.399001")
        return _IndexResponse()

    monkeypatch.setattr(source_eastmoney.httpx, "get", fail_sina_request)
    monkeypatch.setattr(source_eastmoney, "_push2_get", fake_push2_get)

    drafts = source_eastmoney.EastmoneyAdapter().fetch("eastmoney://indices", "")

    assert len(drafts) == 1
    assert drafts[0].title == "上证指数"
    assert drafts[0].body == "4031.51 +1.12%"
    assert drafts[0].metrics == {
        "percent": 1.12,
        "current": 4031.51,
        "change_amount": 44.5,
        "volume": 743131092,
        "turnover": 1537401519424.7,
        "subtype": "indices",
        "symbol": "000001",
    }


def test_source_longhu_uses_datacenter_detail_api(monkeypatch) -> None:
    def fake_datacenter_get():
        return _LonghuDatacenterResponse()

    def fail_push2_get(*args, **kwargs):
        raise AssertionError("datacenter success must not use push2 fallback")

    monkeypatch.setattr(source_eastmoney, "_datacenter_longhu_get", fake_datacenter_get)
    monkeypatch.setattr(source_eastmoney, "_push2_get", fail_push2_get)

    drafts = source_eastmoney.EastmoneyAdapter().fetch("eastmoney://longhu", "")

    assert len(drafts) == 1
    assert drafts[0].external_id == "lhb_2026-06-15_100348255"
    assert drafts[0].title == "国际复材"
    assert drafts[0].published_at.isoformat() == "2026-06-15T00:00:00"
    assert drafts[0].metrics["net_amount"] == 268777357.14
    assert drafts[0].metrics["net_buy"] == 268777357.14
    assert drafts[0].metrics["reason"] == "日涨幅达到15%的前5只证券"
    assert drafts[0].metrics["billboard_deal_amount"] == 2327447269.88
    assert drafts[0].metrics["free_market_cap"] == 47931930461.99


def test_source_longhu_does_not_fall_back_to_incorrect_push2_data(monkeypatch) -> None:
    def fail_datacenter_get():
        raise TimeoutError("datacenter unavailable")

    def fail_push2_get(*args, **kwargs):
        raise AssertionError("longhu must not fall back to push2")

    monkeypatch.setattr(source_eastmoney, "_datacenter_longhu_get", fail_datacenter_get)
    monkeypatch.setattr(source_eastmoney, "_push2_get", fail_push2_get)

    with pytest.raises(TimeoutError, match="datacenter unavailable"):
        source_eastmoney.EastmoneyAdapter().fetch("eastmoney://longhu", "")
