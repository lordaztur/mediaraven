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
from messages import lmsg
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
    logger.info(lmsg("services.sess_o_aiohttp_global", AIOHTTP_TOTAL_TIMEOUT=AIOHTTP_TOTAL_TIMEOUT))

    logger.info(lmsg("services.iniciando_playwright_navegador"))
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
            logger.info(lmsg("services.x_cookies_do", arg0=len(state.FIREFOX_COOKIES_CACHE)))
        except Exception as e:
            logger.warning(lmsg("services.erro_ao_injetar", e=e))

    logger.info(lmsg("services.contexto_playwright_pronto"))

    app.bot_data['lang_requests'] = TTLCache(maxsize=1000, ttl=TTL_RETRIES_SECONDS)
    app.bot_data['retries'] = TTLCache(maxsize=1000, ttl=TTL_RETRIES_SECONDS)
    app.bot_data['dl_futures'] = TTLCache(maxsize=1000, ttl=TTL_FUTURES_SECONDS)
    app.bot_data['lang_futures'] = TTLCache(maxsize=1000, ttl=TTL_FUTURES_SECONDS)
    app.bot_data['caption_futures'] = TTLCache(maxsize=1000, ttl=TTL_FUTURES_SECONDS)
    app.bot_data['screenshot_futures'] = TTLCache(maxsize=1000, ttl=TTL_FUTURES_SECONDS)
    logger.info(lmsg("services.todos_os_servi_os"))

    asyncio.create_task(periodic_playwright_refresh())
    logger.info(lmsg("services.tarefa_de_limpeza"))

    asyncio.create_task(init_instagrapi_async())
    logger.info(lmsg("services.login_do_instagrapi"))

    asyncio.create_task(periodic_metrics_log())
    logger.info(lmsg("services.log_peri_dico_de"))


async def stop_globals(app) -> None:
    logger.info(lmsg("services.desligando_servi_os_globais"))

    pending = [t for t in state.background_tasks if not t.done()]
    if pending:
        logger.info(lmsg("services.aguardando_x_download", arg0=len(pending), SHUTDOWN_TASKS_TIMEOUT=SHUTDOWN_TASKS_TIMEOUT))
        try:
            await asyncio.wait_for(
                asyncio.gather(*pending, return_exceptions=True),
                timeout=SHUTDOWN_TASKS_TIMEOUT,
            )
            logger.info(lmsg("services.downloads_pendentes_finalizados"))
        except asyncio.TimeoutError:
            still_pending = [t for t in pending if not t.done()]
            logger.warning(lmsg("services.x_task_s", arg0=len(still_pending)))
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
                logger.debug(lmsg("services.falha_ao_desligar", pool_name=pool_name, e=e))

    logger.info(lmsg("services.shutdown_completo"))
