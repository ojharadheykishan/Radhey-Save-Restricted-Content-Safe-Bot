import os
import json
import asyncio

from safe_repo.core.mongo.mongo_client import get_mongo_db, is_mongo_available

STORAGE = os.path.join(os.path.dirname(__file__), "data_storage.json")


def _read():
    if not os.path.exists(STORAGE):
        return {}
    with open(STORAGE, "r") as f:
        return json.load(f)


def _write(data):
    with open(STORAGE, "w") as f:
        json.dump(data, f)


async def _mongo_coll():
    db = get_mongo_db()
    if db is None:
        return None
    return db["user_data"]


async def _mongo_get(user_id):
    coll = await _mongo_coll()
    if coll is None:
        return None
    doc = await coll.find_one({"user_id": str(user_id)})
    return doc


async def _mongo_set(user_id, data):
    coll = await _mongo_coll()
    if coll is None:
        return False
    await coll.update_one(
        {"user_id": str(user_id)},
        {"$set": {"user_id": str(user_id), **data}},
        upsert=True,
    )
    return True


async def _mongo_unset(user_id, key):
    coll = await _mongo_coll()
    if coll is None:
        return False
    await coll.update_one(
        {"user_id": str(user_id)},
        {"$unset": {key: ""}},
    )
    return True


async def get_data(user_id):
    """Primary: MongoDB. Fallback: JSON file."""
    if is_mongo_available():
        doc = await _mongo_get(user_id)
        if doc is not None:
            data = dict(doc)
            data.pop("_id", None)
            return data

    data = await asyncio.to_thread(_read)
    return data.get(str(user_id))


async def _ensure_user(user_id):
    data = await asyncio.to_thread(_read)
    u = data.get(str(user_id), {})
    data[str(user_id)] = u
    await asyncio.to_thread(_write, data)
    if is_mongo_available():
        await _mongo_set(user_id, u)
    return u


async def set_thumbnail(user_id, thumb):
    await _ensure_user(user_id)
    data = await asyncio.to_thread(_read)
    data[str(user_id)]["thumb"] = thumb
    await asyncio.to_thread(_write, data)
    await _mongo_set(user_id, {"thumb": thumb})


async def set_caption(user_id, caption):
    await _ensure_user(user_id)
    data = await asyncio.to_thread(_read)
    data[str(user_id)]["caption"] = caption
    await asyncio.to_thread(_write, data)
    await _mongo_set(user_id, {"caption": caption})


async def replace_caption(user_id, replace_txt, to_replace):
    await _ensure_user(user_id)
    data = await asyncio.to_thread(_read)
    data[str(user_id)]["replace_txt"] = replace_txt
    data[str(user_id)]["to_replace"] = to_replace
    await asyncio.to_thread(_write, data)
    await _mongo_set(user_id, {"replace_txt": replace_txt, "to_replace": to_replace})


async def set_session(user_id, session):
    await _ensure_user(user_id)
    data = await asyncio.to_thread(_read)
    data[str(user_id)]["session"] = session
    await asyncio.to_thread(_write, data)
    await _mongo_set(user_id, {"session": session})


async def clean_words(user_id, new_clean_words):
    await _ensure_user(user_id)
    data = await asyncio.to_thread(_read)
    existing = data[str(user_id)].get("clean_words", []) or []
    updated = list(dict.fromkeys(existing + new_clean_words))
    data[str(user_id)]["clean_words"] = updated
    await asyncio.to_thread(_write, data)
    await _mongo_set(user_id, {"clean_words": updated})


async def remove_clean_words(user_id, words_to_remove):
    await _ensure_user(user_id)
    data = await asyncio.to_thread(_read)
    existing = data[str(user_id)].get("clean_words", []) or []
    data[str(user_id)]["clean_words"] = [w for w in existing if w not in words_to_remove]
    await asyncio.to_thread(_write, data)
    await _mongo_set(user_id, {"clean_words": data[str(user_id)]["clean_words"]})


async def set_channel(user_id, chat_id):
    await _ensure_user(user_id)
    data = await asyncio.to_thread(_read)
    data[str(user_id)]["chat_id"] = chat_id
    await asyncio.to_thread(_write, data)
    await _mongo_set(user_id, {"chat_id": chat_id})


async def all_words_remove(user_id):
    await _ensure_user(user_id)
    data = await asyncio.to_thread(_read)
    data[str(user_id)]["clean_words"] = None
    await asyncio.to_thread(_write, data)
    await _mongo_unset(user_id, "clean_words")


async def remove_thumbnail(user_id):
    await _ensure_user(user_id)
    data = await asyncio.to_thread(_read)
    data[str(user_id)]["thumb"] = None
    await asyncio.to_thread(_write, data)
    await _mongo_unset(user_id, "thumb")


async def remove_caption(user_id):
    await _ensure_user(user_id)
    data = await asyncio.to_thread(_read)
    data[str(user_id)]["caption"] = None
    await asyncio.to_thread(_write, data)
    await _mongo_unset(user_id, "caption")


async def remove_replace(user_id):
    await _ensure_user(user_id)
    data = await asyncio.to_thread(_read)
    data[str(user_id)]["replace_txt"] = None
    data[str(user_id)]["to_replace"] = None
    await asyncio.to_thread(_write, data)
    await _mongo_unset(user_id, "replace_txt")
    await _mongo_unset(user_id, "to_replace")


async def remove_session(user_id):
    await _ensure_user(user_id)
    data = await asyncio.to_thread(_read)
    data[str(user_id)]["session"] = None
    await asyncio.to_thread(_write, data)
    await _mongo_unset(user_id, "session")


async def remove_channel(user_id):
    await _ensure_user(user_id)
    data = await asyncio.to_thread(_read)
    data[str(user_id)]["chat_id"] = None
    await asyncio.to_thread(_write, data)
    await _mongo_unset(user_id, "chat_id")


async def delete_session(user_id):
    data = await asyncio.to_thread(_read)
    if str(user_id) in data:
        data[str(user_id)].pop("session", None)
        await asyncio.to_thread(_write, data)
