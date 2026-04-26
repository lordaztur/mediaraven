import asyncio
import logging
import os
from typing import Optional
from urllib.parse import quote, urlparse

from curl_cffi import requests as curl_requests

import state
from config import (
    PW_GOTO_TIMEOUT_MS,
    SCRAPE_ARCHIVE_TIMEOUT_S,
    SCRAPE_ARTICLE_EXTRACT,
    SCRAPE_ARTICLE_MIN_CHARS,
    SCRAPE_FAST_PATH_TIMEOUT_S,
    SCRAPE_GALLERY_DL_ENABLE,
    SCRAPE_GALLERY_DL_TIMEOUT_S,
    SCRAPE_HLS_TIMEOUT_S,
    SCRAPE_MAX_MEDIA_URLS,
    SCRAPE_MAX_PARALLEL_DOWNLOADS,
    SCRAPE_MIN_IMAGE_SIZE,
    SCRAPE_PAYWALL_BYPASS,
    SCRAPE_SCROLL_MAX_ROUNDS,
    SCRAPE_SCROLL_PAUSE_MS,
    YTDLP_MAX_HEIGHT,
    YTDLP_SOCKET_TIMEOUT,
)
from messages import msg
from utils import (
    async_download_file,
    async_download_via_playwright,
    async_ffmpeg_remux,
    normalize_image,
    safe_url,
)

from ._caption import _build_caption
from ._scrape_helpers import (
    MediaTuple,
    classify_media_url,
    dedupe_key,
    extract_article,
    extract_iframes,
    extract_jsonld_media,
    extract_meta_media,
    extract_player_configs,
    is_junk_url,
    merge_media_lists,
    rewrite_to_max_resolution,
)

logger = logging.getLogger(__name__)


_FACEBOOK_HOSTS = ('facebook.com', 'fb.com', 'fb.watch')
_PAYWALL_PATTERNS = (
    'sign in to continue', 'log in to continue', 'subscribe to read',
    'create a free account to read', 'this content is for subscribers',
    'faça login para continuar', 'assine para ler', 'conteúdo exclusivo para assinantes',
)


def _is_facebook(url: str) -> bool:
    try:
        host = (urlparse(url).netloc or '').lower()
    except Exception:
        return False
    if host.startswith('www.'):
        host = host[4:]
    return any(host == h or host.endswith('.' + h) for h in _FACEBOOK_HOSTS)


_GOOGLEBOT_UA = (
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
)


async def _fetch_html(
    url: str,
    timeout: int,
    user_agent: Optional[str] = None,
) -> Optional[str]:
    loop = asyncio.get_running_loop()
    headers = {'User-Agent': user_agent} if user_agent else None
    try:
        r = await loop.run_in_executor(
            state.IO_POOL,
            lambda: curl_requests.get(
                url, impersonate="chrome", timeout=timeout,
                allow_redirects=True, headers=headers,
            ),
        )
    except Exception as e:
        logger.debug(f"curl_cffi falhou pra {safe_url(url)}: {e}")
        return None
    if r.status_code != 200:
        logger.debug(f"Fast-path HTTP {r.status_code} pra {safe_url(url)}")
        return None
    return r.text


def _looks_like_paywall(html: str) -> bool:
    if not html:
        return False
    low = html.lower()
    return any(p in low for p in _PAYWALL_PATTERNS)


async def _try_archive_today(url: str, timeout: int) -> Optional[str]:
    archive_url = f"https://archive.ph/newest/{quote(url, safe=':/?&=')}"
    logger.info(f"📚 Tentando archive.ph para: {safe_url(url)}")
    return await _fetch_html(archive_url, timeout=timeout)


