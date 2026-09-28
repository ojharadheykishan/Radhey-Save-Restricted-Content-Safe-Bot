import os
import sys
import tempfile
from pathlib import Path

import cv2
import fitz
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import safe_repo.core.media_links as media_links
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

    _publish_batch_media_to_site(str(source), str(poster), BatchMessage(), "pdf")
    assert _publish_batch_media_to_site(str(source), str(poster), BatchMessage(), "pdf") is None

    entries = read_stream_entries(str(catalog_path))
    assert len(entries) == 1
    assert entries[0]["title"] == "Lesson 4"
    assert entries[0]["subject"] == "Physics"
    assert entries[0]["media_type"] == "pdf"
    assert entries[0]["thumbnail_url"].endswith(f"/thumbnail/{entries[0]['token']}")
    assert entries[0]["approved"] is False
