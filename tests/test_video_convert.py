import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import state
import utils


def _fake_proc(returncode: int, stdout: bytes = b"", stderr: bytes = b""):
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.kill = MagicMock()
    proc.wait = AsyncMock()
    return proc


def test_is_telegram_compatible_video_ext():
    assert utils.is_telegram_compatible_video_ext("/x/clip.mp4")
    assert utils.is_telegram_compatible_video_ext("/x/clip.M4V")
    assert utils.is_telegram_compatible_video_ext("/x/clip.MOV")
    assert not utils.is_telegram_compatible_video_ext("/x/clip.webm")
    assert not utils.is_telegram_compatible_video_ext("/x/clip.mkv")
    assert not utils.is_telegram_compatible_video_ext("/x/clip.avi")
    assert not utils.is_telegram_compatible_video_ext("/x/clip.flv")


@pytest.mark.asyncio
async def test_ffprobe_returns_none_when_binary_missing():
    with patch.object(state, "FFPROBE_PATH", None):
        v, a = await utils.async_ffprobe_codecs("/whatever.webm")
    assert v is None and a is None


@pytest.mark.asyncio
async def test_ffprobe_parses_codec_lines():
    stdout = b"codec_name=vp9\ncodec_type=video\ncodec_name=opus\ncodec_type=audio\n"

    async def fake_exec(*args, **kwargs):
        return _fake_proc(0, stdout=stdout)

    with patch.object(state, "FFPROBE_PATH", "/usr/bin/ffprobe"), \
         patch.object(asyncio, "create_subprocess_exec", fake_exec):
        v, a = await utils.async_ffprobe_codecs("/clip.webm")
    assert v == "vp9"
    assert a == "opus"


@pytest.mark.asyncio
async def test_ffprobe_no_audio_stream():
    stdout = b"codec_name=h264\ncodec_type=video\n"

    async def fake_exec(*args, **kwargs):
        return _fake_proc(0, stdout=stdout)

    with patch.object(state, "FFPROBE_PATH", "/usr/bin/ffprobe"), \
         patch.object(asyncio, "create_subprocess_exec", fake_exec):
        v, a = await utils.async_ffprobe_codecs("/clip.mp4")
    assert v == "h264"
    assert a == ""


@pytest.mark.asyncio
async def test_ensure_video_passes_through_compatible_ext():
    out = await utils.async_ensure_telegram_video("/x/clip.mp4")
    assert out == "/x/clip.mp4"
    out = await utils.async_ensure_telegram_video("/x/clip.MOV")
    assert out == "/x/clip.MOV"


@pytest.mark.asyncio
async def test_ensure_video_mp4_h264_aac_passes_through(tmp_path):
    """.mp4 com codec compatível (h264+aac) não deve ser convertido."""
    f = tmp_path / "clip.mp4"
    f.write_bytes(b"x")
    exec_called = {"n": 0}

    async def fake_exec(*args, **kwargs):
        exec_called["n"] += 1
        return _fake_proc(0)

    async def fake_probe(filepath, timeout=30):
        return "h264", "aac"

    with patch.object(state, "FFMPEG_PATH", "/usr/bin/ffmpeg"), \
         patch.object(utils, "async_ffprobe_codecs", fake_probe), \
         patch.object(asyncio, "create_subprocess_exec", fake_exec):
        out = await utils.async_ensure_telegram_video(str(f))

    assert out == str(f)
    assert exec_called["n"] == 0


@pytest.mark.asyncio
async def test_ensure_video_mp4_with_av1_gets_reencoded(tmp_path):
    """.mp4 com codec incompatível (av1) deve ser re-encodado apesar da extensão .mp4."""
    f = tmp_path / "clip.mp4"
    f.write_bytes(b"x")
    out_target = tmp_path / "clip.tg.mp4"
    captured: list = []

    async def fake_exec(*args, **kwargs):
        captured.extend(args)
        out_target.write_bytes(b"out")
        return _fake_proc(0)

    async def fake_probe(filepath, timeout=30):
        return "av1", "aac"

    with patch.object(state, "FFMPEG_PATH", "/usr/bin/ffmpeg"), \
         patch.object(utils, "async_ffprobe_codecs", fake_probe), \
         patch.object(asyncio, "create_subprocess_exec", fake_exec):
        out = await utils.async_ensure_telegram_video(str(f))

    assert out == str(out_target)
    assert "libx264" in captured
    assert "copy" in captured


@pytest.mark.asyncio
async def test_ensure_video_mp4_hevc_gets_reencoded(tmp_path):
    """.mp4 HEVC (TikTok/bytevc1) deve ser re-encodado pra h264."""
    f = tmp_path / "clip.mp4"
    f.write_bytes(b"x")
    out_target = tmp_path / "clip.tg.mp4"
    captured: list = []

    async def fake_exec(*args, **kwargs):
        captured.extend(args)
        out_target.write_bytes(b"out")
        return _fake_proc(0)

    async def fake_probe(filepath, timeout=30):
        return "hevc", "aac"

    with patch.object(state, "FFMPEG_PATH", "/usr/bin/ffmpeg"), \
         patch.object(utils, "async_ffprobe_codecs", fake_probe), \
         patch.object(asyncio, "create_subprocess_exec", fake_exec):
        out = await utils.async_ensure_telegram_video(str(f))

    assert out == str(out_target)
    assert "libx264" in captured


