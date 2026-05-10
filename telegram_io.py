import asyncio
import logging
from typing import Any, Optional

from telegram import InputMediaPhoto, InputMediaVideo
from telegram.error import RetryAfter, TimedOut

from config import (
    cfg,
    IMAGE_EXTS,
    VIDEO_EXTS,
)
from messages import lmsg

logger = logging.getLogger(__name__)


async def send_downloaded_media(
    context: Any,
    chat_id: int,
    files: list[str],
    original_msg_id: int,
    upload_kwargs: dict[str, Any],
    caption: Optional[str] = None,
) -> None:
    if len(files) == 1:
        f_path = files[0]
        if caption:
            upload_kwargs['caption'] = caption

        timeout = cfg("TELEGRAM_UPLOAD_TIMEOUT")
        upload_kwargs.setdefault('read_timeout', timeout)
        upload_kwargs.setdefault('write_timeout', timeout)
        upload_kwargs.setdefault('connect_timeout', timeout)

        filename_lower = f_path.lower()
        for attempt in range(4):
            try:
                if filename_lower.endswith(IMAGE_EXTS):
                    await context.bot.send_photo(chat_id=chat_id, photo=f_path, **upload_kwargs)
                elif filename_lower.endswith(VIDEO_EXTS):
                    await context.bot.send_video(chat_id=chat_id, video=f_path, supports_streaming=True, **upload_kwargs)
                else:
                    await context.bot.send_document(chat_id=chat_id, document=f_path, **upload_kwargs)
                break
            except RetryAfter as e:
                logger.warning(lmsg("telegram_io.flood_control_telegram", arg0=e.retry_after))
                await asyncio.sleep(e.retry_after + 1)
            except TimedOut:
                logger.warning(lmsg("telegram_io.timeout_no_envio"))
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(lmsg("telegram_io.erro_fatal_ao", e=e), exc_info=True)
                raise e
    else:
        chunk_size = cfg("MEDIA_GROUP_CHUNK_SIZE")
        for i in range(0, len(files), chunk_size):
            chunk_files = files[i:i + chunk_size]
            media_group = []

            for f_path in chunk_files:
                filename_lower = f_path.lower()
                item_caption = caption if (i == 0 and len(media_group) == 0) else None

                if filename_lower.endswith(IMAGE_EXTS):
                    media_group.append(InputMediaPhoto(media=f_path, parse_mode='HTML', caption=item_caption))
                elif filename_lower.endswith(VIDEO_EXTS):
                    media_group.append(InputMediaVideo(media=f_path, parse_mode='HTML', caption=item_caption))

            if media_group:
                for attempt in range(5):
                    try:
                        timeout = cfg("TELEGRAM_UPLOAD_TIMEOUT")
                        await context.bot.send_media_group(
                            chat_id=chat_id,
                            media=media_group,
                            reply_to_message_id=original_msg_id,
                            read_timeout=timeout,
                            write_timeout=timeout,
                            connect_timeout=timeout,
                        )
                        break
                    except RetryAfter as e:
                        logger.warning(lmsg("telegram_io.flood_control_de", arg0=e.retry_after))
                        await asyncio.sleep(e.retry_after + 1)
                    except TimedOut:
                        logger.warning(lmsg("telegram_io.timeout_no_envio_2"))
                        await asyncio.sleep(5)
                    except Exception as e:
                        logger.error(lmsg("telegram_io.erro_desconhecido_ao", e=e), exc_info=True)
                        raise e

                if i + chunk_size < len(files):
                    await asyncio.sleep(cfg("MEDIA_GROUP_DELAY"))
