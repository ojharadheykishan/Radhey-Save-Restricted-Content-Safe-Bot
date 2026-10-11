import asyncio
from urllib.parse import parse_qs, urlparse

from safe_repo.modules.stream import (
    build_local_file_name,
    build_public_stream_link,
    get_archive_chat_ids,
    get_message_media_size,
    format_progress_bar,
    has_media_payload,
    should_use_direct_channel_link,
)
import safe_repo.modules.stream as stream_module


class DummyMessage:
    message_id = 42

    class DummyMedia:
        pass

    video = DummyMedia()


def test_build_local_file_name_uses_video_extension():
    filename = build_local_file_name(DummyMessage())
    assert filename.startswith("stream_42_")
    assert filename.endswith(".mp4")


def test_build_local_file_name_falls_back_to_id():
    class MessageWithId:
        id = 77
        video = object()

    filename = build_local_file_name(MessageWithId())
    assert filename.startswith("stream_77_")
    assert filename.endswith(".mp4")


def test_build_local_file_name_preserves_video_document_extension():
    class VideoDocumentMessage:
        id = 88
        document = type("Document", (), {
            "mime_type": "video/mp4",
            "file_name": "lesson.mp4",
        })()

    filename = build_local_file_name(VideoDocumentMessage())

    assert filename.startswith("stream_88_")
    assert filename.endswith(".mp4")


def test_has_media_payload_for_forwarded_message():
    class ForwardedMessage:
        forwarded = True
        media = False

    assert has_media_payload(ForwardedMessage())


def test_has_media_payload_for_forward_origin_field():
    class ForwardOriginMessage:
        forward_origin = object()
        media = False

    assert has_media_payload(ForwardOriginMessage())


def test_gigabyte_media_uses_direct_channel_link():
    class LargeMediaMessage:
        document = type("Document", (), {"file_size": 1024 ** 3})()

    message = LargeMediaMessage()

    assert get_message_media_size(message) == 1024 ** 3
    assert should_use_direct_channel_link(message)


def test_large_media_handler_skips_local_download(monkeypatch):
    class LargeMessage:
        chat = type("Chat", (), {"id": 123})()
        document = type("Document", (), {"file_size": 1024 ** 3, "mime_type": "video/mp4"})()
        caption = "Subject: Physics"

    class FakeApp:
        def __init__(self):
            self.edits = []

        async def send_message(self, chat_id, text):
            return type("Status", (), {"id": 7})()

        async def edit_message_text(self, chat_id, message_id, text):
            self.edits.append(text)

    async def fast_link(_message):
        return {
            "source": "channel",
            "player_url": "https://t.me/public/55?embed=1",
            "stream_url": "https://t.me/public/55",
            "token": None,
        }

    async def unexpected_download(*args, **kwargs):
        raise AssertionError("large media should not be downloaded locally")

    async def no_op(*args, **kwargs):
        return None

    fake_app = FakeApp()
    catalog_entries = []
    admin_notifications = []
    async def capture_admin_notification(*args, **kwargs):
        admin_notifications.append((args, kwargs))

    monkeypatch.setattr(stream_module, "app", fake_app)
    monkeypatch.setattr(stream_module, "build_direct_channel_stream_link", fast_link)
    monkeypatch.setattr(stream_module, "download_media_payload", unexpected_download)
    monkeypatch.setattr(
        stream_module,
        "append_stream_link",
        lambda *args, **kwargs: catalog_entries.append((args, kwargs)),
    )
    monkeypatch.setattr(stream_module, "archive_media_for_premium", no_op)
    monkeypatch.setattr(stream_module, "archive_stream_link", no_op)
    monkeypatch.setattr("safe_repo.web.notifications.notify_new_media", capture_admin_notification)
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://study.example")

    asyncio.run(stream_module.handle_direct_media(object(), LargeMessage()))

    assert any("https://t.me/public/55" in text for text in fake_app.edits)
    assert catalog_entries[0][1]["approved"] is False
    assert catalog_entries[0][0][0] == "https://t.me/public/55?embed=1"
    review_token = catalog_entries[0][1]["token"]
    notification_args, notification_kwargs = admin_notifications[0]
    review_url = urlparse(notification_args[1])
    assert review_url.path == "/admin/login"
    assert parse_qs(review_url.query)["next"] == [f"/admin/edit/{review_token}"]
    assert notification_kwargs["admin_only"] is True


