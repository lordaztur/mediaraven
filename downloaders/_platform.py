import logging
from dataclasses import dataclass
from urllib.parse import urlparse

import state
from config import AIOHTTP_UA_DEFAULT
from utils import safe_url

logger = logging.getLogger(__name__)


@dataclass
class Platform:
    threads: bool = False
    instagram: bool = False
    youtube: bool = False
    reddit: bool = False


_PLATFORM_HOSTS = {
    'threads': ('threads.net', 'threads.com'),
    'instagram': ('instagram.com',),
    'youtube': ('youtube.com', 'youtu.be', 'm.youtube.com', 'music.youtube.com'),
    'reddit': ('reddit.com', 'redd.it', 'old.reddit.com', 'new.reddit.com'),
}


def _host_matches(host: str, suffixes: tuple[str, ...]) -> bool:
    for suffix in suffixes:
        if host == suffix or host.endswith('.' + suffix):
            return True
    return False


def _detect_platform(url: str) -> Platform:
    try:
        host = (urlparse(url).netloc or '').lower()
    except Exception:
        host = ''
    if host.startswith('www.'):
        host = host[4:]
    return Platform(
        threads=_host_matches(host, _PLATFORM_HOSTS['threads']),
        instagram=_host_matches(host, _PLATFORM_HOSTS['instagram']),
        youtube=_host_matches(host, _PLATFORM_HOSTS['youtube']),
        reddit=_host_matches(host, _PLATFORM_HOSTS['reddit']),
    )


async def _resolve_short_reddit_url(url: str) -> str:
    if not _detect_platform(url).reddit or "/s/" not in url:
        return url
    try:
        logger.info(f"🔄 Resolvendo link encurtado: {safe_url(url)}")
        headers = {'User-Agent': AIOHTTP_UA_DEFAULT}
        async with state.AIOHTTP_SESSION.get(url, headers=headers, allow_redirects=True, timeout=15) as resp:
            new_url = str(resp.url)
        if new_url != url:
            logger.info(f"✅ Link resolvido: {safe_url(new_url)}")
        return new_url
    except Exception as e:
        logger.warning(f"⚠️ Falha ao resolver redirect Reddit: {e}")
        return url


def _normalize_youtube_url(url: str) -> str:
    url = url.split("?si=")[0].split("&si=")[0]

    if "/shorts/" in url:
        try:
            video_id = url.split("/shorts/")[1].split("?")[0]
            url = f"https://www.youtube.com/watch?v={video_id}"
            logger.info(f"🔄 Convertendo Short para URL normal: {safe_url(url)}")
        except Exception as e:
            logger.debug(f"Falha ao converter Shorts: {e}")
    return url
