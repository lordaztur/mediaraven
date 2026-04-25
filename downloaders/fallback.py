import logging
import os
from urllib.parse import urlparse

import state
from config import PW_GOTO_TIMEOUT_MS
from messages import msg
from utils import async_download_file, normalize_image, safe_url

logger = logging.getLogger(__name__)


_FACEBOOK_HOSTS = ('facebook.com', 'fb.com', 'fb.watch')


def _is_facebook(url: str) -> bool:
    try:
        host = (urlparse(url).netloc or '').lower()
    except Exception:
        return False
    if host.startswith('www.'):
        host = host[4:]
    return any(host == h or host.endswith('.' + h) for h in _FACEBOOK_HOSTS)


async def scrape_fallback(url: str, unique_folder: str) -> tuple[list[str], str]:
    logger.info(f"🕸️ Iniciando Scraping Deep Search (Network) para: {safe_url(url)}")

    if not os.path.exists(unique_folder):
        os.makedirs(unique_folder)

    downloaded_files = []
    media_urls = set()

    if not state.PW_BROWSER or not state.PW_CONTEXT:
        return [], msg("downloader_status.playwright_not_running")

    async with state.PW_SEMAPHORE:
        page = None
        try:
            page = await state.PW_CONTEXT.new_page()

            async def handle_response(response):
                try:
                    resource_type = response.request.resource_type
                    if resource_type in ['image', 'media']:
                        req_url = response.url
                        if req_url.startswith('http'):
                            media_urls.add(req_url)
                except Exception as e:
                    logger.debug(f"handle_response: {e}")

            page.on("response", handle_response)

            await page.goto(url, wait_until="load", timeout=PW_GOTO_TIMEOUT_MS)

            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(3000)

            meta_properties = ['og:video', 'og:video:secure_url', 'og:image', 'og:image:secure_url', 'twitter:image']
            for prop in meta_properties:
                try:
                    content = await page.locator(f'meta[property="{prop}"]').get_attribute('content', timeout=500)
                    if content: media_urls.add(content)
                except Exception:
                    try:
                        content = await page.locator(f'meta[name="{prop}"]').get_attribute('content', timeout=500)
                        if content: media_urls.add(content)
                    except Exception as e:
                        logger.debug(f"Meta '{prop}' não encontrada: {e}")

            try:
                for vid in await page.locator('video').all():
                    src = await vid.get_attribute('src')
                    if src and src.startswith('http'): media_urls.add(src)
                    for source in await vid.locator('source').all():
                        src_attr = await source.get_attribute('src')
                        if src_attr and src_attr.startswith('http'): media_urls.add(src_attr)
            except Exception as e:
                logger.debug(f"Busca por <video> falhou: {e}")

            try:
                for img in await page.locator('img').all():
                    src = await img.get_attribute('src')
                    if src and src.startswith('http'): media_urls.add(src)
            except Exception as e:
                logger.debug(f"Busca por <img> falhou: {e}")

        except Exception as e:
            logger.error(f"❌ Erro Scraper Playwright ao carregar a página: {e}")
        finally:
            if page is not None:
                await page.close()

    logger.info(f"🔎 Encontradas {len(media_urls)} URLs de mídia brutas.")

    count = 0
    processed_hashes = set()

    for media_url in media_urls:
        try:
            url_base = media_url.split('?')[0]
            if url_base in processed_hashes: continue

            is_video = '.mp4' in media_url.lower() or 'video' in media_url.lower()
            if is_video:
                ext = ".mp4"
            else:
                ext = ".jpg" if not url_base[-4:].startswith('.') else url_base[-4:]

            filename = f"scrape_media_{count}{ext}"
            filepath = os.path.join(unique_folder, filename)

            success = await async_download_file(media_url, filepath)

            if success:
                if ext != ".mp4":
                    normalized = normalize_image(filepath, min_size=50)
                    if normalized is None:
                        continue
                    filepath = normalized
                processed_hashes.add(url_base)
                downloaded_files.append(filepath)
                count += 1

        except Exception as e:
            logger.error(f"⚠️ Erro ao baixar item via Scraper: {e}")

    if downloaded_files:
        has_video = any(f.endswith('.mp4') for f in downloaded_files)
        if _is_facebook(url) and not has_video:
            logger.warning(
                f"⚠️ Scraper achou {len(downloaded_files)} mídias para link do Facebook, "
                "mas nenhuma é vídeo — provavelmente lixo de UI. Descartando."
            )
            return [], msg("downloader_status.scraper_fail")

        media_type = msg("media_type_labels.scraper_video_mixed") if has_video else msg("media_type_labels.scraper_images")
        return downloaded_files, msg("downloader_status.scraper", media_type=media_type, count=len(downloaded_files))

    return [], msg("downloader_status.scraper_fail")
