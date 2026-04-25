import asyncio
import logging
import os
from typing import Any, Optional

import yt_dlp
from yt_dlp.networking.impersonate import ImpersonateTarget

import state
from config import (
    FIREFOX_PROFILE_PATH,
    YTDLP_MAX_HEIGHT,
    YTDLP_SOCKET_TIMEOUT,
    YTDLP_YT_CLIENTS,
)

from ._platform import Platform

logger = logging.getLogger(__name__)


def _build_ytdlp_base_opts(unique_folder: str) -> dict[str, Any]:
    opts: dict[str, Any] = {
        'outtmpl': os.path.join(unique_folder, '%(title)s [%(id)s].%(ext)s'),
        'restrictfilenames': True,
        'writedescription': False,
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
        'geo_bypass': True,
        'socket_timeout': YTDLP_SOCKET_TIMEOUT,
        'remote_components': ['ejs:github'],
        'extractor_args': {'youtube': [f'player_client={YTDLP_YT_CLIENTS}']},
    }
    if state.DENO_PATH:
        opts['js_runtimes'] = {'deno': {'path': state.DENO_PATH}}
    return opts


def _apply_format_selection(opts: dict[str, Any], platform: Platform, target_lang: Optional[str]) -> None:
    h = YTDLP_MAX_HEIGHT
    if platform.instagram:
        opts['noplaylist'] = False
        opts['format'] = 'best'
    elif platform.reddit:
        opts['noplaylist'] = False
        opts['format'] = 'bestvideo+bestaudio/best'
    elif platform.youtube:
        opts['noplaylist'] = True
        if target_lang and target_lang != 'original':
            opts['format'] = (
                f'best[height<={h}][language^={target_lang}]/'
                f'bestvideo[height<={h}]+bestaudio[language^={target_lang}]/'
                f'bestvideo[height<={h}]+bestaudio/best[height<={h}]/best'
            )
        else:
            opts['format'] = f'bestvideo[height<={h}]+bestaudio/best[height<={h}]/best'
        opts['merge_output_format'] = 'mp4'
    else:
        opts['noplaylist'] = True
        opts['format'] = f'bestvideo[height<={h}]+bestaudio/best[height<={h}]/best'
        opts['merge_output_format'] = 'mp4'

    if platform.facebook or platform.instagram or platform.reddit:
        opts['impersonate'] = ImpersonateTarget('chrome')


def _yt_dlp_extract(opts: dict[str, Any], url: str, download: bool = False) -> Optional[dict]:
    """Copia opts antes de mutar — evita contaminação cruzada entre tentativas."""
    opts = dict(opts)
    if not download:
        opts['extract_flat'] = False
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=download)


def _list_downloaded_files(folder: str) -> list[str]:
    if not os.path.exists(folder):
        return []
    return [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if os.path.isfile(os.path.join(folder, f))
        and not f.endswith(('.part', '.ytdl', '.temp'))
    ]


def _wipe_folder(folder: str) -> None:
    if not os.path.exists(folder):
        return
    for f in os.listdir(folder):
        full_path = os.path.join(folder, f)
        if os.path.isfile(full_path):
            try:
                os.remove(full_path)
            except OSError as e:
                logger.debug(f"Falha ao remover {full_path}: {e}")


def _attempt_order(has_firefox_cookie: bool, target_lang: Optional[str]) -> list[str]:
    attempts: list[str] = []
    if target_lang and target_lang != 'original':
        if has_firefox_cookie:
            attempts.append("with_cookie")
        attempts.append("no_cookie")
    else:
        attempts.append("no_cookie")
        if has_firefox_cookie:
            attempts.append("with_cookie")
    return attempts


async def _run_ytdlp_with_cookie_fallback(
    base_opts: dict[str, Any],
    url: str,
    unique_folder: str,
    has_firefox_cookie: bool,
    target_lang: Optional[str],
) -> tuple[list[str], dict[str, Any]]:
    loop = asyncio.get_running_loop()
    info_dict: dict[str, Any] = {}
    downloaded_files: list[str] = []

    last_exc: Optional[BaseException] = None
    for mode in _attempt_order(has_firefox_cookie, target_lang):
        _wipe_folder(unique_folder)

        current_opts = base_opts.copy()
        if mode == "with_cookie":
            logger.info("🍪 Usando cookies globais do Firefox profile...")
            current_opts['cookiesfrombrowser'] = ('firefox', FIREFOX_PROFILE_PATH, None, None)

        try:
            info = await loop.run_in_executor(
                state.YTDLP_POOL, _yt_dlp_extract, current_opts, url, True
            )

            if info:
                if 'entries' in info and info.get('entries'):
                    valid = [e for e in info['entries'] if e is not None]
                    info_dict = valid[0] if valid else info
                else:
                    info_dict = info
            if info_dict is None:
                info_dict = {}

            current_files = _list_downloaded_files(unique_folder)
            if current_files:
                downloaded_files = sorted(current_files)
                logger.info(f"✅ Download bem-sucedido na tentativa: {mode}")
                break
            logger.warning(f"⚠️ yt-dlp falhou em baixar arquivos na tentativa '{mode}'")
        except Exception as e:
            last_exc = e
            logger.warning(f"⚠️ yt-dlp exceção na tentativa '{mode}': {e}")

    if not downloaded_files and last_exc is not None:
        logger.debug("Stack trace da última exceção yt-dlp:", exc_info=last_exc)

    return downloaded_files, info_dict
