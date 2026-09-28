import os
import io

import cv2
import numpy as np

from app import app, build_stream_response
import safe_repo.core.media_links as media_links


def test_build_stream_response_uses_inline_video_mimetype(tmp_path):
    media_path = tmp_path / "sample.mp4"
    media_path.write_bytes(b"fake mp4")

    with app.test_request_context('/'):
        response = build_stream_response(str(media_path), as_attachment=False)

    assert response.mimetype == "video/mp4"
    assert "inline" in response.headers.get("Content-Disposition", "")


def test_build_stream_response_uses_attachment_for_download(tmp_path):
    media_path = tmp_path / "sample.mp4"
    media_path.write_bytes(b"fake mp4")

    with app.test_request_context('/'):
        response = build_stream_response(str(media_path), as_attachment=True)

    assert response.mimetype == "video/mp4"
    assert "attachment" in response.headers.get("Content-Disposition", "")


def test_thumbnail_route_serves_cached_poster(tmp_path, monkeypatch):
    source = tmp_path / "sample.mp4"
    source.write_bytes(b"test media")
    poster = tmp_path / "poster.jpg"
    assert cv2.imwrite(str(poster), np.zeros((8, 8, 3), dtype=np.uint8))
    monkeypatch.setattr(media_links, "_STREAM_CACHE_DIR", str(tmp_path / "cache"))
    saved = media_links.save_stream_file(str(source), thumbnail_path=str(poster))

    response = app.test_client().get(f"/thumbnail/{saved['token']}")

    assert response.status_code == 200
    assert response.mimetype == "image/jpeg"


def test_admin_can_replace_cached_thumbnail(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    catalog_path = tmp_path / "catalog.json"
    monkeypatch.setenv("STREAM_CATALOG_FILE", str(catalog_path))
    source = tmp_path / "sample.mp4"
    source.write_bytes(b"test media")
    saved = media_links.save_stream_file(str(source), cache_dir=str(cache_dir))
    media_links.append_stream_link(
        saved["player_url"], saved["stream_url"],
        archive_path=str(tmp_path / "links.txt"), catalog_path=str(catalog_path),
        token=saved["token"],
    )
    replacement = np.full((16, 16, 3), 200, dtype=np.uint8)
    success, encoded = cv2.imencode(".jpg", replacement)
    assert success
    client = app.test_client()
    with client.session_transaction() as session:
        session["is_admin"] = True
        session["admin_role"] = "owner"

    response = client.post(
        f"/admin/thumbnail/{saved['token']}",
        data={"thumbnail": (io.BytesIO(encoded.tobytes()), "poster.jpg")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 302
    assert (cache_dir / f"{saved['token']}.thumb.jpg").stat().st_size > 0


def test_pending_media_cannot_be_streamed_without_admin(tmp_path, monkeypatch):
    source = tmp_path / "sample.mp4"
    source.write_bytes(b"pending video")
    catalog_path = tmp_path / "catalog.json"
    monkeypatch.setenv("STREAM_CATALOG_FILE", str(catalog_path))
    saved = media_links.save_stream_file(str(source), cache_dir=str(tmp_path / "cache"))
    media_links.append_stream_link(
        saved["player_url"], saved["stream_url"],
        archive_path=str(tmp_path / "links.txt"),
        catalog_path=str(catalog_path),
        token=saved["token"], approved=False,
    )

    client = app.test_client()
    assert client.get(f"/stream/{saved['token']}").status_code == 404
    assert client.get(f"/player/{saved['token']}").status_code == 404
