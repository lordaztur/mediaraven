"""Testes de integração do download_media: protegem a assinatura e o fluxo de fallbacks.

Mocka yt-dlp e cada fallback para garantir que o orquestrador:
  - Tenta fallbacks quando yt-dlp retorna vazio
  - Passa os parâmetros corretos
  - Gera tupla (files, status, caption) consistente
  - Trata MULTILANG corretamente
"""
import os
from unittest.mock import AsyncMock, patch

import pytest

from downloaders import dispatcher


@pytest.fixture
def tmp_folder(tmp_path):
    folder = tmp_path / "task"
    folder.mkdir()
    return str(folder)


def _passthrough_async_mock():
    """AsyncMock que devolve o primeiro argumento recebido (para _resolve_short_reddit_url)."""
    async def passthrough(url):
        return url
    return AsyncMock(side_effect=passthrough)


@pytest.mark.asyncio
async def test_download_media_ytdlp_success(tmp_folder):
    """yt-dlp baixa arquivo -> retorna (files, status_success, caption)."""
    fake_file = os.path.join(tmp_folder, "video.mp4")
    with open(fake_file, "wb") as f:
        f.write(b"x")

    with patch.object(dispatcher, "_run_ytdlp_with_cookie_fallback",
                      new=AsyncMock(return_value=([fake_file], {'title': 'Teste', 'description': 'desc'}))), \
         patch.object(dispatcher, "_resolve_short_reddit_url", new=_passthrough_async_mock()), \
         patch.object(dispatcher, "_detect_youtube_languages", new=AsyncMock(return_value=None)):
        files, status, caption = await dispatcher.download_media(
            "https://example.com/video", tmp_folder, target_lang=None
        )

    assert files == [fake_file]
    assert "Teste" in caption
    assert status


@pytest.mark.asyncio
async def test_download_media_falls_back_to_scraper(tmp_folder):
    """yt-dlp vazio -> cai no scrape_fallback e retorna o resultado dele."""
    scraped_file = os.path.join(tmp_folder, "scraped.jpg")

    with patch.object(dispatcher, "_run_ytdlp_with_cookie_fallback",
                      new=AsyncMock(return_value=([], {}))), \
         patch.object(dispatcher, "_resolve_short_reddit_url", new=_passthrough_async_mock()), \
         patch.object(dispatcher, "scrape_fallback",
                      new=AsyncMock(return_value=([scraped_file], "STATUS_SCRAPE"))):
        files, status, caption = await dispatcher.download_media(
            "https://example.com/page", tmp_folder, target_lang=None
        )

    assert files == [scraped_file]
    assert status == "STATUS_SCRAPE"
    assert caption == ""


@pytest.mark.asyncio
async def test_download_media_reddit_tries_json_first(tmp_folder):
    """Reddit: deve tentar reddit_json antes de reddit_playwright e scrape_fallback."""
    reddit_json_file = os.path.join(tmp_folder, "rj.jpg")
    call_order = []

    async def reddit_json_mock(url, folder):
        call_order.append("json")
        return [reddit_json_file], "OK_JSON"

    async def reddit_pw_mock(url, folder):
        call_order.append("pw")
        return [], "fail"

    async def scrape_mock(url, folder):
        call_order.append("scrape")
        return [], "fail"

    with patch.object(dispatcher, "_run_ytdlp_with_cookie_fallback",
                      new=AsyncMock(return_value=([], {}))), \
         patch.object(dispatcher, "_resolve_short_reddit_url", new=_passthrough_async_mock()), \
         patch.object(dispatcher, "download_reddit_json", new=AsyncMock(side_effect=reddit_json_mock)), \
         patch.object(dispatcher, "download_reddit_playwright", new=AsyncMock(side_effect=reddit_pw_mock)), \
         patch.object(dispatcher, "scrape_fallback", new=AsyncMock(side_effect=scrape_mock)):
        files, status, caption = await dispatcher.download_media(
            "https://reddit.com/r/foo/comments/x/", tmp_folder, target_lang=None
        )

    assert files == [reddit_json_file]
    assert status == "OK_JSON"
    assert call_order == ["json"]


@pytest.mark.asyncio
async def test_download_media_threads_goes_straight_to_playwright(tmp_folder):
    """Threads pula yt-dlp e vai direto para o Playwright."""
    pw_file = os.path.join(tmp_folder, "threads.mp4")
    ytdlp_mock = AsyncMock(return_value=([], {}))

    with patch.object(dispatcher, "_run_ytdlp_with_cookie_fallback", new=ytdlp_mock), \
         patch.object(dispatcher, "_resolve_short_reddit_url", new=_passthrough_async_mock()), \
         patch.object(dispatcher, "download_threads",
                      new=AsyncMock(return_value=([pw_file], "OK_THREADS"))):
        files, status, caption = await dispatcher.download_media(
            "https://threads.net/@user/post/1", tmp_folder, target_lang=None
        )

    assert ytdlp_mock.await_count == 0
    assert files == [pw_file]
    assert status == "OK_THREADS"


@pytest.mark.asyncio
async def test_download_media_multilang(tmp_folder):
    """YouTube com múltiplos idiomas deve sinalizar MULTILANG em vez de baixar."""
    lang_buttons = [('original', 'ORIGINAL [EN]'), ('pt', 'PT')]

    with patch.object(dispatcher, "_resolve_short_reddit_url", new=_passthrough_async_mock()), \
         patch.object(dispatcher, "_detect_youtube_languages", new=AsyncMock(return_value=lang_buttons)):
        files, status, caption = await dispatcher.download_media(
            "https://youtube.com/watch?v=abc", tmp_folder, target_lang=None
        )

    assert status == "MULTILANG"
    assert files == lang_buttons


@pytest.mark.asyncio
async def test_download_media_returns_text_when_nothing_downloaded_but_has_info(tmp_folder):
    """Se yt-dlp e fallbacks falharem mas houver título/descrição, devolve texto."""
    with patch.object(dispatcher, "_run_ytdlp_with_cookie_fallback",
                      new=AsyncMock(return_value=([], {'title': 'Só texto', 'description': 'conteúdo'}))), \
         patch.object(dispatcher, "_resolve_short_reddit_url", new=_passthrough_async_mock()), \
         patch.object(dispatcher, "scrape_fallback",
                      new=AsyncMock(return_value=([], "fail"))):
        files, status, caption = await dispatcher.download_media(
            "https://example.com/post", tmp_folder, target_lang=None
        )

    assert files == []
    assert "Só texto" in status
    assert caption == ""
