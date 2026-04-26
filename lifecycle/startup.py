import asyncio
import logging
import os
import shutil

import state
from config import BASE_DOWNLOAD_DIR
from messages import lmsg

logger = logging.getLogger(__name__)


def init_deno() -> None:
    state.DENO_PATH = shutil.which("deno")
    if not state.DENO_PATH:
        candidates = [
            "/usr/bin/deno",
            "/usr/local/bin/deno",
            "/root/.deno/bin/deno",
            os.path.expanduser("~/.deno/bin/deno"),
            os.path.expanduser("~/.deno/bin/deno.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\deno\deno.exe"),
            os.path.expandvars(r"%USERPROFILE%\.deno\bin\deno.exe"),
        ]
        for p in candidates:
            if os.path.exists(p):
                state.DENO_PATH = p
                break
    if state.DENO_PATH:
        logger.info(lmsg("startup.deno_encontrado_em", arg0=state.DENO_PATH))


def init_ffmpeg() -> None:
    state.FFMPEG_PATH = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if state.FFMPEG_PATH:
        logger.info(lmsg("startup.ffmpeg_encontrado_em", arg0=state.FFMPEG_PATH))
    else:
        logger.warning(lmsg("startup.ffmpeg_not_found"))


def _sync_startup_cleanup() -> None:
    folder = BASE_DOWNLOAD_DIR
    if not os.path.exists(folder):
        return
    try:
        for item in os.listdir(folder):
            item_path = os.path.join(folder, item)
            if os.path.isdir(item_path) and item.startswith("task_"):
                shutil.rmtree(item_path)
        logger.info(lmsg("startup.limpeza_inicial_pastas"))
    except Exception as e:
        logger.error(lmsg("startup.erro_na_limpeza", e=e), exc_info=True)


async def startup_cleanup_async() -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(state.IO_POOL, _sync_startup_cleanup)