def test_video_without_persistent_storage_uses_shared_web_cache(tmp_path, monkeypatch):
    source = tmp_path / "lesson.mp4"
    source.write_bytes(b"video")
    cached_media = tmp_path / "cache" / "cached-lesson.mp4"
    cached_media.parent.mkdir()
    cached_media.write_bytes(b"video")
    cached_thumbnail = cached_media.parent / "cached-token.thumb.jpg"
    cached_thumbnail.write_bytes(b"thumbnail")

    class VideoDocumentMessage:
        document = type(
            "Document",
            (),
            {"mime_type": "application/octet-stream", "file_name": "lesson.mp4"},
        )()

    monkeypatch.setattr(stream_module, "find_duplicate_media", lambda _path: None)
    monkeypatch.setattr(
        stream_module,
        "save_stream_file",
        lambda *_args, **_kwargs: {
            "token": "cached-token",
            "file_path": str(cached_media),
            "player_url": "https://study.example/player/cached-token",
            "stream_url": "https://study.example/stream/cached-token",
        },
    )

    async def unexpected_channel_post(_message):
        raise AssertionError("a successful shared cache should not require channel permissions")

    monkeypatch.setattr(stream_module, "post_to_stream_channel", unexpected_channel_post)

    public_link = asyncio.run(build_public_stream_link(VideoDocumentMessage(), str(source)))

    assert public_link["source"] == "cache"
    assert public_link["player_url"] == "https://study.example/player/cached-token"
    assert public_link["stream_url"] == "https://study.example/stream/cached-token"
    assert cached_media.exists()
    assert cached_thumbnail.exists()


def test_video_cache_failure_falls_back_to_telegram_player(tmp_path, monkeypatch):
    source = tmp_path / "lesson.mp4"
    source.write_bytes(b"video")

    class VideoMessage:
        video = object()

    async def channel_post(_message):
        return {
            "embed": "https://t.me/public_channel/55?embed=1",
            "link": "https://t.me/public_channel/55",
        }

    monkeypatch.setattr(stream_module, "find_duplicate_media", lambda _path: None)
    monkeypatch.setattr(stream_module, "save_stream_file", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(stream_module, "post_to_stream_channel", channel_post)

    public_link = asyncio.run(build_public_stream_link(VideoMessage(), str(source)))

    assert public_link["source"] == "channel"
    assert public_link["player_url"] == "https://t.me/public_channel/55?embed=1"
    assert public_link["stream_url"] == "https://t.me/public_channel/55"
    assert public_link["token"]


def test_video_with_persistent_storage_uses_web_player_link(tmp_path, monkeypatch):
    source = tmp_path / "lesson.mp4"
    source.write_bytes(b"video")

    class VideoMessage:
        video = object()

    saved = {
        "token": "persistent-token",
        "file_path": str(tmp_path / "persistent.mp4"),
        "player_url": "https://study.example/player/persistent-token",
        "stream_url": "https://study.example/stream/persistent-token",
        "storage_key": "media/persistent.mp4",
    }
    monkeypatch.setattr(stream_module, "find_duplicate_media", lambda _path: None)
    monkeypatch.setattr(stream_module, "save_stream_file", lambda *_args, **_kwargs: saved)

    async def unexpected_channel_post(_message):
        raise AssertionError("persistent media should not need a Telegram fallback")

    monkeypatch.setattr(stream_module, "post_to_stream_channel", unexpected_channel_post)

    public_link = asyncio.run(build_public_stream_link(VideoMessage(), str(source)))

    assert public_link["source"] == "cache"
    assert public_link["player_url"] == saved["player_url"]
    assert public_link["storage_key"] == saved["storage_key"]


def test_get_archive_chat_ids_includes_configured_channel(monkeypatch):
    monkeypatch.delenv("ARCHIVE_CHAT_ID", raising=False)
    monkeypatch.delenv("CLONE_LOG_CHANNEL", raising=False)
    ids = get_archive_chat_ids()
    assert -1003886456761 in ids


def test_format_progress_bar_contains_percentage_and_label():
    text = format_progress_bar(60, "Downloading media", "Please wait")
    assert "60%" in text
    assert "Downloading media" in text
    assert "Please wait" in text
    assert any(color in text for color in ("🟥", "🟧", "🟨", "🟩", "🟦", "🟪"))


def test_format_progress_bar_animates_between_frames():
    first_frame = format_progress_bar(60, frame=0)
    next_frame = format_progress_bar(60, frame=1)

    assert first_frame != next_frame


def test_download_media_payload_limits_concurrent_downloads(monkeypatch):
    class ConcurrentMessage:
        message_id = 101
        video = object()

    class ConcurrentClient:
        active_downloads = 0
        peak_downloads = 0

        async def download_media(self, message, **kwargs):
            self.active_downloads += 1
            self.peak_downloads = max(self.peak_downloads, self.active_downloads)
            await asyncio.sleep(0.01)
            self.active_downloads -= 1
            return kwargs["file_name"]

    async def run_batch():
        monkeypatch.setattr(stream_module, "_MEDIA_DOWNLOAD_SEMAPHORE", asyncio.Semaphore(4))
        client = ConcurrentClient()
        results = await asyncio.gather(
            *(stream_module.download_media_payload(client, ConcurrentMessage()) for _ in range(12))
        )
        return client, results

    client, results = asyncio.run(run_batch())

    assert len(results) == 12
    assert client.peak_downloads == 4
