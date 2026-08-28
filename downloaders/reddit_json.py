import logging
import os

import aiohttp

import state
from config import cfg
from cookies import get_aiohttp_cookies_for_url
from messages import lmsg, msg
from utils import async_download_file, normalize_image, safe_url

from .reddit_common import build_reddit_caption, clean_reddit_media_url, looks_like_image, reddit_external_link

logger = logging.getLogger(__name__)

_REDDIT_GUEST_BOOTSTRAP_URL = "https://old.reddit.com/"
_reddit_session_ready = False


def _reddit_json_headers() -> dict:
    return {
        'User-Agent': cfg("REDDIT_JSON_UA"),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
    }


async def _ensure_reddit_session(force: bool = False) -> None:
    global _reddit_session_ready
    if _reddit_session_ready and not force:
        return
    try:
        async with state.AIOHTTP_SESSION.get(
            _REDDIT_GUEST_BOOTSTRAP_URL, headers=_reddit_json_headers(),
            allow_redirects=True, timeout=15,
        ) as resp:
            await resp.read()
        _reddit_session_ready = True
        logger.info(lmsg("reddit_json.sessao_anonima_ok"))
    except Exception as e:
        logger.debug(lmsg("reddit_json.sessao_anonima_falhou", e=e))


async def _fetch_reddit_post_data(url: str) -> dict:
    await _ensure_reddit_session()
    cookies_dict = dict(get_aiohttp_cookies_for_url(url) or {})
    cookies_dict.setdefault('over18', '1')
    if cookies_dict:
        logger.info(lmsg("reddit_json.usando_x_cookies", arg0=len(cookies_dict)))
    clean_url = url.split('?')[0].rstrip('/')
    json_url = f"{clean_url}.json?raw_json=1"

    async def _get() -> dict:
        async with state.AIOHTTP_SESSION.get(json_url, headers=_reddit_json_headers(), cookies=cookies_dict, timeout=15) as resp:
            resp.raise_for_status()
            data = await resp.json()
        return data[0]['data']['children'][0]['data']

    try:
        return await _get()
    except aiohttp.ClientResponseError as e:
        if e.status in (403, 429):
            await _ensure_reddit_session(force=True)
            return await _get()
        raise


async def resolve_reddit_external_link(url: str) -> tuple["dict | None", "dict | None"]:
    """Retorna (link, post_data). `link` é o dict do link externo (ou None se o
    post for mídia nativa/texto); `post_data` é reaproveitado por
    download_reddit_json pra não buscar o JSON duas vezes."""
    try:
        post_data = await _fetch_reddit_post_data(url)
    except Exception as e:
        logger.debug(lmsg("reddit_json.erro_ao_ler", e=e))
        return None, None
    return reddit_external_link(post_data), post_data


async def download_reddit_json(
    url: str, unique_folder: str, post_data: "dict | None" = None,
) -> tuple[list[str], str, str, str]:
    logger.info(lmsg("reddit_json.iniciando_extra_o_via", arg0=safe_url(url)))
    if not os.path.exists(unique_folder):
        os.makedirs(unique_folder)

    media_urls = []
    downloaded_files = []
    title = ""
    selftext = ""

    try:
        if post_data is None:
            post_data = await _fetch_reddit_post_data(url)
        title = post_data.get('title', '') or ''
        selftext = post_data.get('selftext', '') or ''

        media_src = post_data
        crosspost_parents = post_data.get('crosspost_parent_list') or []
        if crosspost_parents:
            media_src = crosspost_parents[-1]
            logger.info(lmsg("reddit_json.crosspost_detectado"))
            if not selftext:
                selftext = media_src.get('selftext', '') or ''

        if media_src.get('is_video') or media_src.get('post_hint') in ('hosted:video', 'rich:video'):
            logger.info(lmsg("reddit_json.post_v_deo"))
            return [], msg("downloader_status.reddit_json_fail"), "", ""

        if 'media_metadata' in media_src:
            gallery_items = media_src.get('gallery_data', {}).get('items', [])
            if gallery_items:
                for item in gallery_items:
                    media_id = item['media_id']
                    media_info = media_src['media_metadata'].get(media_id, {})
                    if media_info.get('status') == 'valid':
                        img_url = media_info.get('s', {}).get('u') or media_info.get('s', {}).get('gif')
                        clean_u = clean_reddit_media_url(img_url)
                        if clean_u and clean_u not in media_urls: media_urls.append(clean_u)
            else:
                for media_id, media_info in media_src['media_metadata'].items():
                    if media_info.get('status') == 'valid':
                        img_url = media_info.get('s', {}).get('u') or media_info.get('s', {}).get('gif')
                        clean_u = clean_reddit_media_url(img_url)
                        if clean_u and clean_u not in media_urls: media_urls.append(clean_u)

        elif 'url' in media_src and looks_like_image(media_src['url']):
            clean_u = clean_reddit_media_url(media_src['url'])
            if clean_u and clean_u not in media_urls: media_urls.append(clean_u)

        elif 'preview' in media_src and 'images' in media_src['preview']:
            img_url = media_src['preview']['images'][0]['source']['url']
            clean_u = clean_reddit_media_url(img_url)
            if clean_u and clean_u not in media_urls: media_urls.append(clean_u)

    except Exception as e:
        logger.error(lmsg("reddit_json.erro_ao_ler", e=e), exc_info=True)

    count = 0
    for m_url in media_urls:
        try:
            ext = ".jpg" if not m_url[-4:].startswith('.') else m_url[-4:]
            filepath = os.path.join(unique_folder, f"reddit_media_{count}{ext}")

            success = await async_download_file(m_url, filepath)

            if success:
                if not filepath.lower().endswith(('.mp4', '.gif', '.webm')):
                    normalized = normalize_image(filepath, min_size=1)
                    if normalized is None:
                        continue
                    filepath = normalized

                downloaded_files.append(filepath)
                count += 1
        except Exception as e:
            logger.error(lmsg("reddit_json.erro_ao_processar", e=e))

    if downloaded_files:
        caption_short, caption_full = build_reddit_caption(title, selftext, url)
        return downloaded_files, msg("downloader_status.reddit_json"), caption_short, caption_full
    return [], msg("downloader_status.reddit_json_fail"), "", ""
