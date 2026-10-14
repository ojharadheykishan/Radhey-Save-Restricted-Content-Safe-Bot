import asyncio
import gzip
import json
from pathlib import Path
from types import SimpleNamespace

from safe_repo.core import func


def test_progress_sticker_is_sent_once_and_removed_when_transfer_finishes(tmp_path, monkeypatch):
    sticker_path = tmp_path / "progress.tgs"
    sticker_path.write_bytes(b"test sticker")
    monkeypatch.setattr(func, "PROGRESS_STICKER_PATH", str(sticker_path))
    func._progress_sticker_messages.clear()
    func.progress_bar.last_update = 0

    class FakeStickerMessage:
        deleted = False

        async def delete(self):
            self.deleted = True

    class FakeClient:
        def __init__(self):
            self.stickers = []

        async def send_sticker(self, **kwargs):
            assert kwargs["chat_id"] == 123
            assert kwargs["reply_to_message_id"] == 456
            sticker_message = FakeStickerMessage()
            self.stickers.append(sticker_message)
            return sticker_message

    class FakeStatusMessage:
        id = 456
        chat = SimpleNamespace(id=123)

        def __init__(self, client):
            self._client = client

        async def edit(self, _text):
            return None

    client = FakeClient()
    status_message = FakeStatusMessage(client)

    async def run_progress():
        await func.progress_bar(10, 100, "📥 Downloading...", status_message)
        await func.progress_bar(50, 100, "📥 Downloading...", status_message)

    asyncio.run(run_progress())

    assert len(client.stickers) == 1
    assert not client.stickers[0].deleted

    asyncio.run(func.progress_bar(100, 100, "📤 Uploading...", status_message))

    assert client.stickers[0].deleted
    assert not func._progress_sticker_messages


def test_progress_sticker_asset_is_a_short_animated_tgs():
    asset_path = Path(func.PROGRESS_STICKER_PATH)
    animation = json.loads(gzip.decompress(asset_path.read_bytes()))

    assert animation["w"] == 512
    assert animation["h"] == 512
    assert (animation["op"] - animation["ip"]) / animation["fr"] <= 3
    assert animation["layers"][0]["ks"]["r"]["a"] == 1
