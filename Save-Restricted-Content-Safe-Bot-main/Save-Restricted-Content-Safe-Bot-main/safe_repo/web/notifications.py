import asyncio
import json
import logging
import os
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)
SUBSCRIPTIONS_PATH = Path(__file__).resolve().parent.parent / "core" / "mongo" / "push_subscriptions.json"


def _read_subscriptions():
    if not SUBSCRIPTIONS_PATH.exists():
        return []
    try:
        data = json.loads(SUBSCRIPTIONS_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _write_subscriptions(subscriptions):
    SUBSCRIPTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUBSCRIPTIONS_PATH.write_text(json.dumps(subscriptions, indent=2), encoding="utf-8")


def save_push_subscription(user_id, subscription):
    if not isinstance(subscription, dict):
        return False
    endpoint = str(subscription.get("endpoint") or "")
    parsed = urlparse(endpoint)
    keys = subscription.get("keys") or {}
    if parsed.scheme != "https" or not parsed.hostname or not keys.get("p256dh") or not keys.get("auth"):
        return False
    subscriptions = _read_subscriptions()
    subscriptions = [item for item in subscriptions if item.get("endpoint") != endpoint]
    subscriptions.append({"user_id": str(user_id), "endpoint": endpoint, "subscription": subscription})
    _write_subscriptions(subscriptions)
    return True


def remove_push_subscription(user_id, endpoint):
    subscriptions = _read_subscriptions()
    remaining = [item for item in subscriptions if not (item.get("user_id") == str(user_id) and item.get("endpoint") == endpoint)]
    _write_subscriptions(remaining)
    return len(remaining) != len(subscriptions)


def send_browser_notification(title, url, body="New study media is available"):
    public_key = os.environ.get("VAPID_PUBLIC_KEY", "").strip()
    private_key = os.environ.get("VAPID_PRIVATE_KEY", "").strip()
    claims_email = os.environ.get("VAPID_CLAIMS_EMAIL", "").strip()
    if not public_key or not private_key or not claims_email:
        return 0
    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        logger.warning("pywebpush is not installed; browser notifications are disabled")
        return 0

    payload = json.dumps({"title": title, "body": body, "url": url})
    subscriptions = _read_subscriptions()
    active = []
    delivered = 0
    for item in subscriptions:
        try:
            webpush(
                subscription_info=item["subscription"],
                data=payload,
                vapid_private_key=private_key,
                vapid_claims={"sub": f"mailto:{claims_email}"},
                ttl=3600,
            )
            active.append(item)
            delivered += 1
        except WebPushException as error:
            response = getattr(error, "response", None)
            if response is None or response.status_code not in (404, 410):
                active.append(item)
                logger.warning("Web push delivery failed: %s", error)
        except Exception:
            active.append(item)
            logger.exception("Web push delivery failed")
    if len(active) != len(subscriptions):
        _write_subscriptions(active)
    return delivered


async def notify_new_media(title, url, admin_only=False):
    telegram_ids = [value.strip() for value in os.environ.get("STUDY_ADMIN_TELEGRAM_IDS", "").split(",") if value.strip()]
    if telegram_ids:
        try:
            from safe_repo import app as bot_client

            for raw_chat_id in telegram_ids:
                chat_id = int(raw_chat_id) if raw_chat_id.lstrip("-").isdigit() else raw_chat_id
                try:
                    status = "Media pending admin approval" if admin_only else "New media added"
                    await bot_client.send_message(chat_id, f"{status}: {title}\n{url}")
                except Exception as error:
                    logger.debug("Telegram media notification skipped: %s", error)
        except Exception as error:
            logger.debug("Telegram notifications unavailable: %s", error)
    if admin_only:
        return 0
    return await asyncio.to_thread(send_browser_notification, title, url)
