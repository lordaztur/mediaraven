import asyncio
import logging
from typing import Any, Optional

import state
from config import FIREFOX_PROFILE_PATH
from messages import msg
from utils import safe_url

from ._ytdlp import _yt_dlp_extract

logger = logging.getLogger(__name__)


def _parse_lang_from_format(fmt: dict[str, Any]) -> tuple[Optional[str], bool]:
    acodec = fmt.get('acodec')
    if not acodec or acodec == 'none':
        return None, False

    lang = fmt.get('language')
    fmt_id = str(fmt.get('format_id', ''))

    clean_lang: Optional[str] = None
    if isinstance(lang, str) and len(lang) >= 2:
        clean_lang = lang.split('-')[0].lower()
        if clean_lang == 'und':
            clean_lang = None

    if not clean_lang and '-' in fmt_id:
        parts = fmt_id.split('-')
        if len(parts) >= 2 and len(parts[1]) >= 2:
            possible_lang = parts[1][:2].lower()
            if possible_lang.isalpha() and possible_lang not in ['mp', 'au', 'or']:
                clean_lang = possible_lang

    return clean_lang, clean_lang is None


def _build_lang_buttons(
    langs_found: set[str],
    original_lang: Optional[str],
    has_untagged_audio: bool,
) -> list[tuple[str, str]]:
    if len(langs_found) <= 1:
        return []
    original_label = msg("caption.original_lang_label")
    buttons: list[tuple[str, str]] = []
    for l in sorted(langs_found):
        if l == original_lang:
            buttons.append(('original', f"{original_label} [{l.upper()}]"))
        else:
            buttons.append((l, l.upper()))
    if not original_lang and has_untagged_audio:
        buttons.insert(0, ('original', original_label))
    return buttons


async def _detect_youtube_languages(
    base_opts: dict[str, Any],
    url: str,
    has_firefox_cookie: bool,
) -> Optional[list[tuple[str, str]]]:
    loop = asyncio.get_running_loop()

    extract_attempts: list[str] = []
    if has_firefox_cookie:
        extract_attempts.append("with_cookie")
    extract_attempts.append("no_cookie")

    info: Optional[dict] = None
    for mode in extract_attempts:
        try:
            extract_opts = base_opts.copy()
            extract_opts.pop('format', None)
            if mode == "with_cookie":
                extract_opts['cookiesfrombrowser'] = ('firefox', FIREFOX_PROFILE_PATH, None, None)

            logger.info(f"🔍 Buscando trilhas de idioma ({mode}) para: {safe_url(url)}")
            info = await loop.run_in_executor(state.YTDLP_POOL, _yt_dlp_extract, extract_opts, url, False)
            if info:
                break
        except Exception as e:
            logger.warning(f"⚠️ Falha na extração de idiomas ({mode}): {e}")

    if not info:
        return None

    try:
        formats: list[dict] = []
        if 'formats' in info:
            formats = info['formats']
        elif 'entries' in info and len(info['entries']) > 0:
            valid_entries = [e for e in info['entries'] if e is not None]
            if valid_entries and 'formats' in valid_entries[0]:
                formats = valid_entries[0]['formats']

        if not formats:
            logger.warning("⚠️ O yt-dlp não retornou nenhuma lista de formatos na checagem.")
            return None

        langs_found: set[str] = set()
        original_lang: Optional[str] = None
        has_untagged_audio = False

        for fmt in formats:
            clean_lang, untagged = _parse_lang_from_format(fmt)
            if untagged:
                has_untagged_audio = True
            if clean_lang:
                langs_found.add(clean_lang)
                note = str(fmt.get('format_note', '')).lower()
                fmt_id = str(fmt.get('format_id', ''))
                if 'original' in note or 'default' in note:
                    original_lang = clean_lang
                elif '-' not in fmt_id and fmt_id in ['140', '249', '250', '251']:
                    if not original_lang:
                        original_lang = clean_lang

        if not original_lang:
            main_lang = info.get('language')
            if isinstance(main_lang, str) and len(main_lang) >= 2:
                main_lang = main_lang.split('-')[0].lower()
                if main_lang in langs_found:
                    original_lang = main_lang

        buttons = _build_lang_buttons(langs_found, original_lang, has_untagged_audio)
        if len(buttons) > 1:
            logger.info(f"🌍 Múltiplos idiomas detectados: {buttons}")
            return buttons
        return None
    except Exception as e:
        logger.error(f"⚠️ Erro crítico ao checar idiomas: {e}")
        return None
