"""Testes de integração do download_media: protegem a assinatura e o fluxo de fallbacks.

Mocka yt-dlp e cada fallback para garantir que o orquestrador:
  - Tenta fallbacks quando yt-dlp retorna vazio
  - Passa os parâmetros corretos
  - Gera tupla (files, status, caption, is_article) consistente
  - Trata MULTILANG corretamente
"""
import os
from unittest.mock import AsyncMock, patch

import pytest

from downloaders import dispatcher


@pytest.fixture(autouse=True)
def stub_article_enrichment():
    with patch.object(
        dispatcher, "fetch_article_caption",
        new=AsyncMock(return_value=""),
    ):
        yield


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
        files, status, caption, is_article = await dispatcher.download_media(
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
                      new=AsyncMock(return_value=([scraped_file], "STATUS_SCRAPE", "", False))):
        files, status, caption, is_article = await dispatcher.download_media(
            "https://example.com/page", tmp_folder, target_lang=None
        )

    assert files == [scraped_file]
    assert status == "STATUS_SCRAPE"
    assert caption == ""


@pytest.mark.asyncio
async def test_download_media_scraper_returns_article_caption(tmp_folder):
    scraped_file = os.path.join(tmp_folder, "article_cover.jpg")
    article_body = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 6

    with patch.object(dispatcher, "_run_ytdlp_with_cookie_fallback",
                      new=AsyncMock(return_value=([], {}))), \
         patch.object(dispatcher, "_resolve_short_reddit_url", new=_passthrough_async_mock()), \
         patch.object(dispatcher, "scrape_fallback",
                      new=AsyncMock(return_value=([scraped_file], "STATUS_SCRAPE", article_body, True))):
        files, status, caption, is_article = await dispatcher.download_media(
            "https://news.example.com/article/123", tmp_folder, target_lang=None
        )

    assert files == [scraped_file]
    assert status == "STATUS_SCRAPE"
    assert caption == article_body
    assert is_article is True


@pytest.mark.asyncio
async def test_download_media_reddit_tries_json_first(tmp_folder):
    """Reddit: deve tentar reddit_json antes de reddit_playwright e scrape_fallback."""
    reddit_json_file = os.path.join(tmp_folder, "rj.jpg")
    call_order = []

    async def reddit_json_mock(url, folder):
        call_order.append("json")
        return [reddit_json_file], "OK_JSON", "OK_CAP"

    async def reddit_pw_mock(url, folder):
        call_order.append("pw")
        return [], "fail", ""

    async def ytdlp_mock(*a, **kw):
        call_order.append("ytdlp")
        return [], {}

    async def scrape_mock(url, folder):
        call_order.append("scrape")
        return [], "fail", "", False

    with patch.object(dispatcher, "_run_ytdlp_with_cookie_fallback", new=AsyncMock(side_effect=ytdlp_mock)), \
         patch.object(dispatcher, "_resolve_short_reddit_url", new=_passthrough_async_mock()), \
         patch.object(dispatcher, "download_reddit_json", new=AsyncMock(side_effect=reddit_json_mock)), \
         patch.object(dispatcher, "download_reddit_playwright", new=AsyncMock(side_effect=reddit_pw_mock)), \
         patch.object(dispatcher, "scrape_fallback", new=AsyncMock(side_effect=scrape_mock)):
        files, status, caption, is_article = await dispatcher.download_media(
            "https://reddit.com/r/foo/comments/x/", tmp_folder, target_lang=None
        )

    assert files == [reddit_json_file]
    assert status == "OK_JSON"
    assert call_order == ["json"]
    assert "ytdlp" not in call_order


@pytest.mark.asyncio
async def test_download_media_reddit_video_falls_back_to_ytdlp(tmp_folder):
    """Reddit: se reddit_json retorna vazio (vídeo), yt-dlp deve ser tentado."""
    video_file = os.path.join(tmp_folder, "v.mp4")
    with open(video_file, "wb") as f:
        f.write(b"x")
    call_order = []

    async def reddit_json_mock(url, folder):
        call_order.append("json")
        return [], "fail", ""

    async def ytdlp_mock(*a, **kw):
        call_order.append("ytdlp")
        return [video_file], {"title": "vídeo legal", "description": "selftext aqui"}

    with patch.object(dispatcher, "_run_ytdlp_with_cookie_fallback", new=AsyncMock(side_effect=ytdlp_mock)), \
         patch.object(dispatcher, "_resolve_short_reddit_url", new=_passthrough_async_mock()), \
         patch.object(dispatcher, "download_reddit_json", new=AsyncMock(side_effect=reddit_json_mock)):
        files, status, caption, is_article = await dispatcher.download_media(
            "https://reddit.com/r/foo/comments/y/", tmp_folder, target_lang=None
        )

    assert files == [video_file]
    assert call_order == ["json", "ytdlp"]
    assert "vídeo legal" in caption


