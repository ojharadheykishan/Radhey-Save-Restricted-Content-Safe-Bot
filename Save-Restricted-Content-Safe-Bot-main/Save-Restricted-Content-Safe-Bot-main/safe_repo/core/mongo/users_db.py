import os
import json
import asyncio

from safe_repo.core.mongo.mongo_client import get_mongo_db, is_mongo_available

STORAGE = os.path.join(os.path.dirname(__file__), "users_storage.json")

def _read():
    if not os.path.exists(STORAGE):
        return {"users": []}
    with open(STORAGE, "r") as f:
        return json.load(f)

def _write(data):
    with open(STORAGE, "w") as f:
        json.dump(data, f)

def _get_collection():
    db = get_mongo_db()
    if db is None:
        return None
    return db["users"]


async def get_users():
    """Primary: MongoDB. Fallback: JSON file."""
    if is_mongo_available():
        coll = _get_collection()
        if coll is not None:
            docs = await coll.find_one({}, {"_id": 0, "users": 1})
            if docs and "users" in docs:
                return docs["users"]
    data = await asyncio.to_thread(_read)
    return data.get("users", [])


async def _sync_to_json(users):
    data = {"users": users}
    await asyncio.to_thread(_write, data)


async def add_user(user):
    data = await asyncio.to_thread(_read)
    users = data.get("users", [])
    if user in users:
        return
    users.append(user)
    data["users"] = users
    await asyncio.to_thread(_write, data)
    if is_mongo_available():
        coll = _get_collection()
        if coll is not None:
            await coll.update_one(
                {},
                {"$addToSet": {"users": user}},
                upsert=True,
            )


async def del_user(user):
    data = await asyncio.to_thread(_read)
    users = data.get("users", [])
    if user in users:
        users.remove(user)
        data["users"] = users
        await asyncio.to_thread(_write, data)
    if is_mongo_available():
        coll = _get_collection()
        if coll is not None:
            await coll.update_one(
                {},
                {"$pull": {"users": user}},
                upsert=True,
            )
