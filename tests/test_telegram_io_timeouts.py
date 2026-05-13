from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import telegram_io


class _FakeBot:
    def __init__(self):
        self.send_photo = AsyncMock()
        self.send_video = AsyncMock()
        self.send_animation = AsyncMock()
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
async def test_gif_converts_to_mp4_and_routes_to_send_animation(tmp_path):
    from PIL import Image
    f = tmp_path / "loop.gif"
    Image.new("RGB", (480, 360), color="red").save(f, format="GIF")
    mp4 = tmp_path / "loop.gif.mp4"

    async def fake_gif_to_mp4(input_path, output_path, timeout=60):
        with open(output_path, "wb") as fp:
            fp.write(b"fake-mp4")
        return True

    ctx = _make_context()
    with patch.object(telegram_io, "cfg", lambda key: 600 if key == "TELEGRAM_UPLOAD_TIMEOUT" else 10), \
         patch.object(telegram_io, "async_gif_to_mp4", fake_gif_to_mp4):
        await telegram_io.send_downloaded_media(
            context=ctx,
            chat_id=1,
            files=[str(f)],
            original_msg_id=10,
            upload_kwargs={},
        )

    assert ctx.bot.send_animation.await_count == 1
    assert ctx.bot.send_video.await_count == 0
    kwargs = ctx.bot.send_animation.await_args.kwargs
    assert kwargs["animation"] == str(mp4)
    assert kwargs["width"] == 480
    assert kwargs["height"] == 360


@pytest.mark.asyncio
async def test_gif_falls_back_to_original_when_conversion_fails(tmp_path):
    from PIL import Image
    f = tmp_path / "loop.gif"
    Image.new("RGB", (320, 200), color="blue").save(f, format="GIF")

    async def failing_gif_to_mp4(input_path, output_path, timeout=60):
        return False

    ctx = _make_context()
    with patch.object(telegram_io, "cfg", lambda key: 600 if key == "TELEGRAM_UPLOAD_TIMEOUT" else 10), \
         patch.object(telegram_io, "async_gif_to_mp4", failing_gif_to_mp4):
        await telegram_io.send_downloaded_media(
            context=ctx,
            chat_id=1,
            files=[str(f)],
            original_msg_id=10,
            upload_kwargs={},
        )

    kwargs = ctx.bot.send_animation.await_args.kwargs
    assert kwargs["animation"] == str(f)
    assert kwargs["width"] == 320
    assert kwargs["height"] == 200


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
async def test_video_webm_converts_before_send(tmp_path):
    f = tmp_path / "clip.webm"
    f.write_bytes(b"x")
    converted = tmp_path / "clip.tg.mp4"

    async def fake_ensure(filepath, timeout=600):
        with open(converted, "wb") as fp:
            fp.write(b"converted")
        return str(converted)

    ctx = _make_context()
    with patch.object(telegram_io, "cfg", lambda key: 600 if key in ("TELEGRAM_UPLOAD_TIMEOUT", "VIDEO_CONVERT_TIMEOUT") else 10), \
         patch.object(telegram_io, "async_ensure_telegram_video", fake_ensure):
        await telegram_io.send_downloaded_media(
            context=ctx,
            chat_id=1,
            files=[str(f)],
            original_msg_id=10,
            upload_kwargs={},
        )

    kwargs = ctx.bot.send_video.await_args.kwargs
    assert kwargs["video"] == str(converted)


@pytest.mark.asyncio
async def test_video_webm_falls_back_to_original_when_convert_fails(tmp_path):
    f = tmp_path / "clip.webm"
    f.write_bytes(b"x")

    async def fake_ensure(filepath, timeout=600):
        return None

    ctx = _make_context()
    with patch.object(telegram_io, "cfg", lambda key: 600 if key in ("TELEGRAM_UPLOAD_TIMEOUT", "VIDEO_CONVERT_TIMEOUT") else 10), \
         patch.object(telegram_io, "async_ensure_telegram_video", fake_ensure):
        await telegram_io.send_downloaded_media(
            context=ctx,
            chat_id=1,
            files=[str(f)],
            original_msg_id=10,
            upload_kwargs={},
        )

    kwargs = ctx.bot.send_video.await_args.kwargs
    assert kwargs["video"] == str(f)


@pytest.mark.asyncio
async def test_video_mp4_skips_conversion(tmp_path):
    f = tmp_path / "clip.mp4"
    f.write_bytes(b"x")
    called = {"count": 0}

    async def fake_ensure(filepath, timeout=600):
        called["count"] += 1
        return filepath

    ctx = _make_context()
    with patch.object(telegram_io, "cfg", lambda key: 600 if key in ("TELEGRAM_UPLOAD_TIMEOUT", "VIDEO_CONVERT_TIMEOUT") else 10), \
         patch.object(telegram_io, "async_ensure_telegram_video", fake_ensure):
        await telegram_io.send_downloaded_media(
            context=ctx,
            chat_id=1,
            files=[str(f)],
            original_msg_id=10,
            upload_kwargs={},
        )

    assert called["count"] == 0
    kwargs = ctx.bot.send_video.await_args.kwargs
    assert kwargs["video"] == str(f)


@pytest.mark.asyncio
async def test_media_group_converts_webm_video(tmp_path):
    img = tmp_path / "a.jpg"
    vid = tmp_path / "b.webm"
    img.write_bytes(b"x")
    vid.write_bytes(b"y")
    converted = tmp_path / "b.tg.mp4"

    async def fake_ensure(filepath, timeout=600):
        with open(converted, "wb") as fp:
            fp.write(b"converted")
        return str(converted)

    ctx = _make_context()

    def fake_cfg(key):
        return {
            "TELEGRAM_UPLOAD_TIMEOUT": 600,
            "VIDEO_CONVERT_TIMEOUT": 600,
            "MEDIA_GROUP_CHUNK_SIZE": 10,
            "MEDIA_GROUP_DELAY": 0,
        }[key]

    with patch.object(telegram_io, "cfg", fake_cfg), \
         patch.object(telegram_io, "async_ensure_telegram_video", fake_ensure):
        await telegram_io.send_downloaded_media(
            context=ctx,
            chat_id=1,
            files=[str(img), str(vid)],
            original_msg_id=10,
            upload_kwargs={},
        )

    kwargs = ctx.bot.send_media_group.await_args.kwargs
    media = kwargs["media"]
    assert len(media) == 2
    assert media[1].media == converted.absolute().as_uri()


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
