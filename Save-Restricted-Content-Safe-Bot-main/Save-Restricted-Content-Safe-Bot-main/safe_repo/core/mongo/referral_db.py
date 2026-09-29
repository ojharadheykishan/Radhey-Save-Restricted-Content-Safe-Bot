"""Referral Program — referral codes for premium access."""
import os
import json
import asyncio
import secrets
import string
from datetime import datetime, timezone, timedelta

from safe_repo.core.mongo.mongo_client import get_mongo_db, is_mongo_available

STORAGE = os.path.join(os.path.dirname(__file__), "referrals.json")


def _read():
    if not os.path.exists(STORAGE):
        return {}
    try:
        with open(STORAGE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _write(data):
    try:
        with open(STORAGE, "w") as f:
            json.dump(data, f, default=str)
    except Exception:
        pass


def _get_coll():
    db = get_mongo_db()
    if db is None:
        return None
    return db["referrals"]


def _serialize(doc):
    if doc is None:
        return None
    doc = dict(doc)
    doc.pop("_id", None)
    return doc


def _generate_code(length=8):
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))


async def create_referral_code(user_id):
    """Create a unique referral code for a user."""
    user_id = str(user_id)
    code = _generate_code()
    entry = {
        "user_id": user_id,
        "code": code,
        "created_at": datetime.now(timezone.utc),
        "used_by": [],
        "uses": 0,
    }
    # JSON
    data = await asyncio.to_thread(_read)
    data[code] = entry
    await asyncio.to_thread(_write, data)
    # MongoDB
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            await coll.update_one(
                {"code": code},
                {"$set": entry},
                upsert=True,
            )
    return code


async def use_referral_code(user_id, code):
    """Mark a referral code as used by a user."""
    user_id = str(user_id)
    code = code.upper()

    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            doc = await coll.find_one({"code": code})
            if not doc:
                return {"success": False, "reason": "code_not_found"}
            if user_id in doc.get("used_by", []):
                return {"success": False, "reason": "already_used"}
            await coll.update_one(
                {"code": code},
                {
                    "$addToSet": {"used_by": user_id},
                    "$inc": {"uses": 1},
                    "$set": {"last_used": datetime.now(timezone.utc), "used_by_user": user_id},
                },
            )
            return {"success": True, "referrer": doc.get("user_id")}

    data = await asyncio.to_thread(_read)
    entry = data.get(code)
    if not entry:
        return {"success": False, "reason": "code_not_found"}
    if user_id in entry.get("used_by", []):
        return {"success": False, "reason": "already_used"}
    entry.setdefault("used_by", []).append(user_id)
    entry["uses"] = entry.get("uses", 0) + 1
    entry["last_used"] = datetime.now(timezone.utc).isoformat()
    entry["used_by_user"] = user_id
    await asyncio.to_thread(_write, data)
    return {"success": True, "referrer": entry.get("user_id")}


async def get_referrer_stats(user_id):
    """Return stats for a referrer (number of successful referrals)."""
    user_id = str(user_id)
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            cursor = coll.find({"user_id": user_id})
            docs = await cursor.to_list(length=1000)
            total_uses = sum(d.get("uses", 0) for d in docs)
            return {
                "user_id": user_id,
                "codes": [_serialize(d) for d in docs],
                "total_referrals": total_uses,
            }

    data = await asyncio.to_thread(_read)
    user_entries = [v for v in data.values() if v.get("user_id") == user_id]
    total_uses = sum(e.get("uses", 0) for e in user_entries)
    return {
        "user_id": user_id,
        "codes": user_entries,
        "total_referrals": total_uses,
    }


async def list_user_refs(user_id):
    """List all referral codes created by a user."""
    user_id = str(user_id)
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            cursor = coll.find({"user_id": user_id})
            docs = await cursor.to_list(length=1000)
            return [_serialize(d) for d in docs]

    data = await asyncio.to_thread(_read)
    return [v for v in data.values() if v.get("user_id") == user_id]


def _run_async(coro):
    """Sync wrapper for Flask route usage."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()