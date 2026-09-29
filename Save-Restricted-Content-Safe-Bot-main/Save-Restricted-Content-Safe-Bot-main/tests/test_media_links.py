import os
import json
import sys
import tempfile
import io
from datetime import datetime, timezone
from pathlib import Path

import cv2
import fitz
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import safe_repo.core.media_links as media_links
import safe_repo.core.object_storage as object_storage
from safe_repo.core.media_links import save_stream_file, append_stream_link, read_stream_entries


def test_save_stream_file_creates_public_stream_and_player_urls(tmp_path):
    source = tmp_path / "sample.mp4"
    source.write_bytes(b"test-media")

    cache_dir = tmp_path / "cache"
    result = save_stream_file(
        str(source),
        base_url="https://example.com",
        cache_dir=str(cache_dir),
    )

    assert result is not None
    assert result["token"]
    assert result["stream_url"].startswith("https://example.com/stream/")
    assert result["player_url"].startswith("https://example.com/player/")
    assert os.path.exists(result["file_path"])
    assert os.path.getsize(result["file_path"]) == len(b"test-media")


def test_save_stream_file_stores_supplied_thumbnail(tmp_path):
    source = tmp_path / "sample.mp4"
    source.write_bytes(b"test-media")
    thumbnail = tmp_path / "poster.jpg"
    assert cv2.imwrite(str(thumbnail), np.zeros((8, 8, 3), dtype=np.uint8))

    result = save_stream_file(
        str(source),
        base_url="https://example.com",
        cache_dir=str(tmp_path / "cache"),
        thumbnail_path=str(thumbnail),
    )

    assert result["thumbnail_url"] == f"https://example.com/thumbnail/{result['token']}"
    assert (tmp_path / "cache" / f"{result['token']}.thumb.jpg").exists()


def test_save_stream_file_rejects_large_files(tmp_path):
    source = tmp_path / "large.mp4"
    source.write_bytes(b"x" * 1024)

    cache_dir = tmp_path / "cache"
    result = save_stream_file(
        str(source),
        base_url="https://example.com",
        cache_dir=str(cache_dir),
        max_size_mb=0,
    )

    assert result is None


def test_save_stream_file_extracts_searchable_pdf_text(tmp_path):
    source = tmp_path / "notes.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Conservation of momentum")
    document.save(source)
    document.close()

    result = save_stream_file(str(source), cache_dir=str(tmp_path / "cache"))

    assert "Conservation of momentum" in result["pdf_text"]
    assert len(result["content_hash"]) == 64


def test_stream_cache_quota_rejects_additional_media(tmp_path, monkeypatch):
    source = tmp_path / "sample.mp4"
    source.write_bytes(b"media larger than quota")
    monkeypatch.setenv("STREAM_CACHE_MAX_GB", "0.000000001")

    result = save_stream_file(str(source), cache_dir=str(tmp_path / "cache"))

    assert result is None


def test_save_stream_file_uses_railway_public_domain(tmp_path, monkeypatch):
    source = tmp_path / "sample.mp4"
    source.write_bytes(b"test-media")
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    monkeypatch.delenv("APP_URL", raising=False)
    monkeypatch.setenv("RAILWAY_PUBLIC_DOMAIN", "my-bot.up.railway.app")

    result = save_stream_file(str(source), cache_dir=str(tmp_path / "cache"))

    assert result["player_url"].startswith("https://my-bot.up.railway.app/player/")
    assert result["stream_url"].startswith("https://my-bot.up.railway.app/stream/")


def test_append_stream_link_stores_catalog_entry(tmp_path):
    archive_path = tmp_path / "links.txt"
    entry_path = tmp_path / "catalog.json"
    result = append_stream_link(
        "https://example.com/player/demo",
        "https://example.com/stream/demo",
        archive_path=str(archive_path),
        catalog_path=str(entry_path),
        subject="Movie",
        description="A sample description",
        title="Sample title",
        token="demo",
        thumbnail_url="https://example.com/thumbnail/demo",
        media_type="pdf",
    )

    assert archive_path.exists()
    assert entry_path.exists()
    entries = read_stream_entries(catalog_path=str(entry_path))
    assert len(entries) == 1
    assert entries[0]["subject"] == "Movie"
    assert entries[0]["token"] == "demo"
    assert entries[0]["thumbnail_url"] == "https://example.com/thumbnail/demo"
    assert entries[0]["media_type"] == "pdf"


