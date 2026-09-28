import json

import safe_repo.web.notifications as notifications
from app import app as flask_app


def test_push_subscription_is_validated_and_removable(tmp_path, monkeypatch):
    monkeypatch.setattr(notifications, "SUBSCRIPTIONS_PATH", tmp_path / "subscriptions.json")
    subscription = {
        "endpoint": "https://push.example.test/send/123",
        "keys": {"p256dh": "public-key", "auth": "auth-key"},
    }

    assert notifications.save_push_subscription("learner-1", subscription)
    stored = json.loads(notifications.SUBSCRIPTIONS_PATH.read_text(encoding="utf-8"))
    assert stored[0]["user_id"] == "learner-1"
    assert not notifications.save_push_subscription("learner-1", {**subscription, "endpoint": "http://localhost/push"})
    assert notifications.remove_push_subscription("learner-1", subscription["endpoint"])
    assert json.loads(notifications.SUBSCRIPTIONS_PATH.read_text(encoding="utf-8")) == []


def test_browser_push_is_a_noop_without_vapid_configuration(monkeypatch):
    monkeypatch.delenv("VAPID_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("VAPID_CLAIMS_EMAIL", raising=False)

    assert notifications.send_browser_notification("New lesson", "/study") == 0


def test_admin_session_can_register_browser_push(tmp_path, monkeypatch):
    monkeypatch.setattr(notifications, "SUBSCRIPTIONS_PATH", tmp_path / "subscriptions.json")
    client = flask_app.test_client()
    with client.session_transaction() as session:
        session["is_admin"] = True
        session["admin_role"] = "owner"

    status = client.get("/api/auth/status")
    response = client.post("/api/push/subscribe", json={
        "subscription": {
            "endpoint": "https://push.example.test/send/admin",
            "keys": {"p256dh": "public-key", "auth": "auth-key"},
        },
    })

    assert status.get_json()["authenticated"] is True
    assert response.status_code == 200
    stored = json.loads(notifications.SUBSCRIPTIONS_PATH.read_text(encoding="utf-8"))
    assert stored[0]["user_id"] == "admin_owner"
