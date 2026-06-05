from fastapi.testclient import TestClient


def test_create_ai_model_encrypts_key_and_hides_secret(client: TestClient) -> None:
    response = client.post(
        "/api/admin/ai-models",
        json={
            "name": "DeepSeek 默认",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "api_key": "secret-key",
            "is_default": True,
            "enabled": True,
            "notes": "stocks",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "DeepSeek 默认"
    assert data["has_api_key"] is True
    assert "api_key" not in data


def test_only_one_default_ai_model(client: TestClient) -> None:
    first = client.post(
        "/api/admin/ai-models",
        json={"name": "A", "base_url": "https://a.example/v1", "model": "a", "api_key": "a", "is_default": True, "enabled": True, "notes": ""},
    )
    second = client.post(
        "/api/admin/ai-models",
        json={"name": "B", "base_url": "https://b.example/v1", "model": "b", "api_key": "b", "is_default": True, "enabled": True, "notes": ""},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    listed = client.get("/api/admin/ai-models").json()
    defaults = [item["name"] for item in listed if item["is_default"]]
    assert defaults == ["B"]
