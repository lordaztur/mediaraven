import asyncio
import html
import json
import logging
import os
import re
from typing import Any, Optional
from urllib.parse import urlparse

from curl_cffi import requests as curl_requests

import state
from config import PW_GOTO_TIMEOUT_MS
from messages import msg
from utils import async_download_file, normalize_image, safe_url

logger = logging.getLogger(__name__)


_TWEET_ID_RE = re.compile(r"/(?:i/status|status)/(\d+)")
_INITIAL_STATE_RE = re.compile(r"window\.__INITIAL_STATE__=(\{.*?\});window\.", re.DOTALL)
_X_HOST_REPLACE = ("fxtwitter.com", "vxtwitter.com", "twitter.com", "fixupx.com", "mobile.twitter.com")
_TCO_TRAIL_RE = re.compile(r"\s*https?://t\.co/\S+\s*$")
_X_CAPTION_MAX = 1000


def _normalize_x_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    bare = host[4:] if host.startswith("www.") else host
    if bare in _X_HOST_REPLACE:
        return url.replace(parsed.netloc, "x.com", 1)
    return url


def _extract_tweet_id(url: str) -> Optional[str]:
    m = _TWEET_ID_RE.search(url)
    return m.group(1) if m else None


def _media_from_extended_entities(media_list: list) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for m in media_list or []:
        kind = m.get("type")
        if kind == "photo":
            base = m.get("media_url_https")
            if base:
                base = html.unescape(base)
                sep = "&" if "?" in base else "?"
                out.append(("image", f"{base}{sep}name=orig"))
        elif kind in ("video", "animated_gif"):
            variants = ((m.get("video_info") or {}).get("variants")) or []
            mp4s = [v for v in variants if (v.get("content_type") or "").startswith("video/mp4")]
            if not mp4s:
                continue
            best = max(mp4s, key=lambda v: v.get("bitrate") or 0)
            url = best.get("url")
            if url:
                out.append(("video", html.unescape(url)))
    return out


def _tweet_ids(obj: dict) -> list[str]:
    ids: list[str] = []
    for k in ("id_str", "rest_id", "id", "conversation_id_str"):
        v = obj.get(k)
        if v is not None:
            ids.append(str(v))
    legacy = obj.get("legacy")
    if isinstance(legacy, dict):
        for k in ("id_str", "conversation_id_str"):
            v = legacy.get(k)
            if v is not None:
                ids.append(str(v))
    return ids


def _walk_for_tweet_media(obj, tweet_id: str):
    if isinstance(obj, dict):
        ext = obj.get("extended_entities")
        if isinstance(ext, dict):
            media = ext.get("media")
            if isinstance(media, list) and media:
                ids = _tweet_ids(obj)
                if not ids or tweet_id in ids:
                    yield media
        for v in obj.values():
            yield from _walk_for_tweet_media(v, tweet_id)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_for_tweet_media(v, tweet_id)


def _walk_for_tweet_obj(obj, tweet_id: str):
    if isinstance(obj, dict):
        if tweet_id in _tweet_ids(obj):
            yield obj
        legacy = obj.get("legacy")
        if isinstance(legacy, dict) and tweet_id in _tweet_ids(legacy):
            yield legacy
        for v in obj.values():
            yield from _walk_for_tweet_obj(v, tweet_id)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_for_tweet_obj(v, tweet_id)


def _find_in_initial_state(data: dict, tweet_id: str) -> Optional[dict]:
    tweets = ((data.get("entities") or {}).get("tweets") or {}).get("entities") or {}
    return tweets.get(tweet_id)


def _extract_tweet_text(tweet: Optional[dict]) -> str:
    if not isinstance(tweet, dict):
        return ""
    legacy = tweet.get("legacy")
    src = legacy if isinstance(legacy, dict) and (legacy.get("full_text") or legacy.get("text")) else tweet
    text = src.get("full_text") or src.get("text") or ""
    if not text:
        return ""
    drange = src.get("display_text_range")
    if isinstance(drange, list) and len(drange) == 2:
        try:
            text = text[drange[0]:drange[1]]
        except Exception as e:
            logger.debug(f"display_text_range slice falhou: {e}")
    text = _TCO_TRAIL_RE.sub("", text).strip()
    text = html.unescape(text)
    return text


def _build_caption(tweet: Optional[dict], url: str) -> str:
    text = _extract_tweet_text(tweet)
    link_label = msg("caption.link_original_label")
    link_prefix = msg("caption.link_prefix")
    link_html = f"{link_prefix}<a href='{html.escape(url, quote=True)}'>{link_label}</a>"
    if not text:
        return link_html
    if len(text) > _X_CAPTION_MAX:
        text = text[:_X_CAPTION_MAX].rstrip() + "..."
    return f"{html.escape(text)}\n\n{link_html}"


