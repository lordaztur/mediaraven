import asyncio
import logging

import aiohttp
from cachetools import TTLCache
from playwright.async_api import async_playwright

import state
from config import (
    AIOHTTP_CONN_LIMIT,
    AIOHTTP_CONNECT_TIMEOUT,
    AIOHTTP_READ_TIMEOUT,
    AIOHTTP_TOTAL_TIMEOUT,
    PLAYWRIGHT_UA,
    PW_VIEWPORT_HEIGHT,
    PW_VIEWPORT_WIDTH,
    SHUTDOWN_TASKS_TIMEOUT,
    TTL_FUTURES_SECONDS,
    TTL_RETRIES_SECONDS,
)
from cookies import extract_firefox_cookies

from .instagram_login import init_instagrapi_async
from .metrics_log import periodic_metrics_log
from .playwright_refresh import periodic_playwright_refresh
from .startup import startup_cleanup_async

logger = logging.getLogger(__name__)


async def init_globals(app) -> None:
    await startup_cleanup_async()

    connector = aiohttp.TCPConnector(limit=AIOHTTP_CONN_LIMIT)
    default_timeout = aiohttp.ClientTimeout(
        total=AIOHTTP_TOTAL_TIMEOUT,
        connect=AIOHTTP_CONNECT_TIMEOUT,
        sock_read=AIOHTTP_READ_TIMEOUT,
    )
    state.AIOHTTP_SESSION = aiohttp.ClientSession(
        connector=connector, timeout=default_timeout,
    )
    logger.info(f"🌐 Sessão aiohttp global iniciada (timeout default {AIOHTTP_TOTAL_TIMEOUT}s).")

    logger.info("🌐 Iniciando Playwright (Navegador Global)...")
    state.PW_MANAGER = await async_playwright().start()
    state.PW_BROWSER = await state.PW_MANAGER.chromium.launch(headless=True)
    state.PW_CONTEXT = await state.PW_BROWSER.new_context(
        user_agent=PLAYWRIGHT_UA,
        viewport={'width': PW_VIEWPORT_WIDTH, 'height': PW_VIEWPORT_HEIGHT},
    )

    state.FIREFOX_COOKIES_CACHE = extract_firefox_cookies()
    if state.FIREFOX_COOKIES_CACHE:
        try:
            await state.PW_CONTEXT.add_cookies(state.FIREFOX_COOKIES_CACHE)
            logger.info(f"✅ {len(state.FIREFOX_COOKIES_CACHE)} cookies do Firefox carregados no Playwright!")
        except Exception as e:
            logger.warning(f"⚠️ Erro ao injetar cookies no Playwright: {e}")

    logger.info("✅ Contexto Playwright pronto com cookies carregados!")

    app.bot_data['lang_requests'] = TTLCache(maxsize=1000, ttl=TTL_RETRIES_SECONDS)
    app.bot_data['retries'] = TTLCache(maxsize=1000, ttl=TTL_RETRIES_SECONDS)
    app.bot_data['dl_futures'] = TTLCache(maxsize=1000, ttl=TTL_FUTURES_SECONDS)
    app.bot_data['lang_futures'] = TTLCache(maxsize=1000, ttl=TTL_FUTURES_SECONDS)
    app.bot_data['caption_futures'] = TTLCache(maxsize=1000, ttl=TTL_FUTURES_SECONDS)
    app.bot_data['screenshot_futures'] = TTLCache(maxsize=1000, ttl=TTL_FUTURES_SECONDS)
    logger.info("✅ Todos os serviços globais prontos!")

    asyncio.create_task(periodic_playwright_refresh())
    logger.info("🧹 Tarefa de limpeza de memória agendada.")

    asyncio.create_task(init_instagrapi_async())
    logger.info("📸 Login do Instagrapi iniciado em background.")

    asyncio.create_task(periodic_metrics_log())
    logger.info("📊 Log periódico de métricas agendado.")


async def stop_globals(app) -> None:
    logger.info("🛑 Desligando serviços globais...")

    pending = [t for t in state.background_tasks if not t.done()]
    if pending:
        logger.info(f"⏳ Aguardando {len(pending)} download(s) em andamento (até {SHUTDOWN_TASKS_TIMEOUT}s)...")
        try:
            await asyncio.wait_for(
                asyncio.gather(*pending, return_exceptions=True),
                timeout=SHUTDOWN_TASKS_TIMEOUT,
            )
            logger.info("✅ Downloads pendentes finalizados.")
        except asyncio.TimeoutError:
            still_pending = [t for t in pending if not t.done()]
            logger.warning(f"⚠️ {len(still_pending)} task(s) não terminaram a tempo; cancelando.")
            for t in still_pending:
                t.cancel()
            await asyncio.gather(*still_pending, return_exceptions=True)

    if state.AIOHTTP_SESSION:
        await state.AIOHTTP_SESSION.close()
    if state.PW_CONTEXT:
        await state.PW_CONTEXT.close()
    if state.PW_BROWSER:
        await state.PW_BROWSER.close()
    if state.PW_MANAGER:
        await state.PW_MANAGER.stop()

    for pool_name in ('YTDLP_POOL', 'IG_POOL', 'IO_POOL'):
        pool = getattr(state, pool_name, None)
        if pool is not None:
            try:
                pool.shutdown(wait=False, cancel_futures=True)
            except Exception as e:
                logger.debug(f"Falha ao desligar {pool_name}: {e}")

    logger.info("✅ Shutdown completo.")
