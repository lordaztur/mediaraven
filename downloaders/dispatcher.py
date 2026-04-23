"""Orquestrador de download. Os helpers específicos vivem em submódulos
(_platform, _ytdlp, _languages, _caption) e são re-exportados aqui para que
testes possam patchar via `downloaders.dispatcher.<nome>`.
"""
import logging
import os
import time
from typing import Optional

import metrics
import state
from config import FIREFOX_PROFILE_PATH
from messages import msg
from utils import safe_url

from ._caption import _build_caption
from ._languages import (
    _build_lang_buttons,
    _detect_youtube_languages,
    _parse_lang_from_format,
)
from ._platform import (
    Platform,
    _detect_platform,
    _normalize_youtube_url,
    _resolve_short_reddit_url,
)
from ._ytdlp import (
    _apply_format_selection,
    _attempt_order,
    _build_ytdlp_base_opts,
    _list_downloaded_files,
    _run_ytdlp_with_cookie_fallback,
    _wipe_folder,
    _yt_dlp_extract,
)

from .fallback import scrape_fallback
from .instagram import download_instagram_instagrapi
from .reddit_json import download_reddit_json
from .reddit_playwright import download_reddit_playwright
from .threads import download_threads_playwright

logger = logging.getLogger(__name__)


__all__ = [
    "download_media",
    "Platform",
    "_detect_platform",
    "_normalize_youtube_url",
    "_resolve_short_reddit_url",
    "_apply_format_selection",
    "_attempt_order",
    "_build_ytdlp_base_opts",
    "_list_downloaded_files",
    "_run_ytdlp_with_cookie_fallback",
    "_wipe_folder",
    "_yt_dlp_extract",
    "_build_caption",
    "_build_lang_buttons",
    "_detect_youtube_languages",
    "_parse_lang_from_format",
]


async def _run_platform_fallbacks(
    url: str,
    unique_folder: str,
    platform: Platform,
) -> Optional[tuple[list[str], str, str]]:
    if platform.instagram:
        ig_files, ig_status, ig_cap = await download_instagram_instagrapi(url, unique_folder)
        if ig_files:
            return ig_files, ig_status, ig_cap

    if platform.reddit:
        reddit_files, reddit_status = await download_reddit_json(url, unique_folder)
        if reddit_files:
            return reddit_files, reddit_status, ""

        reddit_pw_files, reddit_pw_status = await download_reddit_playwright(url, unique_folder)
        if reddit_pw_files:
            return reddit_pw_files, reddit_pw_status, ""

    scrape_files, scrape_status = await scrape_fallback(url, unique_folder)
    if scrape_files:
        return scrape_files, scrape_status, ""

    return None


def _platform_label(platform: Platform) -> str:
    for name in ('youtube', 'instagram', 'threads', 'reddit'):
        if getattr(platform, name):
            return name
    return 'other'


async def download_media(
    url: str,
    unique_folder: str,
    target_lang: Optional[str] = None,
    detect_languages: bool = True,
) -> tuple[list, str, str]:
    """Para MULTILANG, `files` no retorno é list[tuple[code, label]].

    Se `detect_languages=False`, a detecção de múltiplas trilhas de áudio do
    YouTube é pulada e o yt-dlp baixa direto com a seleção de formato padrão.
    """
    started = time.monotonic()
    platform_label = 'other'
    try:
        if not os.path.exists(unique_folder):
            os.makedirs(unique_folder)

        url = await _resolve_short_reddit_url(url)
        platform = _detect_platform(url)
        platform_label = _platform_label(platform)

        if platform.youtube:
            url = _normalize_youtube_url(url)

        if platform.threads:
            logger.info("🧵 Link do Threads detectado, redirecionando direto para Playwright.")
            files, status_info = await download_threads_playwright(url, unique_folder)
            if files:
                metrics.record_success(platform_label, time.monotonic() - started)
                return files, status_info, ""
            metrics.record_failure(platform_label, time.monotonic() - started)
            return [], msg("downloader_status.threads_fail"), ""

        has_firefox_cookie = os.path.exists(os.path.join(FIREFOX_PROFILE_PATH, 'cookies.sqlite'))
        if platform.youtube and not state.DENO_PATH:
            logger.warning("⚠️ Atenção: Deno não encontrado! Downloads do YouTube podem falhar por JS Challenges.")
        elif platform.youtube and state.DENO_PATH:
            logger.info(f"🦕 Deno JS Engine ativado para bypass do YouTube: {state.DENO_PATH}")

        base_opts = _build_ytdlp_base_opts(unique_folder)
        _apply_format_selection(base_opts, platform, target_lang)

        if platform.youtube and not target_lang and detect_languages:
            lang_buttons = await _detect_youtube_languages(base_opts, url, has_firefox_cookie)
            if lang_buttons:
                metrics.record_multilang(platform_label)
                return lang_buttons, "MULTILANG", ""

        downloaded_files, info_dict = await _run_ytdlp_with_cookie_fallback(
            base_opts, url, unique_folder, has_firefox_cookie, target_lang
        )

        caption, text_content = _build_caption(info_dict, url)

        if downloaded_files:
            metrics.record_success(platform_label, time.monotonic() - started)
            return downloaded_files, msg("downloader_status.ytdlp_success"), caption

        logger.warning(f"⚠️ Falha no yt-dlp para {safe_url(url)}. Iniciando Fallbacks.")
        _wipe_folder(unique_folder)

        fallback_result = await _run_platform_fallbacks(url, unique_folder, platform)
        if fallback_result:
            metrics.record_success(platform_label, time.monotonic() - started)
            return fallback_result

        if info_dict.get('title') or info_dict.get('description'):
            logger.info("📄 Só texto encontrado, enviando...")
            metrics.record_failure(platform_label, time.monotonic() - started)
            return [], text_content, ""

        metrics.record_failure(platform_label, time.monotonic() - started)
        return [], msg("downloader_status.generic_fail"), ""
    except Exception:
        metrics.record_failure(platform_label, time.monotonic() - started)
        raise
