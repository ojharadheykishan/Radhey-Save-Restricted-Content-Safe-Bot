import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import safe_repo.core.media_links as media_links
import safe_repo.web.users as users_module
from app import app as flask_app
from safe_repo.web.study import build_public_study_url, build_video_index, load_catalog_entries


def test_load_catalog_entries_normalizes_video_metadata(tmp_path):
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps([
        {
            "token": "abc123",
            "title": "Motion Chapter 1",
            "description": "Study video",
            "subject": "Physics",
            "category": "Class 11",
            "player_url": "https://example.com/player/abc123",
            "stream_url": "https://example.com/stream/abc123",
            "thumbnail_url": "https://example.com/thumbnail/abc123",
            "media_type": "pdf",
            "timestamp": "2026-08-02 10:00:00"
        }
    ]), encoding="utf-8")

    entries = load_catalog_entries(str(catalog_path))
    assert len(entries) == 1
    assert entries[0]["watch_url"].endswith("/watch/abc123")
    assert entries[0]["subject"] == "Physics"
    assert entries[0]["category"] == "Class 11"
    assert entries[0]["thumbnail_url"] == "https://example.com/thumbnail/abc123"
    assert entries[0]["media_type"] == "pdf"


def test_home_route_renders_filtered_catalog_for_subject_date_queries(monkeypatch, tmp_path):
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps([
        {
            "token": "one",
            "title": "Alpha",
            "description": "Folder: Mechanics\nStudy video",
            "subject": "Physics",
            "category": "Class 11",
            "player_url": "https://example.com/player/one",
            "stream_url": "https://example.com/stream/one",
            "timestamp": "2026-08-02 10:00:00",
            "date": "2026-08-02"
        }
    ]), encoding="utf-8")
    monkeypatch.setenv("STREAM_CATALOG_FILE", str(catalog_path))

    client = flask_app.test_client()
    response = client.get("/?subject=Physics&date=2026-08-02&q=Alpha")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Showing results for" in html
    assert "Physics" in html
    assert "Alpha" in html
    assert 'src="/thumbnail/one"' in html
    assert 'aria-label="Filter by folder"' in html
    assert 'aria-label="Filter by subfolder"' in html


def test_folder_selector_exposes_existing_subfolder_and_keeps_filters(tmp_path, monkeypatch):
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps([
        {"token": "one", "title": "Mechanics", "subject": "Physics", "description": "Folder: Physics\nSubfolder: Mechanics"},
    ]), encoding="utf-8")
    monkeypatch.setenv("STREAM_CATALOG_FILE", str(catalog_path))

    response = flask_app.test_client().get("/?folder=Physics&subfolder=Mechanics")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert '<option value="Physics" selected>' in html
    assert '<option value="Mechanics" data-folder="Physics" selected>' in html


def test_build_video_index_groups_latest_and_featured(tmp_path):
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps([
        {
            "token": "one",
            "title": "Alpha",
            "description": "A",
            "subject": "Physics",
            "category": "Class 11",
            "player_url": "https://example.com/player/one",
            "stream_url": "https://example.com/stream/one",
            "timestamp": "2026-08-02 10:00:00",
            "featured": True,
            "trending": True,
            "views": 12
        },
        {
            "token": "two",
            "title": "Beta",
            "description": "B",
            "subject": "Chemistry",
            "category": "Class 12",
            "player_url": "https://example.com/player/two",
            "stream_url": "https://example.com/stream/two",
            "timestamp": "2026-08-02 11:00:00",
            "views": 5
        }
    ]), encoding="utf-8")

    index = build_video_index(str(catalog_path))
    assert index["featured"][0]["token"] == "one"
    assert index["latest"][0]["token"] == "two"
    assert index["trending"][0]["token"] == "one"
    assert index["subjects"][0]["name"] == "Physics"


def test_build_video_index_filters_by_subject_and_date(tmp_path):
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps([
        {
            "token": "one",
            "title": "Alpha",
            "description": "A",
            "subject": "Physics",
            "category": "Class 11",
            "player_url": "https://example.com/player/one",
            "stream_url": "https://example.com/stream/one",
            "timestamp": "2026-08-02 10:00:00",
            "date": "2026-08-02"
        },
        {
            "token": "two",
            "title": "Beta",
            "description": "B",
            "subject": "Chemistry",
            "category": "Class 12",
            "player_url": "https://example.com/player/two",
            "stream_url": "https://example.com/stream/two",
            "timestamp": "2026-08-03 11:00:00",
            "date": "2026-08-03"
        }
    ]), encoding="utf-8")

    index = build_video_index(str(catalog_path), subject="Physics", date="2026-08-02")
    assert [video["token"] for video in index["videos"]] == ["one"]
    assert index["filter_summary"]["subject"] == "Physics"
    assert index["filter_summary"]["date"] == "2026-08-02"


