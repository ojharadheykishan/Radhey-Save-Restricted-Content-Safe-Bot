import os
import json
import asyncio
from datetime import datetime, timezone

STORAGE = os.path.join(os.path.dirname(__file__), "plans_storage.json")

def _read():
    if not os.path.exists(STORAGE):
        return {}
    with open(STORAGE, "r") as f:
        return json.load(f)

def _write(data):
    with open(STORAGE, "w") as f:
        json.dump(data, f)

async def add_premium(user_id, expire_date, plan_type="time_limited"):
    data = await asyncio.to_thread(_read)
    data[str(user_id)] = {
        "expire_date": expire_date.isoformat() if hasattr(expire_date, 'isoformat') else str(expire_date),
        "plan_type": plan_type,
    }
    await asyncio.to_thread(_write, data)

async def remove_premium(user_id):
    data = await asyncio.to_thread(_read)
    data.pop(str(user_id), None)
    await asyncio.to_thread(_write, data)

from config import OWNER_ID

# List of users with lifetime premium access
PREMIUM_USERS = [7453797299, 8175151355, 8552899459]

async def premium_users():
    data = await asyncio.to_thread(_read)
    users = [int(k) for k in data.keys()]
    # Add owner and premium users to premium users list if not already present (lifetime premium)
    for owner_id in OWNER_ID:
        if owner_id not in users:
            users.append(owner_id)
    for premium_user in PREMIUM_USERS:
        if premium_user not in users:
            users.append(premium_user)
    return users

async def check_premium(user_id):
    data = await asyncio.to_thread(_read)
    entry = data.get(str(user_id))
    
    # Check if user is owner or in premium users list - if yes, return permanent premium
    if user_id in OWNER_ID or user_id in PREMIUM_USERS:
        return {"_id": user_id, "expire_date": None}  # None indicates lifetime premium
    
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
