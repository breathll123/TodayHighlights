from fastapi.testclient import TestClient


def test_public_topics_route_returns_empty_list(client: TestClient) -> None:
    response = client.get("/api/public/topics")
    assert response.status_code == 200
    assert response.json() == []


def test_public_highlights_route_returns_empty_list(client: TestClient) -> None:
    response = client.get("/api/public/highlights")
    assert response.status_code == 200
    assert response.json() == []


def test_health_reports_cache_backend(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "cache": "memory"}