def test_build_public_study_url_includes_filters():
    url = build_public_study_url("https://example.com", subject="Physics", date="2026-08-02", q="motion")
    assert url == "https://example.com/study?subject=Physics&date=2026-08-02&q=motion"


def test_build_public_study_url_defaults_to_home_page_when_no_filters():
    url = build_public_study_url("https://example.com")
    assert url == "https://example.com/"


def test_append_stream_link_is_visible_to_study_catalog_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("STREAM_CATALOG_FILE", raising=False)
    monkeypatch.setattr(media_links, "_STREAM_CACHE_DIR", str(tmp_path / "cache"))

    catalog_path = Path("safe_repo/core/mongo/stream_catalog.json")
    backup_text = catalog_path.read_text(encoding="utf-8") if catalog_path.exists() else None
    archive_path = Path("safe_repo/core/mongo/stream_links.txt")
    archive_backup = archive_path.read_text(encoding="utf-8") if archive_path.exists() else None

    try:
        media_links.append_stream_link(
            "https://example.com/player/test",
            "https://example.com/stream/test",
            subject="Physics",
            description="Forwarded task media",
            title="Task Media",
            token="task-token",
        )
        entries = load_catalog_entries()
        assert any(entry.get("token") == "task-token" for entry in entries)
    finally:
        if backup_text is None:
            catalog_path.unlink(missing_ok=True)
        else:
            catalog_path.write_text(backup_text, encoding="utf-8")
        if archive_backup is None:
            archive_path.unlink(missing_ok=True)
        else:
            archive_path.write_text(archive_backup, encoding="utf-8")


def test_build_video_index_groups_videos_by_folder_from_description(tmp_path):
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps([
        {
            "token": "one",
            "title": "Alpha",
            "description": "Folder: Mechanics\nStudy video",
            "subject": "Physics",
            "category": "Class 11",
            "player_url": "https://example.com/player/one",
            "stream_url": "https://example.com/stream/one",
            "timestamp": "2026-08-02 10:00:00",
            "date": "2026-08-02"
        }
    ]), encoding="utf-8")

    index = build_video_index(str(catalog_path))
    assert index["folders"][0]["name"] == "Mechanics"
    assert index["folders"][0]["count"] == 1


def test_build_video_index_exposes_subject_playlists(tmp_path):
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps([
        {
            "token": "one",
            "title": "Alpha",
            "description": "Folder: Mechanics\nA",
            "subject": "Physics",
            "category": "Class 11",
            "player_url": "https://example.com/player/one",
            "stream_url": "https://example.com/stream/one",
            "timestamp": "2026-08-02 10:00:00",
            "date": "2026-08-02"
        },
        {
            "token": "two",
            "title": "Beta",
            "description": "Folder: Mechanics\nB",
            "subject": "Physics",
            "category": "Class 11",
            "player_url": "https://example.com/player/two",
            "stream_url": "https://example.com/stream/two",
            "timestamp": "2026-08-03 10:00:00",
            "date": "2026-08-03"
        }
    ]), encoding="utf-8")

    index = build_video_index(str(catalog_path))
    assert index["playlists"][0]["subject"] == "Physics"
    assert index["playlists"][0]["folder"] == "Mechanics"
    assert len(index["playlists"][0]["videos"]) == 2


def test_playlist_count_includes_items_beyond_preview_limit(tmp_path):
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps([
        {
            "token": str(index),
            "title": f"Lesson {index}",
            "description": "Folder: Mechanics",
            "subject": "Physics",
            "timestamp": f"2026-08-{index + 1:02d} 10:00:00",
        }
        for index in range(7)
    ]), encoding="utf-8")

    playlist = build_video_index(str(catalog_path))["playlists"][0]

    assert playlist["count"] == 7
    assert len(playlist["videos"]) == 6


