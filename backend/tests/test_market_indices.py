from app.services.adapters import eastmoney


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
