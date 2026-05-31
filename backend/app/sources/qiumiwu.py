from datetime import datetime
from hashlib import sha256

import httpx

from app.core.config import SH_TZ
from app.sources.base import RawItemDraft

_headers = {
    "User-Agent": "Mozilla/5.0 DailyHighlights/0.1",
    "Accept": "application/json",
    "Referer": "https://www.qiumiwu.com/",
}


class QiumiwuAdapter:

    def fetch(self, entry_url: str, cookie: str) -> list[RawItemDraft]:
        subtype = entry_url.replace("qiumiwu://", "") if entry_url.startswith("qiumiwu://") else ""
        handler = {
            "matches": self._fetch_matches,
        }.get(subtype)
        if handler is None:
            return []
        return handler(subtype)

    def _fetch_matches(self, subtype: str) -> list[RawItemDraft]:
        resp = httpx.get(
            "https://api.qiumiwu.com/v5/game/schedule/0/1/0/0/0",
            params={"reqfrom": "web"},
            headers=_headers,
            timeout=20,
            follow_redirects=True,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("error") != 0:
            return []

        matches = data.get("data", {}).get("list", []) or []
        drafts = []
        for m in matches:
            league = m.get("league", {})
            home = m.get("home", {})
            away = m.get("away", {})
            match_id = m.get("id", "")
            status = m.get("status", 0)
            start_ts = m.get("start_time", 0)
            scores = m.get("scores", [])

            home_score = str(scores[0][0]) if scores and scores[0] else ""
            away_score = str(scores[0][1]) if scores and scores[0] else ""

            title = f"{home.get('name', '?')} vs {away.get('name', '?')}"
            body = f"{league.get('name','')} · {m.get('status_name','')} · {home.get('name','?')} {home_score}-{away_score} {away.get('name','?')}"

            league_name = league.get("name", "")
            home_name = home.get("name", "")
            away_name = away.get("name", "")
            published_at = datetime.fromtimestamp(start_ts, tz=SH_TZ).replace(tzinfo=None) if start_ts else None

            # external_id: time + league + matchup for stable dedup
            ext_id = f"qmw_{start_ts}_{league_name}_{home_name}_{away_name}"
            # content_hash: includes score + status so score changes trigger updates
            content_str = f"qmw|{match_id}|{status}|{home_score}-{away_score}|{start_ts}|{league_name}|{home_name}|{away_name}"

            drafts.append(RawItemDraft(
                external_id=ext_id,
                url=f"https://www.qiumiwu.com/game/{match_id}",
                author=league_name,
                title=title,
                body=body,
                published_at=published_at,
                metrics={
                    "league": league_name,
                    "status": status,
                    "status_name": m.get("status_name", ""),
                    "team_a": home_name,
                    "team_b": away_name,
                    "score_a": home_score,
                    "score_b": away_score,
                    "start_time": start_ts,
                    "stage": m.get("stage", ""),
                    "priority": 0,
                },
                content_hash=sha256(content_str.encode()).hexdigest(),
            ))

        return drafts