def test_public_index_hides_pending_and_searches_pdf_and_transcript(tmp_path):
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps([
        {"token": "public", "title": "Notes", "media_type": "pdf", "pdf_text": "Momentum is conserved", "transcript": "Chapter review", "approved": True},
        {"token": "pending", "title": "Pending Notes", "pdf_text": "Momentum", "approved": False},
    ]), encoding="utf-8")

    index = build_video_index(str(catalog_path), q="conserved", media_type="pdf")

    assert [item["token"] for item in index["videos"]] == ["public"]


def test_custom_playlist_filters_and_orders_items(tmp_path):
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps([
        {"token": "third", "title": "Third", "subject": "Physics", "folder": "General", "playlist": "Revision", "sort_order": 3},
        {"token": "first", "title": "First", "subject": "Physics", "folder": "General", "playlist": "Revision", "sort_order": 1},
        {"token": "second", "title": "Second", "subject": "Physics", "folder": "General", "playlist": "Revision", "sort_order": 2},
    ]), encoding="utf-8")

    index = build_video_index(str(catalog_path), playlist="Revision")

    assert [item["token"] for item in index["videos"]] == ["third", "first", "second"]
    assert [item["token"] for item in index["playlists"][0]["videos"]] == ["first", "second", "third"]


def test_advanced_search_indexes_pdf_text_and_excludes_pending(tmp_path, monkeypatch):
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps([
        {"token": "visible", "title": "Notes", "media_type": "pdf", "pdf_text": "Conservation theorem", "approved": True},
        {"token": "hidden", "title": "Pending notes", "pdf_text": "Conservation theorem", "approved": False},
    ]), encoding="utf-8")
    monkeypatch.setenv("STREAM_CATALOG_FILE", str(catalog_path))

    response = flask_app.test_client().get("/api/search/advanced?q=conservation&media_type=pdf")

    assert response.status_code == 200
    assert [item["token"] for item in response.get_json()["videos"]] == ["visible"]


def test_watch_progress_resumes_and_counts_completion_once(tmp_path, monkeypatch):
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps([{"token": "resume-me", "title": "Lesson", "approved": True, "completion_count": 0}]), encoding="utf-8")
    monkeypatch.setenv("STREAM_CATALOG_FILE", str(catalog_path))
    monkeypatch.setattr(users_module, "PROFILES_FILE", tmp_path / "profiles.json")
    client = flask_app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = "learner-1"

    saved = client.post("/api/videos/resume-me/progress", json={"progress": 0.45})
    assert saved.get_json()["tracked"] is True
    resumed = client.get("/api/videos/resume-me/progress")
    assert resumed.get_json()["progress"] == 0.45
    client.post("/api/videos/resume-me/progress", json={"progress": 0.97})
    client.post("/api/videos/resume-me/progress", json={"progress": 1})
    client.post("/api/videos/resume-me/progress", json={"progress": 0.2})
    client.post("/api/videos/resume-me/progress", json={"progress": 1})

    entry = json.loads(catalog_path.read_text(encoding="utf-8"))[0]
    assert entry["completion_count"] == 1


def test_editor_role_cannot_delete_or_change_approval(tmp_path, monkeypatch):
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps([{"token": "one", "approved": False, "folder": "General"}]), encoding="utf-8")
    monkeypatch.setenv("STREAM_CATALOG_FILE", str(catalog_path))
    client = flask_app.test_client()
    with client.session_transaction() as session:
        session["is_admin"] = True
        session["admin_role"] = "editor"

    forbidden = client.post("/api/admin/videos/bulk", json={"action": "approve", "tokens": ["one"]})
    updated = client.post("/api/admin/videos/bulk", json={"action": "folder", "tokens": ["one"], "value": "Physics"})

    assert forbidden.status_code == 403
    assert updated.status_code == 200
    assert json.loads(catalog_path.read_text(encoding="utf-8"))[0]["folder"] == "Physics"


