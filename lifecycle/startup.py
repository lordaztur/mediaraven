import asyncio
import logging
import os
import shutil

import state
from config import BASE_DOWNLOAD_DIR

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
        logger.info(f"🦕 Deno encontrado em: {state.DENO_PATH} (Pronto para bypass do YouTube)")


def init_ffmpeg() -> None:
    state.FFMPEG_PATH = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if state.FFMPEG_PATH:
        logger.info(f"🎬 ffmpeg encontrado em: {state.FFMPEG_PATH}")
    else:
        logger.warning(
            "⚠️ ffmpeg não encontrado no PATH. "
            "Posts do Instagram com áudio+imagem não vão funcionar. "
            "Linux: apt install ffmpeg | Windows: choco install ffmpeg"
        )


def _sync_startup_cleanup() -> None:
    folder = BASE_DOWNLOAD_DIR
    if not os.path.exists(folder):
        return
    try:
        for item in os.listdir(folder):
            item_path = os.path.join(folder, item)
            if os.path.isdir(item_path) and item.startswith("task_"):
                shutil.rmtree(item_path)
        logger.info("🧹 Limpeza inicial: Pastas temporárias residuais removidas.")
    except Exception as e:
        logger.error(f"⚠️ Erro na limpeza inicial: {e}")


async def startup_cleanup_async() -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(state.IO_POOL, _sync_startup_cleanup)
