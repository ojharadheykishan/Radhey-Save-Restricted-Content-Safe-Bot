import os
import json
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from safe_repo.core.mongo.mongo_client import get_async_db, is_mongo_available

MONGO_DIR = Path(__file__).resolve().parent.parent / "core" / "mongo"
TAGS_PATH = MONGO_DIR / "tags.json"
VIDEO_TAGS_PATH = MONGO_DIR / "video_tags.json"
USER_TAGS_PATH = MONGO_DIR / "user_tags.json"


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _mongo_coll():
    db = get_async_db()
    if db is None:
        return None
    return db["tags_data"]


# ------------------------------------------------------------------
# Tags
# ------------------------------------------------------------------
async def create_tag(name: str, color: str, description: str = "") -> Dict[str, Any]:
    tag = {
        "name": name,
        "color": color,
        "description": description,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # ---- JSON ----
    tags = _read_json(TAGS_PATH, [])
    if not isinstance(tags, list):
        tags = []
    if any(t.get("name") == name for t in tags):
        raise ValueError(f"Tag '{name}' already exists")
    tags.append(tag)
    _write_json(TAGS_PATH, tags)

    # ---- MongoDB ----
    if is_mongo_available():
        coll = _mongo_coll()
        if coll is not None:
            existing = await coll.find_one({"_type": "tag", "name": name})
            if existing:
                raise ValueError(f"Tag '{name}' already exists")
            await coll.insert_one({"_type": "tag", **tag})

    return tag


async def get_tag(name: str) -> Optional[Dict[str, Any]]:
    # ---- MongoDB ----
    if is_mongo_available():
        coll = _mongo_coll()
        if coll is not None:
            doc = await coll.find_one({"_type": "tag", "name": name})
            if doc:
                doc.pop("_id", None)
                doc.pop("_type", None)
                return doc

    # ---- JSON ----
    for tag in _read_json(TAGS_PATH, []):
        if tag.get("name") == name:
            return tag
    return None


async def update_tag(name: str, color: Optional[str] = None, description: Optional[str] = None) -> Optional[Dict[str, Any]]:
    # ---- JSON ----
    tags = _read_json(TAGS_PATH, [])
    if not isinstance(tags, list):
        tags = []
    found = None
    for tag in tags:
        if tag.get("name") == name:
            if color is not None:
                tag["color"] = color
            if description is not None:
                tag["description"] = description
            found = tag
    if found:
        _write_json(TAGS_PATH, tags)

    # ---- MongoDB ----
    if is_mongo_available():
        coll = _mongo_coll()
        if coll is not None:
            update = {}
            if color is not None:
                update["color"] = color
            if description is not None:
                update["description"] = description
            if update:
                await coll.update_one(
                    {"_type": "tag", "name": name},
                    {"$set": update},
                )

    return found


async def delete_tag(name: str) -> bool:
    # ---- JSON ----
    tags = _read_json(TAGS_PATH, [])
    if not isinstance(tags, list):
        tags = []
    new_tags = [t for t in tags if t.get("name") != name]
    if len(new_tags) == len(tags):
        return False
    _write_json(TAGS_PATH, new_tags)

    video_tags = _read_json(VIDEO_TAGS_PATH, {})
    for token, tag_list in list(video_tags.items()):
        video_tags[token] = [t for t in tag_list if t != name]
        if not video_tags[token]:
            del video_tags[token]
    _write_json(VIDEO_TAGS_PATH, video_tags)

    user_tags = _read_json(USER_TAGS_PATH, {})
    for user_id, tag_list in list(user_tags.items()):
        user_tags[user_id] = [t for t in tag_list if t != name]
        if not user_tags[user_id]:
            del user_tags[user_id]
    _write_json(USER_TAGS_PATH, user_tags)

    # ---- MongoDB ----
    if is_mongo_available():
        coll = _mongo_coll()
        if coll is not None:
            await coll.delete_many({"_type": "tag", "name": name})
            await coll.delete_many({"_type": "video_tag", "tag": name})
            await coll.delete_many({"_type": "user_tag", "tag": name})

    return True


async def list_tags() -> List[Dict[str, Any]]:
    if is_mongo_available():
        coll = _mongo_coll()
        if coll is not None:
            cursor = coll.find({"_type": "tag"})
            docs = await cursor.to_list(length=10000)
            result = []
            for d in docs:
                d.pop("_id", None)
                d.pop("_type", None)
                result.append(d)
            return result

    tags = _read_json(TAGS_PATH, [])
    if not isinstance(tags, list):
        tags = []
    return tags


async def get_all_tags_with_counts() -> List[Dict[str, Any]]:
    tags = await list_tags()
    video_tags = await _load_video_tags()
    user_tags = await _load_user_tags()
    result = []
    for tag in tags:
        name = tag.get("name", "")
        video_count = sum(1 for v in video_tags.values() if name in v)
        user_count = sum(1 for u in user_tags.values() if name in u)
        result.append({**tag, "video_count": video_count, "user_count": user_count})
    return result


# ------------------------------------------------------------------
# Video tags
# ------------------------------------------------------------------
async def _load_video_tags() -> Dict[str, List[str]]:
    if is_mongo_available():
        coll = _mongo_coll()
        if coll is not None:
            cursor = coll.find({"_type": "video_tag"})
            docs = await cursor.to_list(length=50000)
            result = {}
            for d in docs:
                result[d.get("token")] = d.get("tags", [])
            return result
    return _read_json(VIDEO_TAGS_PATH, {})


async def _save_video_tag_mongo(token: str, tags: List[str]) -> None:
    coll = _mongo_coll()
    if coll is None:
        return
    await coll.update_one(
        {"_type": "video_tag", "token": token},
        {"$set": {"tags": tags}},
        upsert=True,
    )


async def assign_tag_to_video(tag_name: str, token: str) -> bool:
    # ---- JSON ----
    tags = _read_json(TAGS_PATH, [])
    if not isinstance(tags, list):
        tags = []
    if not any(t.get("name") == tag_name for t in tags):
        raise ValueError(f"Tag '{tag_name}' does not exist")

    video_tags = _read_json(VIDEO_TAGS_PATH, {})
    current = video_tags.get(token, [])
    if tag_name in current:
        return False
    current.append(tag_name)
    video_tags[token] = current
    _write_json(VIDEO_TAGS_PATH, video_tags)

    # ---- MongoDB ----
    if is_mongo_available():
        await _save_video_tag_mongo(token, current)

    return True


async def remove_tag_from_video(tag_name: str, token: str) -> bool:
    video_tags = _read_json(VIDEO_TAGS_PATH, {})
    current = video_tags.get(token, [])
    if tag_name not in current:
        return False
    current = [t for t in current if t != tag_name]
    if current:
        video_tags[token] = current
    else:
        video_tags.pop(token, None)
    _write_json(VIDEO_TAGS_PATH, video_tags)

    if is_mongo_available():
        await _save_video_tag_mongo(token, current)

    return True


async def get_tags_for_video(token: str) -> List[str]:
    if is_mongo_available():
        coll = _mongo_coll()
        if coll is not None:
            doc = await coll.find_one({"_type": "video_tag", "token": token})
            if doc:
                return doc.get("tags", [])

    return _read_json(VIDEO_TAGS_PATH, {}).get(token, [])


async def get_videos_by_tag(tag_name: str) -> List[str]:
    if is_mongo_available():
        coll = _mongo_coll()
        if coll is not None:
            cursor = coll.find({"_type": "video_tag", "tags": tag_name})
            docs = await cursor.to_list(length=50000)
            return [d.get("token") for d in docs if d.get("token")]

    video_tags = _read_json(VIDEO_TAGS_PATH, {})
    return [token for token, tags in video_tags.items() if tag_name in tags]


# ------------------------------------------------------------------
# User tags
# ------------------------------------------------------------------
async def _load_user_tags() -> Dict[str, List[str]]:
    if is_mongo_available():
        coll = _mongo_coll()
        if coll is not None:
            cursor = coll.find({"_type": "user_tag"})
            docs = await cursor.to_list(length=50000)
            result = {}
            for d in docs:
                result[d.get("user_id")] = d.get("tags", [])
            return result
    return _read_json(USER_TAGS_PATH, {})


async def _save_user_tag_mongo(user_id: str, tags: List[str]) -> None:
    coll = _mongo_coll()
    if coll is None:
        return
    await coll.update_one(
        {"_type": "user_tag", "user_id": str(user_id)},
        {"$set": {"tags": tags}},
        upsert=True,
    )


async def assign_tag_to_user(tag_name: str, user_id: str) -> bool:
    tags = await list_tags()
    if not any(t.get("name") == tag_name for t in tags):
        raise ValueError(f"Tag '{tag_name}' does not exist")

    # ---- JSON ----
    user_tags = _read_json(USER_TAGS_PATH, {})
    current = user_tags.get(str(user_id), [])
    if tag_name in current:
        return False
    current.append(tag_name)
    user_tags[str(user_id)] = current
    _write_json(USER_TAGS_PATH, user_tags)

    # ---- MongoDB ----
    if is_mongo_available():
        await _save_user_tag_mongo(user_id, current)

    return True


async def remove_tag_from_user(tag_name: str, user_id: str) -> bool:
    user_tags = _read_json(USER_TAGS_PATH, {})
    current = user_tags.get(str(user_id), [])
    if tag_name not in current:
        return False
    current = [t for t in current if t != tag_name]
    if current:
        user_tags[str(user_id)] = current
    else:
        user_tags.pop(str(user_id), None)
    _write_json(USER_TAGS_PATH, user_tags)

    if is_mongo_available():
        await _save_user_tag_mongo(user_id, current)

    return True


async def get_tags_for_user(user_id: str) -> List[str]:
    if is_mongo_available():
        coll = _mongo_coll()
        if coll is not None:
            doc = await coll.find_one({"_type": "user_tag", "user_id": str(user_id)})
            if doc:
                return doc.get("tags", [])

    return _read_json(USER_TAGS_PATH, {}).get(str(user_id), [])


def _run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


create_tag_sync = lambda name, color, desc="": _run_async(create_tag(name, color, desc))
update_tag_sync = lambda name, color=None, desc=None: _run_async(update_tag(name, color, desc))
delete_tag_sync = lambda name: _run_async(delete_tag(name))
assign_video_tag_sync = lambda tag_name, token: _run_async(assign_tag_to_video(tag_name, token))
remove_video_tag_sync = lambda tag_name, token: _run_async(remove_tag_from_video(tag_name, token))
get_video_tags_sync = lambda token: _run_async(get_tags_for_video(token))
