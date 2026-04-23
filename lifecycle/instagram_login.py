import asyncio
import logging
import os

from instagrapi import Client

import state
from config import IG_SESSION_FILE

logger = logging.getLogger(__name__)


def _restrict_perms(path: str) -> None:
    try:
        os.chmod(path, 0o600)
    except OSError as e:
        logger.debug(f"Falha ao aplicar chmod 0600 em {path}: {e}")


def _sync_login_instagrapi() -> None:
    ig_user = os.getenv("IG_USER")
    ig_pass = os.getenv("IG_PASS")

    if not ig_user or not ig_pass:
        logger.warning("⚠️ Credenciais do Instagram não configuradas (.env). Instagrapi não funcionará.")
        return

    try:
        cl = Client()
        if os.path.exists(IG_SESSION_FILE):
            logger.info("🍪 Carregando sessão salva do Instagrapi...")
            cl.load_settings(IG_SESSION_FILE)

        logger.info("🔐 Autenticando Instagrapi...")
        cl.login(ig_user, ig_pass)
        cl.dump_settings(IG_SESSION_FILE)
        _restrict_perms(IG_SESSION_FILE)

        state.IG_CLIENT = cl
        logger.info("✅ Instagrapi logado e pronto para uso!")
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar Instagrapi: {e}")


async def init_instagrapi_async(timeout: float = 60.0) -> None:
    loop = asyncio.get_running_loop()
    try:
        await asyncio.wait_for(
            loop.run_in_executor(state.IG_POOL, _sync_login_instagrapi),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        logger.warning(f"⌛ Login do Instagram excedeu {timeout}s. Continuando sem Instagrapi (login segue em background).")
    except Exception as e:
        logger.error(f"❌ Falha inesperada no init_instagrapi_async: {e}")
