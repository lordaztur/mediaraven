"""O Instagrapi só resolve a mídia (media_info pela API privada); os arquivos saem direto das
URLs do CDN. Não usar photo_download/video_download/album_download do instagrapi:
- photo_download(media_pk) re-busca pelo GraphQL público, que está bloqueado (401);
- video_download/album_download re-buscam o media_info e baixam com o request_timeout do
  instagrapi (1s por padrão). Esse valor também é a pausa antes de cada chamada da API, então
  não dá pra só aumentar — reels caíam com ReadTimeout no CDN."""
import os
from types import SimpleNamespace

import pytest

import state
from config import cfg
from downloaders import instagram


def _res(media_type, url):
    return SimpleNamespace(
        media_type=media_type,
        video_url=url if media_type == 2 else None,
        thumbnail_url=url if media_type == 1 else "https://cdn/capa_do_video.jpg",
    )


def _media(media_type, resources=(), video_url=None, thumbnail_url=None):
    return SimpleNamespace(
        media_type=media_type, resources=list(resources), video_url=video_url,
        thumbnail_url=thumbnail_url, caption_text="legenda de teste",
    )


class _FakeClient:
    def __init__(self, media):
        self.media = media
        self.media_info_calls = 0

    def media_pk_from_url(self, url):
        return "3979551724859134638"

    def media_info(self, pk):
        self.media_info_calls += 1
        return self.media

    def private_request(self, path):
        return {}


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        yield b"bytes"


@pytest.mark.parametrize("media, expected", [
    (_media(1, thumbnail_url="https://cdn/v/photo_full.jpg"),
     [("https://cdn/v/photo_full.jpg", ".jpg")]),
    (_media(2, video_url="https://cdn/o1/v/reel.mp4?oe=abc", thumbnail_url="https://cdn/capa.jpg"),
     [("https://cdn/o1/v/reel.mp4?oe=abc", ".mp4")]),
    (_media(8, resources=[_res(1, "https://cdn/a.jpg"), _res(2, "https://cdn/b.mp4")]),
     [("https://cdn/a.jpg", ".jpg"), ("https://cdn/b.mp4", ".mp4")]),
], ids=["foto", "video", "album"])
@pytest.mark.asyncio
async def test_baixa_urls_do_media_info_direto(tmp_path, monkeypatch, media, expected):
    client = _FakeClient(media)
    monkeypatch.setattr(state, "IG_CLIENT", client)
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs["timeout"]))
        return _FakeResponse()

    monkeypatch.setattr(instagram.requests, "get", fake_get)

    paths, _, _, full = await instagram.download_instagram_instagrapi(
        "https://www.instagram.com/reel/Dc6NTWNhZKu/", str(tmp_path)
    )

    assert [u for u, _ in calls] == [u for u, _ in expected]
    assert all(t == cfg("DOWNLOAD_TIMEOUT_SECONDS") for _, t in calls)
    assert client.media_info_calls == 1
    assert [os.path.splitext(p)[1] for p in paths] == [e for _, e in expected]
    assert all(os.path.getsize(p) > 0 for p in paths)
    assert "legenda de teste" in full
