import html
import re
from typing import Optional
from urllib.parse import urlparse

from ._caption import _build_caption


_REDDIT_MEDIA_HOSTS = ('i.redd.it', 'preview.redd.it')
_REDDIT_JUNK_MARKERS = ('award_images', 'snoovatar', 'avatars', 'icon')
_IMG_EXT_RE = re.compile(r'\.(jpg|jpeg|png|webp|gif)($|\?)', re.IGNORECASE)
_REDDIT_NATIVE_HOSTS = ('reddit.com', 'redd.it', 'i.redd.it', 'v.redd.it', 'preview.redd.it')


def build_reddit_caption(title: str, selftext: str, url: str) -> tuple[str, str]:
    info = {"title": title or "", "description": selftext or ""}
    return _build_caption(info, url)


def clean_reddit_media_url(raw_url: str) -> str | None:
    if not raw_url:
        return None
    cleaned = html.unescape(raw_url).split('?')[0]
    return cleaned.replace('preview.redd.it', 'i.redd.it')


def is_reddit_media_url(url: str) -> bool:
    if not url:
        return False
    if not any(host in url for host in _REDDIT_MEDIA_HOSTS):
        return False
    lowered = url.lower()
    if any(marker in lowered for marker in _REDDIT_JUNK_MARKERS):
        return False
    return True


def looks_like_image(url: str) -> bool:
    return bool(_IMG_EXT_RE.search(url or ''))


def reddit_external_link(post_data: dict) -> Optional[dict]:
    """Se o post for um link externo (notícia/YouTube/etc.), retorna
    {external_url, title, thumbnail_url}. Retorna None quando o post é mídia
    nativa do Reddit (imagem/galeria/vídeo) ou texto — nesses casos o fluxo
    normal cuida."""
    if not isinstance(post_data, dict):
        return None
    if post_data.get('is_self'):
        return None
    if post_data.get('is_video') or post_data.get('post_hint') in ('hosted:video', 'rich:video'):
        return None
    if 'media_metadata' in post_data:
        return None

    dest = post_data.get('url_overridden_by_dest') or post_data.get('url') or ''
    if not dest:
        return None

    domain = (post_data.get('domain') or '').lower()
    if domain.startswith('self.'):
        return None

    host = (urlparse(dest).netloc or '').lower()
    if host.startswith('www.'):
        host = host[4:]
    if any(host == h or host.endswith('.' + h) for h in _REDDIT_NATIVE_HOSTS):
        return None
    if looks_like_image(dest):
        return None

    thumbnail_url = None
    images = (post_data.get('preview') or {}).get('images') or []
    if images:
        raw = (images[0].get('source') or {}).get('url') or ''
        thumbnail_url = html.unescape(raw) or None

    return {
        'external_url': dest,
        'title': post_data.get('title') or '',
        'thumbnail_url': thumbnail_url,
    }
