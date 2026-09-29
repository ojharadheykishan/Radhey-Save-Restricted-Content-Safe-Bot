import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import safe_repo.core.media_links as media_links


class FakeCollection:
    """Minimal stand-in for the pymongo stream_catalog collection."""

    def __init__(self, documents=None):
        self.documents = [dict(doc) for doc in (documents or [])]
        self.deleted_filters = []

    def _matches(self, document, query):
        for key, expected in (query or {}).items():
            if key == "token" and isinstance(expected, dict) and "$in" in expected:
                if document.get("token") not in expected["$in"]:
                    return False
            elif document.get(key) != expected:
                return False
        return True

    def replace_one(self, query, document, upsert=False):
        for existing in self.documents:
            if self._matches(existing, query):
                existing.clear()
                existing.update(document)
                return
        if upsert:
            self.documents.append(dict(document))

    def update_one(self, query, update, upsert=False):
        for existing in self.documents:
            if self._matches(existing, query):
                existing.update(update.get("$set", {}))
                return
        if upsert:
            self.documents.append(dict(update.get("$set", {})))

    def find_one_and_update(self, query, update, return_document=None):
        for existing in self.documents:
            if self._matches(existing, query):
                for field, delta in update.get("$inc", {}).items():
                    existing[field] = int(existing.get(field) or 0) + int(delta)
                return existing
        return None

    def delete_many(self, query):
        before = len(self.documents)
        self.documents = [doc for doc in self.documents if not self._matches(doc, query)]
        self.deleted_filters.append(query)

        class Result:
            deleted_count = before - len(self.documents)

        return Result()

    def find(self, query=None, projection=None):
        return [doc for doc in self.documents if self._matches(doc, query)]


@pytest.fixture
def mongo(tmp_path, monkeypatch):
    """Point the catalog helpers at a fake collection and temp JSON files."""
    collection = FakeCollection()
    monkeypatch.setattr(media_links, "_mongo_catalog_coll", lambda: collection)
    monkeypatch.setenv("STREAM_CATALOG_FILE", str(tmp_path / "catalog.json"))
    monkeypatch.setenv("STREAM_LINKS_FILE", str(tmp_path / "links.txt"))
    monkeypatch.setattr(media_links, "_STREAM_CACHE_DIR", str(tmp_path / "cache"))
    return collection


def test_partial_write_keeps_entries_missing_from_the_incoming_list(mongo):
    mongo.documents = [{"token": "kept", "title": "Kept"}, {"token": "other", "title": "Other"}]

    media_links.write_stream_entries([{"token": "kept", "title": "Kept", "views": 1}])

    assert {doc["token"] for doc in mongo.documents} == {"kept", "other"}
    assert not mongo.deleted_filters, "a normal catalog write must never delete documents"


def test_empty_write_does_not_wipe_the_collection(mongo):
    mongo.documents = [{"token": "kept", "title": "Kept"}]

    media_links.write_stream_entries([])

    assert [doc["token"] for doc in mongo.documents] == ["kept"]


def test_append_stream_link_only_touches_the_new_entry(mongo):
    mongo.documents = [{"token": "existing", "title": "Existing"}]

    media_links.append_stream_link(
        "https://example.com/player/new",
        "https://example.com/stream/new",
        label="stream",
        token="new",
    )

    assert {doc["token"] for doc in mongo.documents} == {"existing", "new"}
    assert not mongo.deleted_filters


def test_repeated_appends_accumulate_without_losing_earlier_entries(mongo):
    for index in range(5):
        media_links.append_stream_link(
            f"https://example.com/player/{index}",
            f"https://example.com/stream/{index}",
            token=f"token-{index}",
        )

    assert {doc["token"] for doc in mongo.documents} == {f"token-{index}" for index in range(5)}


def test_update_stream_entry_patches_a_single_record(mongo):
    mongo.documents = [{"token": "a", "title": "A"}, {"token": "b", "title": "B"}]

    media_links.update_stream_entry("b", {"title": "B renamed", "featured": True})

    titles = {doc["token"]: doc["title"] for doc in mongo.documents}
    assert titles == {"a": "A", "b": "B renamed"}
    assert mongo.documents[1]["featured"] is True


def test_increment_stream_entry_field_counts_views_atomically(mongo):
    mongo.documents = [{"token": "a", "views": 4}]

    assert media_links.increment_stream_entry_field("a", "views") == 5
    assert media_links.increment_stream_entry_field("a", "views", 2) == 7
    assert mongo.documents[0]["views"] == 7


def test_remove_stream_entries_deletes_only_requested_tokens(mongo):
    mongo.documents = [{"token": "a"}, {"token": "b"}, {"token": "c"}]

    media_links.remove_stream_entries(["b"])

    assert {doc["token"] for doc in mongo.documents} == {"a", "c"}