@pytest.mark.asyncio
async def test_merge_audio_image_uses_normal_fps_and_faststart(tmp_path):
    captured: list = []

    async def fake_exec(*args, **kwargs):
        captured.extend(args)
        return _fake_proc(0)

    with patch.object(state, "FFMPEG_PATH", "/usr/bin/ffmpeg"), \
         patch.object(asyncio, "create_subprocess_exec", fake_exec):
        ok = await utils.async_merge_audio_image("/img.jpg", "/aud.m4a", "/out.mp4", duration=10.0)

    assert ok is True
    fps = captured[captured.index("-framerate") + 1]
    assert fps == "15" and int(fps) > 1
    assert captured[captured.index("-r") + 1] == "15"
    assert captured[captured.index("-movflags") + 1] == "+faststart"


@pytest.mark.asyncio
async def test_ensure_video_returns_none_when_ffmpeg_missing(tmp_path):
    f = tmp_path / "clip.webm"
    f.write_bytes(b"x")
    with patch.object(state, "FFMPEG_PATH", None):
        out = await utils.async_ensure_telegram_video(str(f))
    assert out is None


@pytest.mark.asyncio
async def test_ensure_video_remux_when_h264_aac(tmp_path):
    f = tmp_path / "clip.mkv"
    f.write_bytes(b"x")
    out_target = tmp_path / "clip.tg.mp4"

    captured_cmd: list = []

    async def fake_exec(*args, **kwargs):
        captured_cmd.extend(args)
        out_target.write_bytes(b"out")
        return _fake_proc(0)

    async def fake_probe(filepath, timeout=30):
        return "h264", "aac"

    with patch.object(state, "FFMPEG_PATH", "/usr/bin/ffmpeg"), \
         patch.object(utils, "async_ffprobe_codecs", fake_probe), \
         patch.object(asyncio, "create_subprocess_exec", fake_exec):
        out = await utils.async_ensure_telegram_video(str(f))

    assert out == str(out_target)
    assert "-c:v" in captured_cmd
    assert "copy" in captured_cmd
    assert "-c:a" in captured_cmd
    assert "libx264" not in captured_cmd
    assert "aac" not in captured_cmd[captured_cmd.index("-c:a") + 1: captured_cmd.index("-c:a") + 2]


@pytest.mark.asyncio
async def test_ensure_video_reencode_when_vp9_opus(tmp_path):
    f = tmp_path / "clip.webm"
    f.write_bytes(b"x")
    out_target = tmp_path / "clip.tg.mp4"

    captured_cmd: list = []

    async def fake_exec(*args, **kwargs):
        captured_cmd.extend(args)
        out_target.write_bytes(b"out")
        return _fake_proc(0)

    async def fake_probe(filepath, timeout=30):
        return "vp9", "opus"

    with patch.object(state, "FFMPEG_PATH", "/usr/bin/ffmpeg"), \
         patch.object(utils, "async_ffprobe_codecs", fake_probe), \
         patch.object(asyncio, "create_subprocess_exec", fake_exec):
        out = await utils.async_ensure_telegram_video(str(f))

    assert out == str(out_target)
    assert "libx264" in captured_cmd
    assert "aac" in captured_cmd


@pytest.mark.asyncio
async def test_ensure_video_no_audio_uses_an_flag(tmp_path):
    f = tmp_path / "silent.webm"
    f.write_bytes(b"x")
    out_target = tmp_path / "silent.tg.mp4"

    captured_cmd: list = []

    async def fake_exec(*args, **kwargs):
        captured_cmd.extend(args)
        out_target.write_bytes(b"out")
        return _fake_proc(0)

    async def fake_probe(filepath, timeout=30):
        return "vp9", ""

    with patch.object(state, "FFMPEG_PATH", "/usr/bin/ffmpeg"), \
         patch.object(utils, "async_ffprobe_codecs", fake_probe), \
         patch.object(asyncio, "create_subprocess_exec", fake_exec):
        out = await utils.async_ensure_telegram_video(str(f))

    assert out == str(out_target)
    assert "-an" in captured_cmd


@pytest.mark.asyncio
async def test_ensure_video_remux_fails_falls_back_to_reencode(tmp_path):
    f = tmp_path / "clip.mkv"
    f.write_bytes(b"x")
    out_target = tmp_path / "clip.tg.mp4"

    call_count = {"n": 0}
    captured_cmds: list = []

    async def fake_exec(*args, **kwargs):
        call_count["n"] += 1
        captured_cmds.append(list(args))
        if call_count["n"] == 1:
            return _fake_proc(1, stderr=b"codec not compatible")
        out_target.write_bytes(b"out")
        return _fake_proc(0)

    async def fake_probe(filepath, timeout=30):
        return "h264", "aac"

    with patch.object(state, "FFMPEG_PATH", "/usr/bin/ffmpeg"), \
         patch.object(utils, "async_ffprobe_codecs", fake_probe), \
         patch.object(asyncio, "create_subprocess_exec", fake_exec):
        out = await utils.async_ensure_telegram_video(str(f))

    assert out == str(out_target)
    assert call_count["n"] == 2
    second = captured_cmds[1]
    assert "libx264" in second


@pytest.mark.asyncio
async def test_ensure_video_returns_none_when_both_attempts_fail(tmp_path):
    f = tmp_path / "clip.mkv"
    f.write_bytes(b"x")

    async def fake_exec(*args, **kwargs):
        return _fake_proc(1, stderr=b"oops")

    async def fake_probe(filepath, timeout=30):
        return "h264", "aac"

    with patch.object(state, "FFMPEG_PATH", "/usr/bin/ffmpeg"), \
         patch.object(utils, "async_ffprobe_codecs", fake_probe), \
         patch.object(asyncio, "create_subprocess_exec", fake_exec):
        out = await utils.async_ensure_telegram_video(str(f))

    assert out is None