async def _fetch_html_with_paywall_bypass(
    url: str, timeout: int,
) -> tuple[Optional[str], str]:
    html = await _fetch_html(url, timeout=timeout)
    if not _looks_like_paywall(html or ""):
        return html, ('normal' if html else '')

    if SCRAPE_PAYWALL_BYPASS != "yes":
        return html, 'normal'

    logger.info(f"🔒 Paywall detectado em {safe_url(url)} — tentando Googlebot UA.")
    gbot_html = await _fetch_html(url, timeout=timeout, user_agent=_GOOGLEBOT_UA)
    if gbot_html and not _looks_like_paywall(gbot_html):
        logger.info(f"✅ Googlebot UA passou do paywall em {safe_url(url)}")
        return gbot_html, 'googlebot'

    arch_html = await _try_archive_today(url, timeout=SCRAPE_ARCHIVE_TIMEOUT_S)
    if arch_html and not _looks_like_paywall(arch_html):
        logger.info(f"✅ archive.ph retornou conteúdo para {safe_url(url)}")
        return arch_html, 'archive'

    logger.warning(f"❌ Paywall não vencido para {safe_url(url)}")
    return html, 'normal'


def _normalize_kind(kind: str, url: str) -> str:
    if kind in ('image', 'video', 'hls', 'dash'):
        return kind
    return classify_media_url(url) or 'image'


async def _gather_media_via_playwright(
    page_url: str,
) -> tuple[list[MediaTuple], list[str], str]:
    """Scrape via Playwright. Retorna (media_tuples, iframe_urls, page_text)."""
    if not state.PW_BROWSER or not state.PW_CONTEXT:
        return [], [], ""

    captured_responses: list[tuple[str, str]] = []
    page_html: str = ""

    async with state.PW_SEMAPHORE:
        page = None
        try:
            page = await state.PW_CONTEXT.new_page()

            async def handle_response(response):
                try:
                    rtype = response.request.resource_type
                    ct = (response.headers.get('content-type') or '').lower()
                    if rtype in ('image', 'media') or 'mpegurl' in ct or 'dash+xml' in ct:
                        u = response.url
                        if u.startswith('http'):
                            captured_responses.append((u, ct))
                except Exception as e:
                    logger.debug(f"handle_response: {e}")

            page.on("response", handle_response)
            await page.goto(page_url, wait_until="load", timeout=PW_GOTO_TIMEOUT_MS)

            prev_count = -1
            for _ in range(SCRAPE_SCROLL_MAX_ROUNDS):
                try:
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                except Exception as e:
                    logger.debug(f"scroll falhou: {e}")
                    break
                await page.wait_for_timeout(SCRAPE_SCROLL_PAUSE_MS)
                if len(captured_responses) == prev_count:
                    break
                prev_count = len(captured_responses)

            try:
                page_html = await page.content()
            except Exception as e:
                logger.debug(f"page.content falhou: {e}")

        except Exception as e:
            logger.warning(f"❌ Erro Scraper Playwright: {e}")
        finally:
            if page is not None:
                try:
                    await page.close()
                except Exception:
                    pass

    sniffed: list[MediaTuple] = []
    for u, ct in captured_responses:
        kind = classify_media_url(u, ct)
        if kind:
            sniffed.append((kind, u))

    meta = extract_meta_media(page_html, page_url) if page_html else []
    jsonld = extract_jsonld_media(page_html, page_url) if page_html else []
    players = extract_player_configs(page_html, page_url) if page_html else []
    iframes = extract_iframes(page_html, page_url) if page_html else []

    media = merge_media_lists(meta, jsonld, sniffed, players, cap=SCRAPE_MAX_MEDIA_URLS)
    return media, iframes, page_html


def _gather_media_from_html(html: str, base_url: str) -> list[MediaTuple]:
    meta = extract_meta_media(html, base_url)
    jsonld = extract_jsonld_media(html, base_url)
    players = extract_player_configs(html, base_url)
    return merge_media_lists(meta, jsonld, players, cap=SCRAPE_MAX_MEDIA_URLS)


def _prepare_for_download(
    media: list[MediaTuple],
) -> list[MediaTuple]:
    out: list[MediaTuple] = []
    seen_keys: set[str] = set()
    junked = 0
    deduped = 0
    for kind, url in media:
        if is_junk_url(url):
            junked += 1
            continue
        rewritten = rewrite_to_max_resolution(url)
        normalized_kind = _normalize_kind(kind, rewritten)
        key = dedupe_key(rewritten)
        if key in seen_keys:
            deduped += 1
            continue
        seen_keys.add(key)
        out.append((normalized_kind, rewritten))
    if junked or deduped:
        logger.info(
            f"🧹 _prepare_for_download: {len(media)} entrada(s) → {len(out)} (junk={junked}, dedupe={deduped})"
        )
    return out


