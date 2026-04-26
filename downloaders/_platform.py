import logging
from dataclasses import dataclass
from urllib.parse import urlparse

import state
from config import AIOHTTP_UA_DEFAULT
from utils import safe_url
from messages import lmsg

logger = logging.getLogger(__name__)


@dataclass
class Platform:
    threads: bool = False
    instagram: bool = False
    youtube: bool = False
    reddit: bool = False
    facebook: bool = False
    x: bool = False


_PLATFORM_HOSTS = {
    'threads': ('threads.net', 'threads.com'),
    'instagram': ('instagram.com',),
    'youtube': ('youtube.com', 'youtu.be', 'm.youtube.com', 'music.youtube.com'),
    'reddit': ('reddit.com', 'redd.it', 'old.reddit.com', 'new.reddit.com'),
    'facebook': ('facebook.com', 'fb.com', 'fb.watch', 'm.facebook.com'),
    'x': ('x.com', 'twitter.com', 'mobile.twitter.com', 'fxtwitter.com', 'vxtwitter.com', 'fixupx.com'),
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
        facebook=_host_matches(host, _PLATFORM_HOSTS['facebook']),
        x=_host_matches(host, _PLATFORM_HOSTS['x']),
    )


async def _resolve_short_reddit_url(url: str) -> str:
    if not _detect_platform(url).reddit or "/s/" not in url:
        return url
    try:
        logger.info(lmsg("_platform.resolvendo_link_encurtado", arg0=safe_url(url)))
        headers = {'User-Agent': AIOHTTP_UA_DEFAULT}
        async with state.AIOHTTP_SESSION.get(url, headers=headers, allow_redirects=True, timeout=15) as resp:
            new_url = str(resp.url)
        if new_url != url:
            logger.info(lmsg("_platform.link_resolvido_x", arg0=safe_url(new_url)))
        return new_url
    except Exception as e:
        logger.warning(lmsg("_platform.falha_ao_resolver", e=e))
        return url


async def _resolve_facebook_share_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.netloc or '').lower()
    if host.startswith('www.'):
        host = host[4:]
    if not (host == 'facebook.com' or host.endswith('.facebook.com')):
        return url
    if '/share/' not in parsed.path:
        return url
    try:
        logger.info(lmsg("_platform.resolvendo_share_url", arg0=safe_url(url)))
        headers = {'User-Agent': AIOHTTP_UA_DEFAULT}
        async with state.AIOHTTP_SESSION.get(url, headers=headers, allow_redirects=True, timeout=15) as resp:
            new_url = str(resp.url)
        if new_url != url:
            logger.info(lmsg("_platform.link_resolvido_x_2", arg0=safe_url(new_url)))
        return new_url
    except Exception as e:
        logger.warning(lmsg("_platform.falha_ao_resolver_2", e=e))
        return url


def _normalize_youtube_url(url: str) -> str:
    url = url.split("?si=")[0].split("&si=")[0]

    if "/shorts/" in url:
        try:
            video_id = url.split("/shorts/")[1].split("?")[0]
            url = f"https://www.youtube.com/watch?v={video_id}"
            logger.info(lmsg("_platform.convertendo_short_para", arg0=safe_url(url)))
        except Exception as e:
            logger.debug(lmsg("_platform.falha_ao_converter", e=e))
    return url
