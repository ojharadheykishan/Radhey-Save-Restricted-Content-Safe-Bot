import asyncio
import os

import pytest

# Pyrogram 2 builds its sync helpers at import time and needs a current loop.
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

# The suite must never talk to a real database. Catalog code falls back to its
# JSON store when MONGO_DB is empty, so tests stay on local temp files.
os.environ["MONGO_DB"] = ""


@pytest.fixture(autouse=True)
def _isolate_mongo(monkeypatch):
    monkeypatch.setenv("MONGO_DB", "")
    from safe_repo.core.mongo import mongo_client

    monkeypatch.setattr(mongo_client, "_mongo_available_cache", None, raising=False)
    monkeypatch.setattr(mongo_client, "_mongo_client_sync", None, raising=False)
    monkeypatch.setattr(mongo_client, "_mongo_client_async", None, raising=False)
    yield
