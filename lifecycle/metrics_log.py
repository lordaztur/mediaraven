import asyncio
import logging

import metrics
from config import METRICS_LOG_INTERVAL_MIN

logger = logging.getLogger(__name__)


METRICS_LOG_INTERVAL = METRICS_LOG_INTERVAL_MIN * 60


async def periodic_metrics_log() -> None:
    while True:
        await asyncio.sleep(METRICS_LOG_INTERVAL)
        try:
            logger.info(metrics.format_summary())
        except Exception as e:
            logger.debug(f"Falha ao logar métricas: {e}")
