"""O caminho autenticado do Instagram busca o media/{pk}/info pela API web, com a sessão do
Firefox, e baixa os arquivos direto das URLs do CDN (DOWNLOAD_TIMEOUT_SECONDS por leitura).
O instagrapi saiu na v1.3.0: o login por senha levava 429 desde out/2026."""
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
    monkeypatch.setattr(instagram, "_web_media_info", lambda url, timeout: (media, {}))
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs["timeout"]))
        return _FakeResponse()

    monkeypatch.setattr(instagram.requests, "get", fake_get)

    paths, status, _, full = await instagram.download_instagram_api(
        "https://www.instagram.com/reel/Dc6NTWNhZKu/", str(tmp_path)
    )

    assert [u for u, _ in calls] == [u for u, _ in expected]
    assert all(t == cfg("DOWNLOAD_TIMEOUT_SECONDS") for _, t in calls)
    assert [os.path.splitext(p)[1] for p in paths] == [e for _, e in expected]
    assert all(os.path.getsize(p) > 0 for p in paths)
    assert "legenda de teste" in full
    assert "Web" in status


@pytest.mark.asyncio
async def test_sem_sessao_falha_sem_baixar(tmp_path, monkeypatch):
    monkeypatch.setattr(instagram, "_web_media_info", lambda url, timeout: None)

    paths, status, _, _ = await instagram.download_instagram_api(
        "https://www.instagram.com/p/DeMqyRcBI3X/", str(tmp_path)
    )

    assert paths == []
    assert status


def test_api_web_exige_sessao_do_firefox(monkeypatch):
    monkeypatch.setattr(state, "FIREFOX_COOKIES_CACHE", [{"name": "csrftoken", "value": "x", "domain": ".instagram.com"}])
    called = []
    monkeypatch.setattr(instagram.curl_requests, "get", lambda *a, **k: called.append(a))

    assert instagram._web_media_info("https://www.instagram.com/p/DeMqyRcBI3X/", 10) is None
    assert called == []


@pytest.mark.parametrize("url, pk", [
    ("https://www.instagram.com/p/B1LbfVPlwIA/", "2110901750722920960"),
    ("https://www.instagram.com/reel/B-fKL9qpeab/?igsh=x", "2278584739065882267"),
    ("https://www.instagram.com/p/CCQQsCXjOaBfS3I2PpqsNkxElV9DXj61vzo5xs0/", "2346448800803776129"),
    ("https://www.instagram.com/stories/fulano/3456789012345678901/?utm=1", "3456789012345678901"),
], ids=["post", "reel", "privado", "story"])
def test_media_pk_from_url(url, pk):
    assert instagram._media_pk_from_url(url)[0] == pk


def test_media_from_v1_escolhe_maior_resolucao_e_carrossel():
    item = {
        "media_type": 8,
        "caption": {"text": "oi"},
        "carousel_media": [
            {"media_type": 1, "image_versions2": {"candidates": [
                {"url": "p", "width": 320, "height": 320}, {"url": "g", "width": 1080, "height": 1080}]}},
            {"media_type": 2,
             "video_versions": [{"url": "v_pq", "width": 480, "height": 854}, {"url": "v_gd", "width": 720, "height": 1280}],
             "image_versions2": {"candidates": [{"url": "capa", "width": 720, "height": 1280}]}},
        ],
    }

    m = instagram._media_from_v1(item)

    assert m.media_type == 8 and m.caption_text == "oi"
    assert [(r.media_type, r.thumbnail_url, r.video_url) for r in m.resources] == [(1, "g", None), (2, "capa", "v_gd")]


def test_msg_cai_no_exemplo_quando_messages_json_nao_tem_a_chave(monkeypatch):
    import messages
    monkeypatch.setattr(messages, "_MESSAGES", {"downloader_status": {}})
    assert messages.msg("downloader_status.instagram_web", media_type="X") == "📸 Instagram Web (X)"
    with pytest.raises(KeyError):
        messages.msg("downloader_status.chave_que_nao_existe")
