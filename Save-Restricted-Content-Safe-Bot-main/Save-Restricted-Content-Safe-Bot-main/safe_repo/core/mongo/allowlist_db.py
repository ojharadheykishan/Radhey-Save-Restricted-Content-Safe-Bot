"""IP/Channel Whitelist — manage allowlist for entities."""
import os
import json
import asyncio
from datetime import datetime, timezone

from safe_repo.core.mongo.mongo_client import get_mongo_db, is_mongo_available

STORAGE = os.path.join(os.path.dirname(__file__), "allowlist.json")


def _read():
    if not os.path.exists(STORAGE):
        return {"allowlist": []}
    try:
        with open(STORAGE, "r") as f:
            return json.load(f)
    except Exception:
        return {"allowlist": []}


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
    return db["allowlist"]


def _serialize(doc):
    if doc is None:
        return None
    doc = dict(doc)
    doc.pop("_id", None)
    return doc


async def add_to_allowlist(entity_id, entity_type, note=""):
    """Add an entity to the allowlist."""
    entity_id = str(entity_id)
    entry = {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "note": note,
        "created_at": datetime.now(timezone.utc),
    }
    # JSON
    data = await asyncio.to_thread(_read)
    allowlist = data.get("allowlist", [])
    allowlist = [a for a in allowlist if a.get("entity_id") != entity_id]
    allowlist.append(entry)
    data["allowlist"] = allowlist
    await asyncio.to_thread(_write, data)
    # MongoDB
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            await coll.update_one(
                {"entity_id": entity_id},
                {"$set": entry},
                upsert=True,
            )
    return True


async def check_allowed(entity_id):
    """Check if an entity is on the allowlist."""
    entity_id = str(entity_id)
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            doc = await coll.find_one({"entity_id": entity_id})
            if doc:
                return _serialize(doc)

    data = await asyncio.to_thread(_read)
    allowlist = data.get("allowlist", [])
    for entry in allowlist:
        if entry.get("entity_id") == entity_id:
            return entry
    return None


async def remove_from_allowlist(entity_id):
    """Remove an entity from the allowlist."""
    entity_id = str(entity_id)
    data = await asyncio.to_thread(_read)
    allowlist = data.get("allowlist", [])
    allowlist = [a for a in allowlist if a.get("entity_id") != entity_id]
    data["allowlist"] = allowlist
    await asyncio.to_thread(_write, data)
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            await coll.delete_one({"entity_id": entity_id})
    return True


async def list_allowlist(entity_type=None):
    """List allowlist entries, optionally filtered by entity type."""
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            query = {}
            if entity_type:
                query["entity_type"] = entity_type
            cursor = coll.find(query)
            docs = await cursor.to_list(length=10000)
            return [_serialize(d) for d in docs]

    data = await asyncio.to_thread(_read)
    allowlist = data.get("allowlist", [])
    if entity_type:
        allowlist = [a for a in allowlist if a.get("entity_type") == entity_type]
    return allowlist


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