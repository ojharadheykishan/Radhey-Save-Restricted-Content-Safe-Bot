import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app as flask_app
import safe_repo.web.ai as ai_module


def test_ai_page_is_disabled_without_provider_config(monkeypatch):
    monkeypatch.delenv("AI_API_BASE_URL", raising=False)
    monkeypatch.delenv("AI_MODEL", raising=False)
    monkeypatch.setenv("AI_API_KEY", "must-not-be-rendered")

    response = flask_app.test_client().get("/ai")

    assert response.status_code == 200
    assert b"currently unavailable" in response.data
    assert b"must-not-be-rendered" not in response.data


def test_ai_page_requires_strong_session_secret(monkeypatch):
    monkeypatch.setenv("AI_API_BASE_URL", "https://ai.example/v1")
    monkeypatch.setenv("AI_MODEL", "study-model")
    monkeypatch.setenv("FLASK_SECRET_KEY", "weak")

    response = flask_app.test_client().get("/ai")

    assert response.status_code == 200
    assert b"currently unavailable" in response.data


def test_logged_in_user_gets_ai_form_without_provider_key_exposure(monkeypatch):
    monkeypatch.setenv("AI_API_BASE_URL", "https://ai.example/v1")
    monkeypatch.setenv("AI_API_KEY", "private-provider-key")
    monkeypatch.setenv("AI_MODEL", "study-model")
    monkeypatch.setenv("FLASK_SECRET_KEY", "s" * 48)
    client = flask_app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = "ai-test-page"

    response = client.get("/ai")

    assert response.status_code == 200
    assert b"Your question" in response.data
    assert b"I agree to send this question" in response.data
    assert b"private-provider-key" not in response.data


def test_ai_chat_requires_login_and_consent(monkeypatch):
    monkeypatch.setenv("FLASK_SECRET_KEY", "t" * 48)
    monkeypatch.setenv("AI_API_BASE_URL", "https://ai.example/v1")
    monkeypatch.setenv("AI_MODEL", "study-model")
    client = flask_app.test_client()

    unauthenticated = client.post("/api/ai/chat", json={"question": "Hello", "consent": True})
    with client.session_transaction() as session:
        session["user_id"] = "ai-test-consent"
    no_consent = client.post("/api/ai/chat", json={"question": "Hello"})
    malformed = client.post("/api/ai/chat", json=["not", "an object"])

    assert unauthenticated.status_code == 401
    assert no_consent.status_code == 400
    assert malformed.status_code == 400


def test_ai_chat_sends_only_the_consented_question_without_persisting_it(monkeypatch):
    monkeypatch.setenv("FLASK_SECRET_KEY", "t" * 48)
    monkeypatch.setenv("AI_API_BASE_URL", "https://ai.example/v1")
    monkeypatch.setenv("AI_API_KEY", "test-key")
    monkeypatch.setenv("AI_MODEL", "study-model")
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "Study answer"}}]}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr(ai_module.requests, "post", fake_post)
    client = flask_app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = "ai-test-private-question"

    response = client.post("/api/ai/chat", json={
        "question": "Explain gravity",
        "consent": True,
        "profile": {"email": "private@example.com"},
        "watch_history": ["private-video-token"],
    })

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert captured["url"] == "https://ai.example/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert [message["content"] for message in captured["json"]["messages"]][-1] == "Explain gravity"
    assert "private@example.com" not in str(captured["json"])
    assert "private-video-token" not in str(captured["json"])
    assert "Explain gravity" not in str(ai_module._request_times)


def test_ai_chat_limits_question_length_and_requests(monkeypatch):
    monkeypatch.setenv("FLASK_SECRET_KEY", "t" * 48)
    monkeypatch.setenv("AI_API_BASE_URL", "https://ai.example/v1")
    monkeypatch.setenv("AI_MODEL", "study-model")
    client = flask_app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = "ai-test-limit"

    too_long = client.post("/api/ai/chat", json={"question": "x" * 2001, "consent": True})
    assert too_long.status_code == 400

    monkeypatch.setattr(ai_module, "MAX_REQUESTS_PER_HOUR", 0)
    limited = client.post("/api/ai/chat", json={"question": "Hello", "consent": True})
    assert limited.status_code == 429