async def _download_one(
    kind: str,
    media_url: str,
    page_url: str,
    folder: str,
    idx: int,
    failed_counter: list[int],
) -> Optional[str]:
    """Baixa uma mídia. Retorna o caminho final (já normalizado) ou None."""
    headers = {'Referer': page_url} if page_url else None

    if kind in ('hls', 'dash'):
        out_path = os.path.join(folder, f"scrape_media_{idx}.mp4")
        ok = await async_ffmpeg_remux(
            media_url, out_path, timeout=SCRAPE_HLS_TIMEOUT_S, headers=headers,
        )
        if ok:
            return out_path
        return None

    ext = ".mp4" if kind == "video" else ".jpg"
    filepath = os.path.join(folder, f"scrape_media_{idx}{ext}")

    try:
        result = await async_download_file(
            media_url, filepath, headers=headers, return_content_type=True,
        )
    except Exception as e:
        logger.warning(f"⚠️ async_download falhou: {e}")
        result = (False, '')

    success, ct = (result if isinstance(result, tuple) else (result, ''))

    if not success:
        ok = await async_download_via_playwright(media_url, filepath, referer=page_url)
        if not ok:
            failed_counter[0] += 1
            return None

    if kind == "image":
        normalized = normalize_image(filepath, min_size=SCRAPE_MIN_IMAGE_SIZE)
        return normalized
    return filepath


async def _download_all(
    media: list[MediaTuple],
    page_url: str,
    folder: str,
) -> tuple[list[str], int]:
    """Baixa em paralelo. Retorna (arquivos, contagem_de_403)."""
    semaphore = asyncio.Semaphore(SCRAPE_MAX_PARALLEL_DOWNLOADS)
    failed_counter = [0]

    async def task(idx: int, kind: str, url: str) -> Optional[str]:
        async with semaphore:
            return await _download_one(kind, url, page_url, folder, idx, failed_counter)

    coros = [task(i, k, u) for i, (k, u) in enumerate(media)]
    results = await asyncio.gather(*coros, return_exceptions=True)

    files: list[str] = []
    seen_paths: set[str] = set()
    for r in results:
        if isinstance(r, Exception):
            logger.debug(f"Download task exception: {r}")
            continue
        if r and r not in seen_paths and os.path.exists(r):
            seen_paths.add(r)
            files.append(r)
    return files, failed_counter[0]


async def _ytdlp_generic(url: str, folder: str) -> list[str]:
    """yt-dlp em modo genérico forçado. Cobre iframe/JSON-LD/HLS de saída."""
    import yt_dlp

    opts = {
        'outtmpl': os.path.join(folder, 'generic_%(autonumber)s.%(ext)s'),
        'restrictfilenames': True,
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
        'noplaylist': True,
        'force_generic_extractor': True,
        'socket_timeout': YTDLP_SOCKET_TIMEOUT,
        'format': f'bestvideo[height<={YTDLP_MAX_HEIGHT}]+bestaudio/best[height<={YTDLP_MAX_HEIGHT}]/best',
        'merge_output_format': 'mp4',
    }

    loop = asyncio.get_running_loop()

    def _run():
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.extract_info(url, download=True)
        except Exception as e:
            logger.debug(f"yt-dlp generic exception: {e}")

    try:
        await loop.run_in_executor(state.YTDLP_POOL, _run)
    except Exception as e:
        logger.debug(f"yt-dlp generic executor falhou: {e}")
        return []

    if not os.path.exists(folder):
        return []
    return sorted(
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if os.path.isfile(os.path.join(folder, f))
        and not f.endswith(('.part', '.ytdl', '.temp'))
    )


_GALLERY_DL_LOCK = asyncio.Lock()
_GALLERY_DL_LOADED = False


