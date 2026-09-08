import logging
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

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
    tiktok: bool = False


_PLATFORM_HOSTS = {
    'threads': ('threads.net', 'threads.com'),
    'instagram': ('instagram.com',),
    'youtube': ('youtube.com', 'youtu.be', 'm.youtube.com', 'music.youtube.com'),
    'reddit': ('reddit.com', 'redd.it', 'old.reddit.com', 'new.reddit.com'),
    'facebook': ('facebook.com', 'fb.com', 'fb.watch', 'm.facebook.com'),
    'x': ('x.com', 'twitter.com', 'mobile.twitter.com', 'fxtwitter.com', 'vxtwitter.com', 'fixupx.com'),
    'tiktok': ('tiktok.com', 'vt.tiktok.com', 'vm.tiktok.com'),
}


def _host_matches(host: str, suffixes: tuple[str, ...]) -> bool:
    return any(host == s or host.endswith('.' + s) for s in suffixes)


def _bare_host(url: str) -> str:
    """netloc em minúsculas, sem 'www.'. String vazia se a URL for inválida."""
    try:
        host = (urlparse(url).netloc or '').lower()
    except Exception:
        return ''
    return host[4:] if host.startswith('www.') else host


async def _resolve_redirect(url: str, fail_key: str) -> str:
    """GET seguindo redirects; devolve a URL final (ou a original, em erro)."""
    try:
        async with state.AIOHTTP_SESSION.get(
            url, headers={'User-Agent': AIOHTTP_UA_DEFAULT},
            allow_redirects=True, timeout=15,
        ) as resp:
            return str(resp.url)
    except Exception as e:
        logger.warning(lmsg(fail_key, e=e))
        return url


def _detect_platform(url: str) -> Platform:
    host = _bare_host(url)
    return Platform(
        threads=_host_matches(host, _PLATFORM_HOSTS['threads']),
        instagram=_host_matches(host, _PLATFORM_HOSTS['instagram']),
        youtube=_host_matches(host, _PLATFORM_HOSTS['youtube']),
        reddit=_host_matches(host, _PLATFORM_HOSTS['reddit']),
        facebook=_host_matches(host, _PLATFORM_HOSTS['facebook']),
        x=_host_matches(host, _PLATFORM_HOSTS['x']),
        tiktok=_host_matches(host, _PLATFORM_HOSTS['tiktok']),
    )


async def _resolve_short_reddit_url(url: str) -> str:
    if not _detect_platform(url).reddit or "/s/" not in url:
        return url
    logger.info(lmsg("_platform.resolvendo_link_encurtado", arg0=safe_url(url)))
    new_url = await _resolve_redirect(url, "_platform.falha_ao_resolver")
    if new_url != url:
        logger.info(lmsg("_platform.link_resolvido_x", arg0=safe_url(new_url)))
    return new_url


_KWAI_HOSTS = (
    'kwai-video.com', 'kwai.com', 'm.kwai.com',
    'kw.ai', 's.kw.ai',
    'snackvideo.com', 'snackvideo.in',
)


def _is_kwai_host(host: str) -> bool:
    if host.startswith('www.'):
        host = host[4:]
    return _host_matches(host, _KWAI_HOSTS)


async def _resolve_kwai_url(url: str) -> str:
    if not _is_kwai_host(_bare_host(url)):
        return url
    logger.info(lmsg("_platform.resolvendo_kwai", arg0=safe_url(url)))
    new_url = await _resolve_redirect(url, "_platform.falha_ao_resolver_kwai")
    cleaned = urlunparse(urlparse(new_url)._replace(query="", fragment=""))
    if cleaned != url:
        logger.info(lmsg("_platform.kwai_resolvido", arg0=safe_url(cleaned)))
    return cleaned


async def _resolve_facebook_share_url(url: str) -> str:
    if not _host_matches(_bare_host(url), ('facebook.com',)):
        return url
    if '/share/' not in urlparse(url).path:
        return url
    logger.info(lmsg("_platform.resolvendo_share_url", arg0=safe_url(url)))
    new_url = await _resolve_redirect(url, "_platform.falha_ao_resolver_2")
    if new_url != url:
        logger.info(lmsg("_platform.link_resolvido_x_2", arg0=safe_url(new_url)))
    return new_url


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
