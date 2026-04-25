import logging
import os
import re
from urllib.parse import urlparse

import state
from config import PW_GOTO_TIMEOUT_MS
from messages import msg
from utils import async_download_file, safe_url

from .reddit_common import build_reddit_caption, clean_reddit_media_url, is_reddit_media_url, looks_like_image

logger = logging.getLogger(__name__)


_REDDIT_HOSTS_TO_SWAP = ('reddit.com', 'www.reddit.com', 'new.reddit.com', 'np.reddit.com')


def _force_old_reddit(url: str) -> str:
    try:
        parsed = urlparse(url)
    except Exception:
        return url
    host = (parsed.netloc or '').lower()
    if host in _REDDIT_HOSTS_TO_SWAP:
        return url.replace(parsed.netloc, 'old.reddit.com', 1)
    return url


async def download_reddit_playwright(url: str, unique_folder: str) -> tuple[list[str], str, str]:
    logger.info(f"👽 Iniciando extração via Playwright para Reddit: {safe_url(url)}")
    if not os.path.exists(unique_folder):
        os.makedirs(unique_folder)

    downloaded_files = []
    media_urls = []
    og_title = ""

    if not state.PW_BROWSER:
        return [], msg("downloader_status.playwright_not_running"), ""

    if not state.PW_CONTEXT:
        return [], msg("downloader_status.playwright_not_running"), ""

    target_url = _force_old_reddit(url)
    if target_url != url:
        logger.info(f"👽 Forçando old.reddit.com: {safe_url(target_url)}")

    async with state.PW_SEMAPHORE:
        page = await state.PW_CONTEXT.new_page()

        try:
            await page.goto(target_url, wait_until="domcontentloaded", timeout=PW_GOTO_TIMEOUT_MS)
            await page.wait_for_timeout(3000)

            try:
                nsfw_button = page.get_by_role("button", name=re.compile("Yes", re.IGNORECASE))
                if await nsfw_button.count() > 0:
                    await nsfw_button.first.click(timeout=2000)
                    await page.wait_for_timeout(1500)
            except Exception as e:
                logger.debug(f"Botão NSFW não encontrado/clicável: {e}")

            try:
                unblur_buttons = page.locator('button', has_text=re.compile(r'(View spoiler|View NSFW content|Click to see)', re.IGNORECASE))
                if await unblur_buttons.count() > 0:
                    for i in range(await unblur_buttons.count()):
                        try:
                            await unblur_buttons.nth(i).click(timeout=1500)
                        except Exception as e:
                            logger.debug(f"Falha ao clicar unblur #{i}: {e}")
                    await page.wait_for_timeout(1000)

                shadow_buttons = page.locator('shreddit-blurred-container button')
                if await shadow_buttons.count() > 0:
                    for i in range(await shadow_buttons.count()):
                        try:
                            await shadow_buttons.nth(i).click(timeout=1500)
                        except Exception as e:
                            logger.debug(f"Falha ao clicar shadow unblur #{i}: {e}")
                    await page.wait_for_timeout(1000)
            except Exception as e:
                logger.warning(f"⚠️ Erro ao tentar remover blur do Reddit: {e}")

            main_post = page.locator('shreddit-post').first
            if await main_post.count() > 0:
                logger.info("👽 Post principal detectado. Buscando mídias na Shadow Tree...")
                images = await main_post.locator('img').all()
                for img in images:
                    src = await img.get_attribute('src')
                    if src and is_reddit_media_url(src):
                        clean_url = clean_reddit_media_url(src)
                        if clean_url and clean_url not in media_urls:
                            media_urls.append(clean_url)

                links = await main_post.locator('a').all()
                for a in links:
                    href = await a.get_attribute('href')
                    if href and is_reddit_media_url(href) and looks_like_image(href):
                        clean_url = clean_reddit_media_url(href)
                        if clean_url and clean_url not in media_urls:
                            media_urls.append(clean_url)

            if not media_urls:
                og_image = await page.locator('meta[property="og:image"]').get_attribute('content')
                if og_image and 'redd.it' in og_image:
                    clean_og = clean_reddit_media_url(og_image)
                    if clean_og and clean_og not in media_urls:
                        media_urls.append(clean_og)

            try:
                og_title_attr = await page.locator('meta[property="og:title"]').get_attribute('content', timeout=500)
                if og_title_attr:
                    og_title = og_title_attr.strip()
            except Exception as e:
                logger.debug(f"Meta og:title não encontrada: {e}")

        except Exception as e:
            logger.warning(f"⚠️ Erro no Playwright ao carregar a página: {e}")
        finally:
            await page.close()

    count = 0
    for m_url in media_urls:
        try:
            ext = ".jpg" if not m_url.split('?')[0][-4:].startswith('.') else m_url.split('?')[0][-4:]
            filepath = os.path.join(unique_folder, f"reddit_media_{count}{ext}")

            success = await async_download_file(m_url, filepath)
            if success:
                downloaded_files.append(filepath)
                count += 1
        except Exception as e:
            logger.error(f"⚠️ Erro ao baixar imagem do Reddit: {e}")

    if downloaded_files:
        caption = build_reddit_caption(og_title, "", url)
        return downloaded_files, msg("downloader_status.reddit_playwright"), caption
    return [], msg("downloader_status.reddit_playwright_fail"), ""