def test_find_duplicate_media_matches_content_hash(tmp_path):
    source = tmp_path / "lesson.pdf"
    source.write_bytes(b"same media bytes")
    digest = media_links.get_file_sha256(str(source))
    catalog_path = tmp_path / "catalog.json"
    append_stream_link(
        "https://example.com/player/existing",
        "https://example.com/stream/existing",
        catalog_path=str(catalog_path),
        archive_path=str(tmp_path / "links.txt"),
        token="existing",
        content_hash=digest,
    )

    duplicate = media_links.find_duplicate_media(str(source), str(catalog_path))

    assert duplicate["token"] == "existing"


def test_app_data_dir_migrates_legacy_catalog_and_stream_cache(tmp_path, monkeypatch):
    fake_core = tmp_path / "source" / "safe_repo" / "core"
    legacy_mongo = fake_core / "mongo"
    legacy_cache = fake_core / "stream_cache"
    legacy_mongo.mkdir(parents=True)
    legacy_cache.mkdir(parents=True)
    legacy_catalog = legacy_mongo / "stream_catalog.json"
    legacy_catalog.write_text(json.dumps([{"token": "approved", "approved": True}]), encoding="utf-8")
    (legacy_mongo / "stream_links.txt").write_text("approved links", encoding="utf-8")
    (legacy_cache / "approved_video.mp4").write_bytes(b"saved video")
    persistent_dir = tmp_path / "railway-volume"
    monkeypatch.setattr(media_links, "__file__", str(fake_core / "media_links.py"))
    monkeypatch.setattr(media_links, "_STREAM_CACHE_DIR", None)
    monkeypatch.delenv("STREAM_CACHE_DIR", raising=False)
    monkeypatch.setenv("APP_DATA_DIR", str(persistent_dir))
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)

    data_dir = media_links._get_shared_repo_dir()
    cache_dir = Path(media_links._get_cache_dir())

    migrated_entries = media_links.read_stream_entries(str(data_dir / "stream_catalog.json"))
    assert migrated_entries == [{"token": "approved", "approved": True}]
    assert (data_dir / "stream_links.txt").read_text(encoding="utf-8") == "approved links"
    assert (cache_dir / "approved_video.mp4").read_bytes() == b"saved video"


def test_app_data_dir_does_not_overwrite_existing_approval_catalog(tmp_path, monkeypatch):
    fake_core = tmp_path / "source" / "safe_repo" / "core"
    legacy_mongo = fake_core / "mongo"
    legacy_mongo.mkdir(parents=True)
    (legacy_mongo / "stream_catalog.json").write_text(json.dumps([{"token": "old", "approved": False}]), encoding="utf-8")
    persistent_dir = tmp_path / "railway-volume"
    persistent_dir.mkdir()
    persistent_catalog = persistent_dir / "stream_catalog.json"
    persistent_catalog.write_text(json.dumps([{"token": "kept", "approved": True}]), encoding="utf-8")
    monkeypatch.setattr(media_links, "__file__", str(fake_core / "media_links.py"))
    monkeypatch.setenv("APP_DATA_DIR", str(persistent_dir))
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)

    media_links._get_shared_repo_dir()

    entries = media_links.read_stream_entries(str(persistent_catalog))
    assert entries == [{"token": "kept", "approved": True}]


