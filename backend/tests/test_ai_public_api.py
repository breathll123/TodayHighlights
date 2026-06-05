from datetime import datetime

from fastapi.testclient import TestClient

from app.core.database import get_session
from app.models.entities import AITopicSummary, Topic


def test_public_ai_summary_returns_latest_generated_version(client: TestClient) -> None:
    session = next(client.app.dependency_overrides[get_session]())
    topic = Topic(name="股票", slug="stocks", sort_order=1, enabled=True)
    session.add(topic)
    session.flush()
    session.add_all(
        [
            AITopicSummary(topic_id=topic.id, summary_date=datetime(2026, 6, 5), version=1, status="generated", title="旧版", items_json=[{"title": "旧", "reason": "旧内容", "related": [], "risk": "", "source_refs": []}], source_refs_json=[]),
            AITopicSummary(topic_id=topic.id, summary_date=datetime(2026, 6, 5), version=2, status="generated", title="新版", items_json=[{"title": "新", "reason": "新版内容达到长度要求", "related": [], "risk": "", "source_refs": []}], source_refs_json=[]),
        ]
    )
    session.commit()

    response = client.get("/api/public/topics/stocks/ai-summary")

    assert response.status_code == 200
    assert response.json()["title"] == "新版"
    assert response.json()["version"] == 2


def test_public_ai_summary_404_when_missing(client: TestClient) -> None:
    response = client.get("/api/public/topics/stocks/ai-summary")
    assert response.status_code == 404