def test_admin_edit_saves_transcript_vtt_playlist_and_approval(tmp_path, monkeypatch):
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps([{
        "token": "media-one",
        "title": "Lesson",
        "subject": "Physics",
        "category": "Class 11",
        "folder": "General",
        "approved": False,
        "player_url": "https://example.com/player/media-one",
        "stream_url": "https://example.com/stream/media-one",
    }]), encoding="utf-8")
    monkeypatch.setenv("STREAM_CATALOG_FILE", str(catalog_path))
    client = flask_app.test_client()
    with client.session_transaction() as session:
        session["is_admin"] = True
        session["admin_role"] = "owner"

    response = client.post("/admin/edit/media-one", data={
        "title": "Lesson one",
        "subject": "Physics",
        "category": "Class 11",
        "folder": "Mechanics",
        "subfolder": "",
        "description": "Lesson description",
        "transcript": "Momentum notes",
        "subtitles": "WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nHello\n",
        "playlist": "Exam revision",
        "sort_order": "3",
        "approved": ["off", "on"],
    })

    assert response.status_code == 302
    entry = json.loads(catalog_path.read_text(encoding="utf-8"))[0]
    assert entry["transcript"] == "Momentum notes"
    assert entry["playlist"] == "Exam revision"
    assert entry["sort_order"] == 3
    assert entry["approved"] is True
    captions = client.get("/captions/media-one.vtt")
    assert captions.status_code == 200
    assert captions.mimetype == "text/vtt"


def test_admin_roles_can_be_configured_from_environment(monkeypatch):
    monkeypatch.setenv("STUDY_ADMIN_USERS", json.dumps({
        "library-editor": {"password": "not-a-real-secret", "role": "editor"},
    }))
    client = flask_app.test_client()

    response = client.post("/admin/login", data={"username": "library-editor", "password": "not-a-real-secret"})

    assert response.status_code == 302
    with client.session_transaction() as session:
        assert session["admin_role"] == "editor"


def test_push_configuration_requires_vapid_environment(monkeypatch):
    monkeypatch.delenv("VAPID_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("VAPID_CLAIMS_EMAIL", raising=False)

    response = flask_app.test_client().get("/api/push/config")

    assert response.status_code == 200
    assert response.get_json()["enabled"] is False


def test_build_video_index_filters_by_folder(tmp_path):
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps([
        {
            "token": "one",
            "title": "Alpha",
            "description": "Folder: Mechanics\nA",
            "subject": "Physics",
            "category": "Class 11",
            "player_url": "https://example.com/player/one",
            "stream_url": "https://example.com/stream/one",
            "timestamp": "2026-08-02 10:00:00",
            "date": "2026-08-02"
        },
        {
            "token": "two",
            "title": "Beta",
            "description": "Folder: Waves\nB",
            "subject": "Physics",
            "category": "Class 11",
            "player_url": "https://example.com/player/two",
            "stream_url": "https://example.com/stream/two",
            "timestamp": "2026-08-03 10:00:00",
            "date": "2026-08-03"
        }
    ]), encoding="utf-8")

    index = build_video_index(str(catalog_path), subject="Physics", folder="Mechanics")
    assert [video["token"] for video in index["videos"]] == ["one"]


def test_admin_bulk_action_updates_and_deletes_selected_entries(tmp_path, monkeypatch):
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps([
        {"token": "one", "title": "Alpha", "featured": False},
        {"token": "two", "title": "Beta", "featured": False},
    ]), encoding="utf-8")
    monkeypatch.setenv("STREAM_CATALOG_FILE", str(catalog_path))
    client = flask_app.test_client()
    with client.session_transaction() as session:
        session["is_admin"] = True

    dashboard = client.get("/admin/dashboard")
    assert dashboard.status_code == 200
    assert "admin-table-select-all" in dashboard.get_data(as_text=True)
    dashboard_html = dashboard.get_data(as_text=True)
    assert "media-search" in dashboard_html
    assert "media-preview-modal" in dashboard_html
    assert "export-media" in dashboard_html

    response = client.post("/api/admin/videos/bulk", json={"action": "featured", "tokens": ["one"]})
    assert response.status_code == 200
    assert response.get_json()["updated"] == 1
    assert json.loads(catalog_path.read_text(encoding="utf-8"))[0]["featured"] is True

    response = client.post("/api/admin/videos/bulk", json={"action": "delete", "tokens": ["two"]})
    assert response.status_code == 200
    assert [entry["token"] for entry in json.loads(catalog_path.read_text(encoding="utf-8"))] == ["one"]


def test_study_page_labels_and_links_pdf_items(tmp_path, monkeypatch):
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps([
        {
            "token": "pdf-one",
            "title": "Physics Notes",
            "subject": "Physics",
            "media_type": "pdf",
            "player_url": "https://example.com/player/pdf-one",
            "stream_url": "https://example.com/stream/pdf-one",
        }
    ]), encoding="utf-8")
    monkeypatch.setenv("STREAM_CATALOG_FILE", str(catalog_path))

    response = flask_app.test_client().get("/study")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Media Library" in html
    assert ">PDF<" in html
    assert "fa-file-pdf" in html