def _can_handle_with_gallery_dl(url: str) -> bool:
    try:
        from gallery_dl import extractor
        return extractor.find(url) is not None
    except Exception as e:
        logger.debug(f"gallery-dl extractor.find falhou: {e}")
        return False


def _list_files_in(folder: str) -> list[str]:
    if not os.path.exists(folder):
        return []
    out: list[str] = []
    for root, _, files in os.walk(folder):
        for f in files:
            if f.endswith(('.part', '.json', '.txt')):
                continue
            out.append(os.path.join(root, f))
    return sorted(out)


async def _gallery_dl_run(url: str, folder: str) -> list[str]:
    """Roda gallery-dl pra URL. Útil em galerias (Pinterest, Imgur, Tumblr, etc.)."""
    if SCRAPE_GALLERY_DL_ENABLE != "yes":
        return []
    if not _can_handle_with_gallery_dl(url):
        return []

    files_before = set(_list_files_in(folder))

    async with _GALLERY_DL_LOCK:
        global _GALLERY_DL_LOADED
        from gallery_dl import config as gdl_config, job as gdl_job

        if not _GALLERY_DL_LOADED:
            try:
                gdl_config.load()
            except Exception as e:
                logger.debug(f"gallery-dl config.load falhou: {e}")
            _GALLERY_DL_LOADED = True

        gdl_config.set(('extractor',), 'base-directory', folder + os.sep)
        gdl_config.set(('extractor',), 'directory', [])
        gdl_config.set(('extractor',), 'filename', 'galdl_{num:>03}.{extension}')
        gdl_config.set(('extractor',), 'skip', True)
        gdl_config.set((), 'output', {'mode': 'null'})

        loop = asyncio.get_running_loop()

        def _run() -> None:
            try:
                gdl_job.DownloadJob(url).run()
            except Exception as e:
                logger.debug(f"gallery-dl job exception: {e}")

        try:
            await asyncio.wait_for(
                loop.run_in_executor(state.YTDLP_POOL, _run),
                timeout=SCRAPE_GALLERY_DL_TIMEOUT_S,
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"⚠️ gallery-dl timeout ({SCRAPE_GALLERY_DL_TIMEOUT_S}s) pra {safe_url(url)}"
            )
        except Exception as e:
            logger.debug(f"gallery-dl executor falhou: {e}")

    files_after = set(_list_files_in(folder))
    new_files = sorted(files_after - files_before)
    return new_files


async def _ytdlp_generic_iframes(iframes: list[str], folder: str) -> list[str]:
    for iframe_url in iframes:
        logger.info(f"🪟 Tentando yt-dlp generic em iframe: {safe_url(iframe_url)}")
        files = await _ytdlp_generic(iframe_url, folder)
        if files:
            return files
    return []


async def take_page_screenshot(folder: str, url: str) -> Optional[str]:
    """Captura screenshot da fold da página. Retorna o path ou None se falhar."""
    if not state.PW_BROWSER or not state.PW_CONTEXT:
        return None
    if not os.path.exists(folder):
        os.makedirs(folder)
    out_path = os.path.join(folder, "screenshot.jpg")
    async with state.PW_SEMAPHORE:
        page = None
        try:
            page = await state.PW_CONTEXT.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=PW_GOTO_TIMEOUT_MS)
            await page.wait_for_timeout(2000)
            await page.screenshot(path=out_path, full_page=False, type='jpeg', quality=85)
        except Exception as e:
            logger.warning(f"⚠️ Falha screenshot: {e}")
            return None
        finally:
            if page is not None:
                try:
                    await page.close()
                except Exception:
                    pass
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        return out_path
    return None


def _build_status(
    files: list[str], status_key: str, count_override: Optional[int] = None,
) -> str:
    has_video = any(f.endswith('.mp4') for f in files)
    if has_video and len(files) > 1:
        label = msg("media_type_labels.scraper_video_mixed")
    elif has_video:
        label = msg("media_type_labels.scraper_video")
    else:
        label = msg("media_type_labels.scraper_images")
    return msg(status_key, media_type=label, count=count_override or len(files))


