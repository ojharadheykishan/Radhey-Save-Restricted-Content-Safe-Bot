import os
import json
import asyncio
from datetime import datetime, timezone

from safe_repo.core.mongo.mongo_client import get_mongo_db, is_mongo_available

STORAGE = os.path.join(os.path.dirname(__file__), "plans_storage.json")

def _read():
    if not os.path.exists(STORAGE):
        return {}
    with open(STORAGE, "r") as f:
        return json.load(f)

def _write(data):
    with open(STORAGE, "w") as f:
        json.dump(data, f)

def _get_collection():
    db = get_mongo_db()
    if db is None:
        return None
    return db["premium_plans"]


async def _mongo_set(user_id, fields):
    coll = _get_collection()
    if coll is None:
        return False
    await coll.update_one(
        {"user_id": str(user_id)},
        {"$set": {"user_id": str(user_id), **fields}},
        upsert=True,
    )
    return True


async def _mongo_unset(user_id, key):
    coll = _get_collection()
    if coll is None:
        return False
    await coll.update_one(
        {"user_id": str(user_id)},
        {"$unset": {key: ""}},
    )
    return True


async def add_premium(user_id, expire_date, plan_type="time_limited"):
    entry = {
        "expire_date": expire_date.isoformat() if hasattr(expire_date, "isoformat") else str(expire_date),
        "plan_type": plan_type,
    }
    # ---- JSON ----
    data = await asyncio.to_thread(_read)
    data[str(user_id)] = entry
    await asyncio.to_thread(_write, data)
    # ---- MongoDB ----
    if is_mongo_available():
        await _mongo_set(user_id, entry)


async def remove_premium(user_id):
    data = await asyncio.to_thread(_read)
    data.pop(str(user_id), None)
    await asyncio.to_thread(_write, data)
    if is_mongo_available():
        coll = _get_collection()
        if coll is not None:
            await coll.delete_one({"user_id": str(user_id)})


from config import OWNER_ID

PREMIUM_USERS = [7453797299, 8175151355, 8552899459]


async def premium_users():
    """Primary: MongoDB + lifetime list. Fallback: JSON + lifetime list."""
    if is_mongo_available():
        coll = _get_collection()
        if coll is not None:
            cursor = coll.find({}, {"_id": 0, "user_id": 1})
            docs = await cursor.to_list(length=10000)
            users = [int(doc["user_id"]) for doc in docs if doc.get("user_id")]
        else:
            data = await asyncio.to_thread(_read)
            users = [int(k) for k in data.keys()]
    else:
        data = await asyncio.to_thread(_read)
        users = [int(k) for k in data.keys()]

    for owner_id in OWNER_ID:
        if owner_id not in users:
            users.append(owner_id)
    for premium_user in PREMIUM_USERS:
        if premium_user not in users:
            users.append(premium_user)
    return users


async def check_premium(user_id):
    # Owner / lifetime-premium shortcut
    if user_id in OWNER_ID or user_id in PREMIUM_USERS:
        return {"_id": user_id, "expire_date": None}

    if is_mongo_available():
        coll = _get_collection()
        if coll is not None:
            doc = await coll.find_one({"user_id": str(user_id)})
            if not doc:
                return None
            try:
                expire = datetime.fromisoformat(doc.get("expire_date")).replace(tzinfo=timezone.utc)
            except Exception:
                expire = None
            return {"_id": int(user_id), "expire_date": expire}

    data = await asyncio.to_thread(_read)
    entry = data.get(str(user_id))
    if not entry:
        return None
    try:
        expire = datetime.fromisoformat(entry.get("expire_date")).replace(tzinfo=timezone.utc)
    except Exception:
        expire = None
    return {"_id": int(user_id), "expire_date": expire}


async def get_lifetime_users():
    users = []
    for owner_id in OWNER_ID:
        if owner_id not in users:
            users.append(owner_id)
    for premium_user in PREMIUM_USERS:
        if premium_user not in users:
            users.append(premium_user)
    return users


async def get_time_limited_users():
    if is_mongo_available():
        coll = _get_collection()
        if coll is not None:
            cursor = coll.find({}, {"_id": 0, "user_id": 1, "expire_date": 1, "plan_type": 1})
            docs = await cursor.to_list(length=10000)
            users = []
            for doc in docs:
                users.append({
                    "user_id": int(doc.get("user_id")),
                    "expire_date": doc.get("expire_date"),
                    "plan_type": doc.get("plan_type", "time_limited"),
                })
            return users

    data = await asyncio.to_thread(_read)
    users = []
    for user_id_str, info in data.items():
        users.append({
            "user_id": int(user_id_str),
            "expire_date": info.get("expire_date"),
            "plan_type": info.get("plan_type", "time_limited"),
        })
    return users


async def get_15_day_users():
    users = await get_time_limited_users()
    return [
        user for user in users
        if user.get("plan_type") in ("15_days", "15_days_trial")
    ]


async def get_1_day_users():
    users = await get_time_limited_users()
    return [user for user in users if user.get("plan_type") == "1_day_trial"]


async def get_all_premium_details():
    lifetime = await get_lifetime_users()
    time_limited = await get_time_limited_users()
    all_users = []
    for uid in lifetime:
        all_users.append({"user_id": uid, "plan_type": "lifetime", "expire_date": None})
    for entry in time_limited:
        all_users.append({
            "user_id": entry["user_id"],
            "plan_type": entry.get("plan_type", "time_limited"),
            "expire_date": entry["expire_date"],
        })
    return all_users


async def check_and_remove_expired_users():
    if is_mongo_available():
        coll = _get_collection()
        if coll is not None:
            now = datetime.now(timezone.utc)
            cursor = coll.find({})
            docs = await cursor.to_list(length=10000)
            removed = []
            for doc in docs:
                try:
                    expire = datetime.fromisoformat(doc.get("expire_date")).replace(tzinfo=timezone.utc)
                    if expire and expire < now:
                        await coll.delete_one({"_id": doc.get("_id")})
                        removed.append(doc.get("user_id"))
                except Exception:
                    continue
            for r in removed:
                print(f"Removed user {r} due to expired plan.")
            return

    data = await asyncio.to_thread(_read)
    now = datetime.now(timezone.utc)
    removed = []
    for k, v in list(data.items()):
        try:
            expire = datetime.fromisoformat(v.get("expire_date")).replace(tzinfo=timezone.utc)
            if expire and expire < now:
                data.pop(k, None)
                removed.append(k)
        except Exception:
            continue
    if removed:
        await asyncio.to_thread(_write, data)
    for r in removed:
        print(f"Removed user {r} due to expired plan.")
