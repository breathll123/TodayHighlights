from app.services.adapters import qiumiwu
from app.services.adapters.qiumiwu import set_media_cache


class _FakeMediaCache:
    def __init__(self) -> None:
        self.calls = []

    def cache_remote_image(self, url: str, **kwargs) -> str:
        self.calls.append((url, kwargs))
        return f"/api/public/media/local-{len(self.calls)}"


class _ScheduleResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "error": 0,
            "data": {
                "list": [
                    {
                        "id": "100",
                        "league": {"name": "英超", "logo": "https://file.qiumiwu.com/league/epl.png"},
                        "home": {"name": "阿森纳", "logo": "https://file.qiumiwu.com/team/arsenal.png"},
                        "away": {"name": "切尔西", "logo": "https://file.qiumiwu.com/team/chelsea.png"},
                        "status": 1,
                        "status_name": "未开赛",
                        "start_time": 1780000000,
                        "scores": [[], []],
                    }
                ]
            },
        }


def test_fetch_matches_adds_local_logo_paths(monkeypatch) -> None:
    def fake_get(*args, **kwargs):
        return _ScheduleResponse()

    monkeypatch.setattr(qiumiwu.httpx, "get", fake_get)
    media_cache = _FakeMediaCache()
    set_media_cache(media_cache)

    qiumiwu.fetch_matches.cache_clear()
    matches = qiumiwu.fetch_matches({}, 10)

    assert matches[0]["logo_league_local"] == "/api/public/media/local-1"
    assert matches[0]["logo_a_local"] == "/api/public/media/local-2"
    assert matches[0]["logo_b_local"] == "/api/public/media/local-3"
    assert media_cache.calls[1][1]["entity_type"] == "team"
    assert media_cache.calls[1][1]["entity_name"] == "阿森纳"
