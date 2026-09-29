"""Multi-Bot Coordination — shared clone job queue with distributed locking."""
import os
import json
import asyncio
import secrets
import string
from datetime import datetime, timezone, timedelta

from safe_repo.core.mongo.mongo_client import get_mongo_db, is_mongo_available

STORAGE = os.path.join(os.path.dirname(__file__), "clone_queue.json")

JOB_TTL_SECONDS = 300  # 5 min job expiry for stuck jobs


def _read():
    if not os.path.exists(STORAGE):
        return {"jobs": []}
    try:
        with open(STORAGE, "r") as f:
            return json.load(f)
    except Exception:
        return {"jobs": []}


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
    return db["clone_queue"]


def _serialize(doc):
    if doc is None:
        return None
    doc = dict(doc)
    doc.pop("_id", None)
    return doc


def _generate_job_id():
    chars = string.ascii_uppercase + string.digits
    return "JOB_" + "".join(secrets.choice(chars) for _ in range(12))


async def enqueue_clone_job(user_id, message_data):
    """Add a clone job to the queue."""
    user_id = str(user_id)
    job_id = _generate_job_id()
    job = {
        "job_id": job_id,
        "user_id": user_id,
        "message_data": message_data,
        "status": "pending",
        "claimed_by": None,
        "created_at": datetime.now(timezone.utc),
        "expire_at": datetime.now(timezone.utc) + timedelta(seconds=JOB_TTL_SECONDS),
    }
    # JSON
    data = await asyncio.to_thread(_read)
    jobs = data.get("jobs", [])
    jobs.append(job)
    data["jobs"] = jobs
    await asyncio.to_thread(_write, data)
    # MongoDB
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            await coll.insert_one(job)
    return job_id


async def claim_clone_job(bot_id):
    """Atomically claim the next pending job for a bot."""
    bot_id = str(bot_id)
    now = datetime.now(timezone.utc)

    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            # Atomic claim using find_one_and_update
            job = await coll.find_one_and_update(
                {
                    "status": "pending",
                    "expire_at": {"$gt": now},
                },
                {
                    "$set": {
                        "status": "claimed",
                        "claimed_by": bot_id,
                        "claimed_at": now,
                    },
                },
                sort=[("created_at", 1)],
                return_document=True,
            )
            if job:
                return _serialize(job)
            return None

    data = await asyncio.to_thread(_read)
    jobs = data.get("jobs", [])
    for job in jobs:
        if job.get("status") == "pending":
            try:
                expire = datetime.fromisoformat(job.get("expire_at", "")).replace(tzinfo=timezone.utc)
            except Exception:
                continue
            if expire > now:
                job["status"] = "claimed"
                job["claimed_by"] = bot_id
                job["claimed_at"] = now.isoformat()
                await asyncio.to_thread(_write, data)
                return job
    return None


async def complete_clone_job(job_id):
    """Mark a clone job as completed."""
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            result = await coll.update_one(
                {"job_id": job_id},
                {"$set": {"status": "completed", "completed_at": datetime.now(timezone.utc)}},
            )
            return result.modified_count > 0

    data = await asyncio.to_thread(_read)
    jobs = data.get("jobs", [])
    for job in jobs:
        if job.get("job_id") == job_id:
            job["status"] = "completed"
            job["completed_at"] = datetime.now(timezone.utc).isoformat()
            await asyncio.to_thread(_write, data)
            return True
    return False


async def get_pending_jobs(limit=10):
    """Return pending clone jobs."""
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            cursor = coll.find({"status": "pending"}).sort("created_at", 1).limit(limit)
            docs = await cursor.to_list(length=limit)
            return [_serialize(d) for d in docs]

    data = await asyncio.to_thread(_read)
    jobs = data.get("jobs", [])
    pending = [j for j in jobs if j.get("status") == "pending"]
    return pending[:limit]


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