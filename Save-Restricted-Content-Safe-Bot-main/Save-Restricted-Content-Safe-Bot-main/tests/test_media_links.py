import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
    )

    assert archive_path.exists()
    assert entry_path.exists()
    entries = read_stream_entries(catalog_path=str(entry_path))
    assert len(entries) == 1
    assert entries[0]["subject"] == "Movie"
    assert entries[0]["token"] == "demo"
