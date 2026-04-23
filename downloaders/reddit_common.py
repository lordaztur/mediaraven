import html
import re


_REDDIT_MEDIA_HOSTS = ('i.redd.it', 'preview.redd.it')
_REDDIT_JUNK_MARKERS = ('award_images', 'snoovatar', 'avatars', 'icon')
_IMG_EXT_RE = re.compile(r'\.(jpg|jpeg|png|webp|gif)($|\?)', re.IGNORECASE)


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
