import logging
import os

import state
from config import PW_GOTO_TIMEOUT_MS, THREADS_JUNK_KEYWORDS, THREADS_MIN_IMAGE_SIZE
from messages import msg
from utils import async_download_file, normalize_image, safe_url

logger = logging.getLogger(__name__)


async def download_threads_playwright(url: str, unique_folder: str) -> tuple[list[str], str]:
    logger.info(f"🧵 Iniciando extração via Playwright para Threads: {safe_url(url)}")

    if not os.path.exists(unique_folder):
        os.makedirs(unique_folder)

    downloaded_files = []
    media_urls = []

    if not state.PW_BROWSER:
        return [], msg("downloader_status.playwright_not_running")

    if not state.PW_CONTEXT:
        return [], msg("downloader_status.playwright_not_running")

    async with state.PW_SEMAPHORE:
        page = await state.PW_CONTEXT.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=PW_GOTO_TIMEOUT_MS)
            await page.wait_for_timeout(3000)

            og_video = None
            og_image = None
            try:
                og_video = await page.locator('meta[property="og:video"]').get_attribute('content')
                if og_video:
                    media_urls.append(og_video)
                    logger.info("🎯 Vídeo principal encontrado na Meta Tag (og:video).")
            except Exception as e:
                logger.debug(f"Meta og:video não encontrada: {e}")
            try:
                og_image = await page.locator('meta[property="og:image"]').get_attribute('content')
            except Exception as e:
                logger.debug(f"Meta og:image não encontrada: {e}")

            try:
                videos = await page.locator('video').all()
                first_video_y = None

                for v in videos:
                    box = await v.bounding_box()
                    if not box: continue

                    if first_video_y is None:
                        first_video_y = box['y']

                    if box['y'] > first_video_y + 200:
                        continue

                    src = await v.get_attribute('src')
                    if src and src.startswith('http') and src not in media_urls:
                        media_urls.append(src)

                video_urls_found = [m for m in media_urls if '.mp4' in m.lower() or 'video' in m.lower()]

                if len(video_urls_found) == 0:
                    images = await page.locator('img').all()
                    junk_keywords = THREADS_JUNK_KEYWORDS

                    first_img_y = None

                    for img in images:
                        src = await img.get_attribute('src')
                        if not src or not ('fbcdn.net' in src or 'cdninstagram.com' in src): continue
                        if any(k in src.lower() for k in junk_keywords): continue

                        box = await img.bounding_box()
                        if not box: continue

                        if first_img_y is None:
                            first_img_y = box['y']

                        if box['y'] > first_img_y + 200:
                            continue

                        if src not in media_urls:
                            media_urls.append(src)

                    if len(media_urls) == 0 and og_image:
                        media_urls.append(og_image)
                        logger.info("🎯 Imagem principal encontrada na Meta Tag (og:image).")

            except Exception as e:
                 logger.warning(f"⚠️ Aviso na extração do DOM: {e}")

        except Exception as e:
            logger.warning(f"⚠️ Erro no Playwright ao carregar a página: {e}")
        finally:
            await page.close()

    clean_urls = list(dict.fromkeys(media_urls))

    video_urls = [m for m in clean_urls if '.mp4' in m.lower() or 'video' in m.lower()]
    if video_urls:
        clean_urls = video_urls
        logger.info(f"🎥 Vídeos isolados. Ignorando imagens acessórias.")

    count = 0
    for m_url in clean_urls:
        try:
            base_url = m_url.split('?')[0]

            if '.mp4' in base_url.lower() or 'video' in m_url.lower():
                ext = ".mp4"
            else:
                ext = ".jpg" if not base_url[-4:].startswith('.') else base_url[-4:]

            filepath = os.path.join(unique_folder, f"threads_media_{count}{ext}")

            success = await async_download_file(m_url, filepath)

            if success:
                if ext != ".mp4":
                    normalized = normalize_image(filepath, min_size=THREADS_MIN_IMAGE_SIZE)
                    if normalized is None:
                        continue
                    downloaded_files.append(normalized)
                    count += 1
                else:
                    downloaded_files.append(filepath)
                    count += 1

        except Exception as e:
            logger.error(f"⚠️ Erro ao baixar mídia do Threads: {e}")

    if downloaded_files:
        has_video = any(f.endswith('.mp4') for f in downloaded_files)
        media_type = msg("media_type_labels.threads_video") if has_video else msg("media_type_labels.threads_album")
        return downloaded_files, msg("downloader_status.threads_playwright", media_type=media_type)

    return [], msg("downloader_status.threads_playwright_fail")