def _drop_facebook_image_only(files: list[str], page_url: str) -> list[str]:
    if not _is_facebook(page_url):
        return files
    has_video = any(f.endswith('.mp4') for f in files)
    if has_video:
        return files
    logger.warning(
        f"⚠️ Scraper achou {len(files)} mídias para Facebook, "
        "mas nenhuma é vídeo — provavelmente lixo de UI. Descartando."
    )
    return []


async def fetch_article_caption(url: str, html: Optional[str] = None) -> str:
    if SCRAPE_ARTICLE_EXTRACT != "yes":
        return ""
    if html is None:
        html, _ = await _fetch_html_with_paywall_bypass(
            url, timeout=SCRAPE_FAST_PATH_TIMEOUT_S,
        )
    if not html:
        return ""
    result = extract_article(html, url=url, min_chars=SCRAPE_ARTICLE_MIN_CHARS)
    if not result:
        return ""
    title, body = result
    caption, _ = _build_caption({'title': title, 'description': body}, url)
    logger.info(
        f"📰 Artigo detectado ({len(body)} chars body, "
        f"caption {len(caption)} chars) em {safe_url(url)}"
    )
    return caption


async def scrape_fallback(
    url: str, unique_folder: str,
) -> tuple[list[str], str, str, bool]:
    logger.info(f"🕸️ Iniciando Scraping Multi-Tier para: {safe_url(url)}")

    if not os.path.exists(unique_folder):
        os.makedirs(unique_folder)

    pw_available = bool(state.PW_BROWSER and state.PW_CONTEXT)

    if pw_available:
        bypass_result, pw_result = await asyncio.gather(
            _fetch_html_with_paywall_bypass(url, timeout=SCRAPE_FAST_PATH_TIMEOUT_S),
            _gather_media_via_playwright(url),
        )
        fast_html, html_source = bypass_result
        pw_media, iframes, page_html = pw_result
    else:
        fast_html, html_source = await _fetch_html_with_paywall_bypass(
            url, timeout=SCRAPE_FAST_PATH_TIMEOUT_S,
        )
        pw_media, iframes, page_html = [], [], ""

    paywall_in_pw = _looks_like_paywall(page_html)

    article_text = await fetch_article_caption(url, html=fast_html or page_html)
    is_article = bool(article_text)

    fast_media = _gather_media_from_html(fast_html, url) if fast_html else []
    combined = merge_media_lists(fast_media, pw_media, cap=SCRAPE_MAX_MEDIA_URLS)
    logger.info(
        f"🔎 Combinado: {len(fast_media)} HTML ({html_source}) + {len(pw_media)} Playwright "
        f"→ {len(combined)} (após dedupe), {len(iframes)} iframe(s) embed."
    )

    prepared = _prepare_for_download(combined)
    files: list[str] = []
    failed = 0
    if prepared:
        files, failed = await _download_all(prepared, url, unique_folder)
        files = _drop_facebook_image_only(files, url)

    if files:
        return files, _build_status(files, "downloader_status.scraper"), article_text, is_article

    logger.info("🧩 Tentando yt-dlp em modo genérico...")
    yt_files = await _ytdlp_generic(url, unique_folder)
    if yt_files:
        return yt_files, _build_status(yt_files, "downloader_status.scraper_generic_ytdlp"), article_text, is_article

    logger.info("🖼️ Tentando gallery-dl...")
    galdl_files = await _gallery_dl_run(url, unique_folder)
    if galdl_files:
        return galdl_files, _build_status(galdl_files, "downloader_status.scraper_gallerydl"), article_text, is_article

    if iframes:
        iframe_files = await _ytdlp_generic_iframes(iframes, unique_folder)
        if iframe_files:
            return iframe_files, _build_status(iframe_files, "downloader_status.scraper_generic_ytdlp"), article_text, is_article

    if not pw_available:
        return [], msg("downloader_status.playwright_not_running"), "", False

    if paywall_in_pw or (failed > 0 and failed == len(prepared) and prepared):
        return [], msg("downloader_status.scraper_paywall"), "", False

    return [], msg("downloader_status.scraper_fail"), "", False
