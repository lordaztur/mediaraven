import logging
import os

import state
from config import cfg
from cookies import get_aiohttp_cookies_for_url
from messages import lmsg, msg
from utils import async_download_file, normalize_image, safe_url

from .reddit_common import build_reddit_caption, clean_reddit_media_url, looks_like_image

logger = logging.getLogger(__name__)


async def download_reddit_json(url: str, unique_folder: str) -> tuple[list[str], str, str]:
    logger.info(lmsg("reddit_json.iniciando_extra_o_via", arg0=safe_url(url)))
    if not os.path.exists(unique_folder):
        os.makedirs(unique_folder)

    media_urls = []
    downloaded_files = []
    title = ""
    selftext = ""

    headers = {
        'User-Agent': cfg("REDDIT_JSON_UA"),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
    }

    cookies_dict = get_aiohttp_cookies_for_url(url)
    if cookies_dict:
         logger.info(lmsg("reddit_json.usando_x_cookies", arg0=len(cookies_dict)))

    try:
        clean_url = url.split('?')[0].rstrip('/')
        json_url = f"{clean_url}.json?raw_json=1"

        async with state.AIOHTTP_SESSION.get(json_url, headers=headers, cookies=cookies_dict, timeout=15) as resp:
            resp.raise_for_status()
            data = await resp.json()

        post_data = data[0]['data']['children'][0]['data']
        title = post_data.get('title', '') or ''
        selftext = post_data.get('selftext', '') or ''

        if post_data.get('is_video') or post_data.get('post_hint') in ('hosted:video', 'rich:video'):
            logger.info(lmsg("reddit_json.post_v_deo"))
            return [], msg("downloader_status.reddit_json_fail"), ""

        if 'media_metadata' in post_data:
            gallery_items = post_data.get('gallery_data', {}).get('items', [])
            if gallery_items:
                for item in gallery_items:
                    media_id = item['media_id']
                    media_info = post_data['media_metadata'].get(media_id, {})
                    if media_info.get('status') == 'valid':
                        img_url = media_info.get('s', {}).get('u') or media_info.get('s', {}).get('gif')
                        clean_u = clean_reddit_media_url(img_url)
                        if clean_u and clean_u not in media_urls: media_urls.append(clean_u)
            else:
                for media_id, media_info in post_data['media_metadata'].items():
                    if media_info.get('status') == 'valid':
                        img_url = media_info.get('s', {}).get('u') or media_info.get('s', {}).get('gif')
                        clean_u = clean_reddit_media_url(img_url)
                        if clean_u and clean_u not in media_urls: media_urls.append(clean_u)

        elif 'url' in post_data and looks_like_image(post_data['url']):
            clean_u = clean_reddit_media_url(post_data['url'])
            if clean_u and clean_u not in media_urls: media_urls.append(clean_u)

        elif 'preview' in post_data and 'images' in post_data['preview']:
            img_url = post_data['preview']['images'][0]['source']['url']
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
        caption = build_reddit_caption(title, selftext, url)
        return downloaded_files, msg("downloader_status.reddit_json"), caption
    return [], msg("downloader_status.reddit_json_fail"), ""