@pytest.mark.asyncio
async def test_download_media_threads_goes_straight_to_playwright(tmp_folder):
    """Threads pula yt-dlp e vai direto para o Playwright."""
    pw_file = os.path.join(tmp_folder, "threads.mp4")
    ytdlp_mock = AsyncMock(return_value=([], {}))

    with patch.object(dispatcher, "_run_ytdlp_with_cookie_fallback", new=ytdlp_mock), \
         patch.object(dispatcher, "_resolve_short_reddit_url", new=_passthrough_async_mock()), \
         patch.object(dispatcher, "download_threads",
                      new=AsyncMock(return_value=([pw_file], "OK_THREADS", ""))):
        files, status, caption, is_article = await dispatcher.download_media(
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
        files, status, caption, is_article = await dispatcher.download_media(
            "https://youtube.com/watch?v=abc", tmp_folder, target_lang=None
        )

    assert status == "MULTILANG"
    assert files == lang_buttons


@pytest.mark.asyncio
async def test_download_media_returns_generic_fail_when_all_fail(tmp_folder):
    """yt-dlp e scrape vazios -> retorna status semântico generic_fail (handler usa generic_fail msg)."""
    with patch.object(dispatcher, "_run_ytdlp_with_cookie_fallback",
                      new=AsyncMock(return_value=([], {'title': 'Só texto', 'description': 'conteúdo'}))), \
         patch.object(dispatcher, "_resolve_short_reddit_url", new=_passthrough_async_mock()), \
         patch.object(dispatcher, "scrape_fallback",
                      new=AsyncMock(return_value=([], "fail", "", False))):
        files, status, caption, is_article = await dispatcher.download_media(
            "https://example.com/post", tmp_folder, target_lang=None
        )

    assert files == []
    assert status
    assert caption == ""


@pytest.mark.asyncio
async def test_threads_enriches_caption_from_article(tmp_folder):
    pw_file = os.path.join(tmp_folder, "threads.mp4")
    article_caption = "📄 <b>Título</b>\n\nCorpo do artigo\n\n🔗 link"

    with patch.object(dispatcher, "_resolve_short_reddit_url", new=_passthrough_async_mock()), \
         patch.object(dispatcher, "download_threads",
                      new=AsyncMock(return_value=([pw_file], "OK_THREADS", ""))), \
         patch.object(dispatcher, "fetch_article_caption",
                      new=AsyncMock(return_value=article_caption)):
        files, status, caption, is_article = await dispatcher.download_media(
            "https://threads.net/@user/post/1", tmp_folder, target_lang=None
        )

    assert files == [pw_file]
    assert caption == article_caption
    assert is_article is True


@pytest.mark.asyncio
async def test_x_keeps_caption_when_already_present(tmp_folder):
    x_file = os.path.join(tmp_folder, "x.mp4")
    tweet_caption = "📄 <b>Tweet legal</b>\n\nTexto do tweet aqui\n\n🔗 link"
    article_mock = AsyncMock(return_value="ARTIGO_NAO_DEVERIA_SER_USADO")

    with patch.object(dispatcher, "_resolve_short_reddit_url", new=_passthrough_async_mock()), \
         patch.object(dispatcher, "download_x",
                      new=AsyncMock(return_value=([x_file], "OK_X", tweet_caption))), \
         patch.object(dispatcher, "fetch_article_caption", new=article_mock):
        files, status, caption, is_article = await dispatcher.download_media(
            "https://x.com/u/status/1", tmp_folder, target_lang=None
        )

    assert caption == tweet_caption
    assert is_article is False
    article_mock.assert_not_called()


def test_caption_is_weak_detects_empty_and_link_only():
    from downloaders.dispatcher import _caption_is_weak
    assert _caption_is_weak("") is True
    assert _caption_is_weak("   ") is True
    assert _caption_is_weak("🔗 <a href='https://x.com/'>Link Original</a>") is True
    assert _caption_is_weak("📄 <b>T</b>\n\nDesc\n\n🔗 <a>L</a>") is False
    assert _caption_is_weak("Just text content") is False


@pytest.mark.asyncio
async def test_x_text_only_returns_caption_without_files(tmp_folder):
    text_caption = "📄 <b>@user</b>\n\nTexto puro do tweet\n\n🔗 link"

    with patch.object(dispatcher, "_resolve_short_reddit_url", new=_passthrough_async_mock()), \
         patch.object(dispatcher, "download_x",
                      new=AsyncMock(return_value=([], "X_TEXT_ONLY", text_caption))):
        files, status, caption, is_article = await dispatcher.download_media(
            "https://x.com/u/status/1", tmp_folder, target_lang=None
        )

    assert files == []
    assert caption == text_caption
    assert status == "X_TEXT_ONLY"


@pytest.mark.asyncio
async def test_threads_text_only_returns_caption_without_files(tmp_folder):
    text_caption = "📄 <b>@user</b>\n\nThread só com texto\n\n🔗 link"

    with patch.object(dispatcher, "_resolve_short_reddit_url", new=_passthrough_async_mock()), \
         patch.object(dispatcher, "download_threads",
                      new=AsyncMock(return_value=([], "THREADS_TEXT_ONLY", text_caption))):
        files, status, caption, is_article = await dispatcher.download_media(
            "https://threads.net/@u/post/X", tmp_folder, target_lang=None
        )

    assert files == []
    assert caption == text_caption
    assert status == "THREADS_TEXT_ONLY"
