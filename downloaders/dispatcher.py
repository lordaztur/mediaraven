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
from utils import safe_url

from messages import lmsg, msg

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
    _resolve_facebook_share_url,
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

from .fallback import fetch_article_caption, scrape_fallback
from .instagram import download_instagram_instagrapi
from .instagram_embed import download_instagram_embed
from .reddit_json import download_reddit_json
from .reddit_playwright import download_reddit_playwright
from .threads import download_threads
from .x import download_x

logger = logging.getLogger(__name__)


__all__ = [
    "download_media",
    "Platform",
    "_detect_platform",
    "_normalize_youtube_url",
    "_resolve_facebook_share_url",
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
) -> Optional[tuple[list[str], str, str, bool]]:
    if platform.instagram:
        ig_files, ig_status, ig_cap = await download_instagram_instagrapi(url, unique_folder)
        if ig_files:
            return await _finalize_success(ig_files, ig_status, ig_cap, url)

    if platform.reddit:
        reddit_pw_files, reddit_pw_status, reddit_pw_cap = await download_reddit_playwright(url, unique_folder)
        if reddit_pw_files:
            return await _finalize_success(reddit_pw_files, reddit_pw_status, reddit_pw_cap, url)

    scrape_files, scrape_status, scrape_caption, scrape_is_article = await scrape_fallback(url, unique_folder)
    if scrape_files:
        return scrape_files, scrape_status, scrape_caption, scrape_is_article

    return None


def _platform_label(platform: Platform) -> str:
    for name in ('youtube', 'instagram', 'threads', 'reddit', 'facebook', 'x'):
        if getattr(platform, name):
            return name
    return 'other'


def _caption_is_weak(caption: str) -> bool:
    if not caption or not caption.strip():
        return True
    link_prefix = msg("caption.link_prefix")
    stripped = caption.strip()
    return stripped.startswith(link_prefix) and stripped.count('<a ') <= 1


async def _enrich_caption_with_article(url: str, caption: str) -> tuple[str, bool]:
    if not _caption_is_weak(caption):
        return caption, False
    article_caption = await fetch_article_caption(url)
    if article_caption:
        return article_caption, True
    return caption, False


async def _finalize_success(
    files: list,
    status: str,
    caption: str,
    url: str,
    platform_label: Optional[str] = None,
    started: Optional[float] = None,
) -> tuple[list, str, str, bool]:
    caption, is_article = await _enrich_caption_with_article(url, caption)
    if platform_label is not None and started is not None:
        metrics.record_success(platform_label, time.monotonic() - started)
    return files, status, caption, is_article


async def download_media(
    url: str,
    unique_folder: str,
    target_lang: Optional[str] = None,
    detect_languages: bool = True,
) -> tuple[list, str, str, bool]:
    started = time.monotonic()
    platform_label = 'other'
    try:
        if not os.path.exists(unique_folder):
            os.makedirs(unique_folder)

        url = await _resolve_short_reddit_url(url)
        url = await _resolve_facebook_share_url(url)
        platform = _detect_platform(url)
        platform_label = _platform_label(platform)

        if platform.youtube:
            url = _normalize_youtube_url(url)

        if platform.threads:
            logger.info(lmsg("dispatcher.link_do_threads"))
            files, status_info, threads_cap = await download_threads(url, unique_folder)
            if files:
                return await _finalize_success(files, status_info, threads_cap, url, platform_label, started)
            if threads_cap:
                metrics.record_success(platform_label, time.monotonic() - started)
                return [], status_info, threads_cap, False
            metrics.record_failure(platform_label, time.monotonic() - started)
            return [], msg("downloader_status.threads_fail"), "", False

        if platform.x:
            logger.info(lmsg("dispatcher.link_do_x"))
            files, status_info, x_caption = await download_x(url, unique_folder)
            if files:
                return await _finalize_success(files, status_info, x_caption, url, platform_label, started)
            if x_caption:
                metrics.record_success(platform_label, time.monotonic() - started)
                return [], status_info, x_caption, False
            metrics.record_failure(platform_label, time.monotonic() - started)
            return [], msg("downloader_status.x_fail"), "", False

        if platform.instagram:
            embed_files, embed_status, embed_cap = await download_instagram_embed(url, unique_folder)
            if embed_files:
                return await _finalize_success(embed_files, embed_status, embed_cap, url, platform_label, started)

        if platform.reddit:
            rj_files, rj_status, rj_cap = await download_reddit_json(url, unique_folder)
            if rj_files:
                return await _finalize_success(rj_files, rj_status, rj_cap, url, platform_label, started)

        has_firefox_cookie = os.path.exists(os.path.join(FIREFOX_PROFILE_PATH, 'cookies.sqlite'))
        if platform.youtube and not state.DENO_PATH:
            logger.warning(lmsg("dispatcher.aten_o_deno_n_o"))
        elif platform.youtube and state.DENO_PATH:
            logger.info(lmsg("dispatcher.deno_js_engine", arg0=state.DENO_PATH))

        base_opts = _build_ytdlp_base_opts(unique_folder)
        _apply_format_selection(base_opts, platform, target_lang)

        if platform.youtube and not target_lang and detect_languages:
            lang_buttons = await _detect_youtube_languages(base_opts, url, has_firefox_cookie)
            if lang_buttons:
                metrics.record_multilang(platform_label)
                return lang_buttons, "MULTILANG", "", False

        downloaded_files, info_dict = await _run_ytdlp_with_cookie_fallback(
            base_opts, url, unique_folder, has_firefox_cookie, target_lang
        )

        caption, _ = _build_caption(info_dict, url)

        if downloaded_files:
            return await _finalize_success(
                downloaded_files, msg("downloader_status.ytdlp_success"),
                caption, url, platform_label, started,
            )

        logger.warning(lmsg("dispatcher.falha_no_yt", arg0=safe_url(url)))
        _wipe_folder(unique_folder)

        fallback_result = await _run_platform_fallbacks(url, unique_folder, platform)
        if fallback_result:
            metrics.record_success(platform_label, time.monotonic() - started)
            return fallback_result

        metrics.record_failure(platform_label, time.monotonic() - started)
        return [], msg("downloader_status.generic_fail"), "", False
    except Exception:
        metrics.record_failure(platform_label, time.monotonic() - started)
        raise
