from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import telegram_io


class _FakeBot:
    def __init__(self):
        self.send_photo = AsyncMock()
        self.send_video = AsyncMock()
        self.send_document = AsyncMock()
        self.send_media_group = AsyncMock()


def _make_context():
    ctx = MagicMock()
    ctx.bot = _FakeBot()
    return ctx


@pytest.mark.asyncio
async def test_send_video_passes_path_and_timeouts(tmp_path):
    f = tmp_path / "vid.mp4"
    f.write_bytes(b"x")
    ctx = _make_context()

    with patch.object(telegram_io, "cfg", lambda key: 600 if key == "TELEGRAM_UPLOAD_TIMEOUT" else 10):
        await telegram_io.send_downloaded_media(
            context=ctx,
            chat_id=1,
            files=[str(f)],
            original_msg_id=10,
            upload_kwargs={},
        )

    kwargs = ctx.bot.send_video.await_args.kwargs
    assert kwargs["video"] == str(f)
    assert kwargs["read_timeout"] == 600
    assert kwargs["write_timeout"] == 600
    assert kwargs["connect_timeout"] == 600


@pytest.mark.asyncio
async def test_send_photo_passes_path_and_timeouts(tmp_path):
    f = tmp_path / "img.jpg"
    f.write_bytes(b"x")
    ctx = _make_context()

    with patch.object(telegram_io, "cfg", lambda key: 600 if key == "TELEGRAM_UPLOAD_TIMEOUT" else 10):
        await telegram_io.send_downloaded_media(
            context=ctx,
            chat_id=1,
            files=[str(f)],
            original_msg_id=10,
            upload_kwargs={},
        )

    kwargs = ctx.bot.send_photo.await_args.kwargs
    assert kwargs["photo"] == str(f)
    assert kwargs["read_timeout"] == 600
    assert kwargs["write_timeout"] == 600
    assert kwargs["connect_timeout"] == 600


@pytest.mark.asyncio
async def test_send_document_passes_path_and_timeouts(tmp_path):
    f = tmp_path / "blob.bin"
    f.write_bytes(b"x")
    ctx = _make_context()

    with patch.object(telegram_io, "cfg", lambda key: 600 if key == "TELEGRAM_UPLOAD_TIMEOUT" else 10):
        await telegram_io.send_downloaded_media(
            context=ctx,
            chat_id=1,
            files=[str(f)],
            original_msg_id=10,
            upload_kwargs={},
        )

    kwargs = ctx.bot.send_document.await_args.kwargs
    assert kwargs["document"] == str(f)
    assert kwargs["read_timeout"] == 600
    assert kwargs["write_timeout"] == 600
    assert kwargs["connect_timeout"] == 600


@pytest.mark.asyncio
async def test_caller_overrides_take_precedence(tmp_path):
    f = tmp_path / "vid.mp4"
    f.write_bytes(b"x")
    ctx = _make_context()

    with patch.object(telegram_io, "cfg", lambda key: 600 if key == "TELEGRAM_UPLOAD_TIMEOUT" else 10):
        await telegram_io.send_downloaded_media(
            context=ctx,
            chat_id=1,
            files=[str(f)],
            original_msg_id=10,
            upload_kwargs={"write_timeout": 9999},
        )

    kwargs = ctx.bot.send_video.await_args.kwargs
    assert kwargs["write_timeout"] == 9999
    assert kwargs["read_timeout"] == 600


@pytest.mark.asyncio
async def test_media_group_passes_paths_and_timeouts(tmp_path):
    a = tmp_path / "a.jpg"
    b = tmp_path / "b.jpg"
    a.write_bytes(b"x")
    b.write_bytes(b"y")
    ctx = _make_context()

    def fake_cfg(key):
        return {
            "TELEGRAM_UPLOAD_TIMEOUT": 600,
            "MEDIA_GROUP_CHUNK_SIZE": 10,
            "MEDIA_GROUP_DELAY": 0,
        }[key]

    with patch.object(telegram_io, "cfg", fake_cfg):
        await telegram_io.send_downloaded_media(
            context=ctx,
            chat_id=1,
            files=[str(a), str(b)],
            original_msg_id=10,
            upload_kwargs={},
        )

    kwargs = ctx.bot.send_media_group.await_args.kwargs
    media = kwargs["media"]
    assert len(media) == 2
    assert media[0].media == a.absolute().as_uri()
    assert media[1].media == b.absolute().as_uri()
    assert kwargs["read_timeout"] == 600
    assert kwargs["write_timeout"] == 600
    assert kwargs["connect_timeout"] == 600