def test_increment_without_mongo_falls_back_to_the_json_catalog(tmp_path, monkeypatch):
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps([{"token": "a", "views": 1}]), encoding="utf-8")
    monkeypatch.setenv("STREAM_CATALOG_FILE", str(catalog))
    monkeypatch.setattr(media_links, "_mongo_catalog_coll", lambda: None)

    assert media_links.increment_stream_entry_field("a", "views") == 2
    assert json.loads(catalog.read_text(encoding="utf-8"))[0]["views"] == 2


def test_catalog_cleanup_is_disabled_by_default(monkeypatch, tmp_path):
    monkeypatch.setattr(media_links, "_CATALOG_MAX_AGE_HOURS", 0)
    old = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d %H:%M:%S")
    monkeypatch.setenv("STREAM_CATALOG_FILE", str(tmp_path / "catalog.json"))
    monkeypatch.setattr(media_links, "_mongo_catalog_coll", lambda: None)
    (tmp_path / "catalog.json").write_text(
        json.dumps([{"token": "ancient", "timestamp": old, "approved": True}]),
        encoding="utf-8",
    )

    assert media_links.cleanup_old_catalog_entries() == 0
    assert media_links.run_full_cleanup() == 0
    assert json.loads((tmp_path / "catalog.json").read_text(encoding="utf-8"))[0]["token"] == "ancient"


def test_catalog_cleanup_still_prunes_when_a_window_is_configured(monkeypatch, tmp_path):
    old = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    recent = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    monkeypatch.setenv("STREAM_CATALOG_FILE", str(tmp_path / "catalog.json"))
    monkeypatch.setattr(media_links, "_mongo_catalog_coll", lambda: None)
    (tmp_path / "catalog.json").write_text(
        json.dumps([{"token": "ancient", "timestamp": old}, {"token": "fresh", "timestamp": recent}]),
        encoding="utf-8",
    )

    assert media_links.cleanup_old_catalog_entries(max_age_hours=24) == 1
    remaining = json.loads((tmp_path / "catalog.json").read_text(encoding="utf-8"))
    assert [entry["token"] for entry in remaining] == ["fresh"]


def test_stream_file_cleanup_is_disabled_by_default(monkeypatch, tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    stale = cache / "stale_video.mp4"
    stale.write_bytes(b"video")
    monkeypatch.setattr(media_links, "_CLEANUP_MAX_AGE_HOURS", 0)

    assert media_links.cleanup_old_stream_files() == 0
    assert stale.exists(), "cached media must survive until a retention window is configured"


def test_local_json_backup_tracks_single_entry_updates(tmp_path, monkeypatch):
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps([{"token": "a", "views": 1}, {"token": "b"}]), encoding="utf-8")
    monkeypatch.setenv("STREAM_CATALOG_FILE", str(catalog))
    monkeypatch.setattr(media_links, "_mongo_catalog_coll", lambda: None)

    media_links.increment_stream_entry_field("a", "views")

    data = json.loads(catalog.read_text(encoding="utf-8"))
    assert data[0]["views"] == 2


def test_api_tags_endpoint_returns_json_instead_of_a_coroutine(monkeypatch):
    from flask import Flask
    from safe_repo.web import api

    monkeypatch.setattr(api, "tags_get_all_tags_with_counts", lambda: _async_value([{"name": "physics"}]))
    app = Flask(__name__)
    app.add_url_rule("/api/tags", "api_tags_list", api.api_tags_list, methods=["GET"])

    with app.test_client() as client:
        response = client.get("/api/tags")

    assert response.status_code == 200
    assert response.get_json()["tags"] == [{"name": "physics"}]


def test_saved_links_survive_a_cleanup_cycle(mongo, monkeypatch):
    """Regression: links used to be pruned by the periodic cleanup task."""
    monkeypatch.setattr(media_links, "_CLEANUP_MAX_AGE_HOURS", 0)
    monkeypatch.setattr(media_links, "_CATALOG_MAX_AGE_HOURS", 0)
    for index in range(3):
        media_links.append_stream_link(
            f"https://example.com/player/{index}",
            f"https://example.com/stream/{index}",
            token=f"token-{index}",
        )

    stale = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    for document in mongo.documents:
        document["timestamp"] = stale
    media_links.write_stream_entries(mongo.documents, mongo_sync=False)

    assert media_links.run_full_cleanup() == 0
    assert {doc["token"] for doc in mongo.documents} == {"token-0", "token-1", "token-2"}


def test_read_returns_one_entry_per_token(mongo):
    mongo.documents = [
        {"token": "dup", "title": "older", "timestamp": "2024-01-01 00:00:00"},
        {"token": "dup", "title": "newer", "timestamp": "2026-01-01 00:00:00"},
    ]

    class Sortable(list):
        def sort(self, *_args, **_kwargs):
            return self

    mongo.find = lambda *_args, **_kwargs: Sortable(mongo.documents)

    entries = media_links.read_stream_entries()
    assert [entry["token"] for entry in entries] == ["dup"]


def _async_value(value):
    async def _coro():
        return value

    return _coro()