async def _fetch_guest_html(url: str) -> Optional[str]:
    loop = asyncio.get_running_loop()
    try:
        r = await loop.run_in_executor(
            state.IO_POOL,
            lambda: curl_requests.get(url, impersonate="chrome", timeout=15, allow_redirects=True),
        )
    except Exception as e:
        logger.warning(f"⚠️ curl_cffi falhou pro X (guest): {e}")
        return None
    if r.status_code != 200:
        logger.debug(f"X guest HTTP {r.status_code} pra {safe_url(url)}")
        return None
    return r.text


def _parse_initial_state(html_text: str) -> Optional[dict]:
    m = _INITIAL_STATE_RE.search(html_text)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def _extract_from_data(data: dict, tweet_id: str) -> tuple[list[tuple[str, str]], Optional[dict]]:
    tweet = _find_in_initial_state(data, tweet_id)
    if not tweet:
        for t in _walk_for_tweet_obj(data, tweet_id):
            tweet = t
            break
    media_items: list[tuple[str, str]] = []
    if tweet:
        media_list = (tweet.get("extended_entities") or {}).get("media") or []
        media_items = _media_from_extended_entities(media_list)
    if not media_items:
        for media in _walk_for_tweet_media(data, tweet_id):
            media_items = _media_from_extended_entities(media)
            if media_items:
                break
    return media_items, tweet


async def _try_guest(url: str, tweet_id: str) -> tuple[list[tuple[str, str]], Optional[dict]]:
    html_text = await _fetch_guest_html(url)
    if not html_text:
        return [], None
    data = _parse_initial_state(html_text)
    if not data:
        return [], None
    return _extract_from_data(data, tweet_id)


async def _try_authenticated(url: str, tweet_id: str) -> tuple[list[tuple[str, str]], Optional[dict]]:
    if not state.PW_BROWSER or not state.PW_CONTEXT:
        return [], None
    captured: list[Any] = []

    async with state.PW_SEMAPHORE:
        page = await state.PW_CONTEXT.new_page()

        async def on_response(resp):
            try:
                if "/i/api/graphql/" not in resp.url:
                    return
                data = await resp.json()
                captured.append(data)
            except Exception as e:
                logger.debug(f"X graphql parse falhou: {e}")

        page.on("response", on_response)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=PW_GOTO_TIMEOUT_MS)
            await page.wait_for_timeout(3500)
            content = await page.content()
        except Exception as e:
            logger.warning(f"⚠️ Playwright erro carregando {safe_url(url)}: {e}")
            content = ""
        finally:
            await page.close()

    tweet_obj: Optional[dict] = None
    for data in captured:
        items, tweet = _extract_from_data(data, tweet_id)
        if tweet and not tweet_obj:
            tweet_obj = tweet
        if items:
            return items, tweet_obj or tweet

    if content:
        data = _parse_initial_state(content)
        if data:
            items, tweet = _extract_from_data(data, tweet_id)
            if tweet and not tweet_obj:
                tweet_obj = tweet
            if items:
                return items, tweet_obj or tweet

    return [], tweet_obj


async def download_x(url: str, unique_folder: str) -> tuple[list[str], str, str]:
    logger.info(f"🐦 Iniciando extração para X: {safe_url(url)}")

    if not os.path.exists(unique_folder):
        os.makedirs(unique_folder)

    url = _normalize_x_url(url)
    tweet_id = _extract_tweet_id(url)
    if not tweet_id:
        logger.warning(f"⚠️ Não consegui extrair tweet ID: {safe_url(url)}")
        return [], msg("downloader_status.x_fail"), ""

    media_items, tweet_obj = await _try_guest(url, tweet_id)
    if not media_items:
        logger.info(f"🔒 Tweet {tweet_id}: guest vazio, tentando Playwright autenticado")
        auth_items, auth_tweet = await _try_authenticated(url, tweet_id)
        media_items = auth_items
        if auth_tweet:
            tweet_obj = auth_tweet

    if not media_items:
        logger.warning(f"⚠️ Nenhuma mídia encontrada no tweet {tweet_id}")
        return [], msg("downloader_status.x_fail"), ""

    downloaded: list[str] = []
    for idx, (kind, m_url) in enumerate(media_items):
        ext = ".mp4" if kind == "video" else ".jpg"
        filepath = os.path.join(unique_folder, f"x_{idx}{ext}")
        try:
            ok = await async_download_file(m_url, filepath)
        except Exception as e:
            logger.error(f"⚠️ Erro ao baixar mídia do X: {e}")
            continue
        if not ok:
            continue
        if kind == "image":
            normalized = normalize_image(filepath, min_size=100)
            if normalized is None:
                continue
            downloaded.append(normalized)
        else:
            downloaded.append(filepath)

    if not downloaded:
        logger.warning(
            f"⚠️ Tweet {tweet_id}: {len(media_items)} URLs encontradas mas downloads falharam"
        )
        return [], msg("downloader_status.x_fail"), ""

    has_video = any(f.endswith(".mp4") for f in downloaded)
    label = msg("media_type_labels.x_video") if has_video else msg("media_type_labels.x_album")
    caption = _build_caption(tweet_obj, url)
    return downloaded, msg("downloader_status.x", media_type=label, count=len(downloaded)), caption