def test_object_storage_catalog_keeps_approvals_after_local_catalog_is_removed(tmp_path, monkeypatch):
    class FakeS3:
        objects = {}

        def put_object(self, Bucket, Key, Body, ContentType):
            self.objects[Key] = bytes(Body)

        def get_object(self, Bucket, Key):
            if Key not in self.objects:
                raise FileNotFoundError(Key)
            return {"Body": io.BytesIO(self.objects[Key])}

        def get_object(self, Bucket, Key):
            if Key not in self.objects:
                raise FileNotFoundError(Key)
            return {"Body": io.BytesIO(self.objects[Key])}

    client = FakeS3()
    monkeypatch.setenv("OBJECT_STORAGE_ENDPOINT", "https://account.r2.cloudflarestorage.com")
    monkeypatch.setenv("OBJECT_STORAGE_BUCKET", "study-media")
    monkeypatch.setenv("OBJECT_STORAGE_ACCESS_KEY_ID", "test-access")
    monkeypatch.setenv("OBJECT_STORAGE_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(object_storage, "_get_client", lambda: (client, object_storage._configuration()))
    catalog = [{"token": "approved-video", "approved": True}, {"token": "pending-pdf", "approved": False}]

    media_links.write_stream_entries(catalog)
    Path(media_links.get_catalog_path()).unlink()
    restored = media_links.read_stream_entries()

    assert restored == catalog
    assert json.loads(client.objects["safe-repo/catalog/stream_catalog.json"]) == catalog


def test_object_storage_uploads_media_and_thumbnail_objects(tmp_path, monkeypatch):
    class FakeS3:
        objects = {}

        def upload_file(self, Filename, Bucket, Key, ExtraArgs):
            self.objects[Key] = Path(Filename).read_bytes()

        def put_object(self, Bucket, Key, Body, ContentType):
            self.objects[Key] = bytes(Body)

        def get_object(self, Bucket, Key):
            if Key not in self.objects:
                raise FileNotFoundError(Key)
            return {"Body": io.BytesIO(self.objects[Key])}

    client = FakeS3()
    monkeypatch.setenv("OBJECT_STORAGE_ENDPOINT", "https://account.r2.cloudflarestorage.com")
    monkeypatch.setenv("OBJECT_STORAGE_BUCKET", "study-media")
    monkeypatch.setenv("OBJECT_STORAGE_ACCESS_KEY_ID", "test-access")
    monkeypatch.setenv("OBJECT_STORAGE_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(object_storage, "_get_client", lambda: (client, object_storage._configuration()))
    source = tmp_path / "lesson.pdf"
    document = fitz.open()
    document.new_page().insert_text((72, 72), "Lesson")
    document.save(source)
    document.close()
    poster = tmp_path / "poster.jpg"
    assert cv2.imwrite(str(poster), np.zeros((8, 8, 3), dtype=np.uint8))

    saved = media_links.save_stream_file(str(source), cache_dir=str(tmp_path / "cache"), thumbnail_path=str(poster))
    media_links.append_stream_link(
        saved["player_url"], saved["stream_url"],
        archive_path=str(tmp_path / "links.txt"),
        token=saved["token"], storage_key=saved["storage_key"],
        thumbnail_storage_key=saved["thumbnail_storage_key"], approved=False,
    )

    assert saved["storage_key"] in client.objects
    assert saved["thumbnail_storage_key"] in client.objects
    assert any(key.endswith("stream_catalog.json") for key in client.objects)


def test_object_storage_restores_missing_stream_cache_file(tmp_path, monkeypatch):
    class FakeS3:
        objects = {"safe-repo/media/token_lesson.mp4": b"restored video"}

        def get_object(self, Bucket, Key):
            return {"Body": io.BytesIO(self.objects[Key])}

        def put_object(self, Bucket, Key, Body, ContentType):
            self.objects[Key] = bytes(Body)

        def download_file(self, Bucket, Key, Filename):
            Path(Filename).write_bytes(self.objects[Key])

    client = FakeS3()
    monkeypatch.setenv("OBJECT_STORAGE_ENDPOINT", "https://account.r2.cloudflarestorage.com")
    monkeypatch.setenv("OBJECT_STORAGE_BUCKET", "study-media")
    monkeypatch.setenv("OBJECT_STORAGE_ACCESS_KEY_ID", "test-access")
    monkeypatch.setenv("OBJECT_STORAGE_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(object_storage, "_get_client", lambda: (client, object_storage._configuration()))
    monkeypatch.setattr(media_links, "_get_cache_dir", lambda: str(tmp_path / "cache"))
    media_links.write_stream_entries([{
        "token": "token", "storage_key": "safe-repo/media/token_lesson.mp4", "approved": True,
    }])

    restored = media_links.get_stream_file("token")

    assert Path(restored["file_path"]).read_bytes() == b"restored video"


def test_object_storage_migration_uploads_available_legacy_media(tmp_path, monkeypatch):
    class FakeS3:
        objects = {}

        def put_object(self, Bucket, Key, Body, ContentType):
            self.objects[Key] = bytes(Body)

        def get_object(self, Bucket, Key):
            if Key not in self.objects:
                raise FileNotFoundError(Key)
            return {"Body": io.BytesIO(self.objects[Key])}

        def upload_file(self, Filename, Bucket, Key, ExtraArgs):
            self.objects[Key] = Path(Filename).read_bytes()

    client = FakeS3()
    monkeypatch.setenv("OBJECT_STORAGE_ENDPOINT", "https://account.r2.cloudflarestorage.com")
    monkeypatch.setenv("OBJECT_STORAGE_BUCKET", "study-media")
    monkeypatch.setenv("OBJECT_STORAGE_ACCESS_KEY_ID", "test-access")
    monkeypatch.setenv("OBJECT_STORAGE_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(object_storage, "_get_client", lambda: (client, object_storage._configuration()))
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "legacy_video.mp4").write_bytes(b"legacy video")
    (cache_dir / "legacy.thumb.jpg").write_bytes(b"legacy poster")
    monkeypatch.setattr(media_links, "_get_cache_dir", lambda: str(cache_dir))
    media_links.write_stream_entries([{"token": "legacy", "approved": True}])

    result = media_links.migrate_local_media_to_object_storage()
    entries = media_links.read_stream_entries()

    assert result == {"uploaded": 1, "missing": 0, "total": 1}
    assert client.objects["safe-repo/media/legacy_video.mp4"] == b"legacy video"
    assert client.objects["safe-repo/thumbnails/legacy.thumb.jpg"] == b"legacy poster"
    assert entries[0]["storage_key"] == "safe-repo/media/legacy_video.mp4"
    assert entries[0]["thumbnail_storage_key"] == "safe-repo/thumbnails/legacy.thumb.jpg"


def test_video_thumbnail_fallback_uses_frame_at_one_minute(tmp_path, monkeypatch):
    from safe_repo.core.func import generate_video_thumbnail

    positions = []

    class Capture:
        def isOpened(self):
            return True

        def get(self, prop):
            if prop == cv2.CAP_PROP_FRAME_COUNT:
                return 2000
            if prop == cv2.CAP_PROP_FPS:
                return 10
            return 0

        def set(self, prop, value):
            positions.append((prop, value))

        def read(self):
            return True, np.zeros((8, 8, 3), dtype=np.uint8)

        def release(self):
            return None

    monkeypatch.setattr(cv2, "VideoCapture", lambda _path: Capture())
    monkeypatch.setattr(cv2, "imwrite", lambda path, *_args: (Path(path).write_bytes(b"jpeg"), True)[1])
    output = tmp_path / "poster.jpg"

    assert media_links._create_media_thumbnail("lesson.mp4", str(output))
    assert positions == [(cv2.CAP_PROP_POS_FRAMES, 600)]
    positions.clear()
    assert generate_video_thumbnail("lesson.mp4", str(output))
    assert positions == [(cv2.CAP_PROP_POS_FRAMES, 600)]


def test_batch_media_publisher_adds_pdf_to_website_catalog(tmp_path, monkeypatch):
    from safe_repo.core.get_func import _publish_batch_media_to_site

    source = tmp_path / "lesson.pdf"
    source.write_bytes(b"pdf bytes")
    poster = tmp_path / "poster.jpg"
    assert cv2.imwrite(str(poster), np.zeros((8, 8, 3), dtype=np.uint8))
    catalog_path = tmp_path / "catalog.json"
    monkeypatch.setenv("STREAM_CATALOG_FILE", str(catalog_path))
    monkeypatch.setenv("STREAM_LINKS_FILE", str(tmp_path / "links.txt"))
    monkeypatch.setattr(media_links, "_STREAM_CACHE_DIR", str(tmp_path / "cache"))

    class BatchMessage:
        caption = "Lesson 4\nSubject: Physics"
        date = datetime(2024, 5, 6, 8, 30, tzinfo=timezone.utc)

    _publish_batch_media_to_site(str(source), str(poster), BatchMessage(), "pdf")
    assert _publish_batch_media_to_site(str(source), str(poster), BatchMessage(), "pdf") is None

    entries = read_stream_entries(str(catalog_path))
    assert len(entries) == 1
    assert entries[0]["title"] == "Lesson 4"
    assert entries[0]["subject"] == "Physics"
    assert entries[0]["media_type"] == "pdf"
    assert entries[0]["thumbnail_url"].endswith(f"/thumbnail/{entries[0]['token']}")
    assert entries[0]["approved"] is False
    assert entries[0]["date"] == "2024-05-06"
