import asyncio
import logging
import os
from typing import Any, Optional

from PIL import Image
from telegram import InputMediaPhoto, InputMediaVideo
from telegram.error import RetryAfter, TimedOut

from config import (
    cfg,
    ANIMATION_EXTS,
    IMAGE_EXTS,
    VIDEO_EXTS,
)
from messages import lmsg
from utils import async_ensure_telegram_video, async_gif_to_mp4, is_telegram_compatible_video_ext

logger = logging.getLogger(__name__)


def _get_image_dims(filepath: str) -> tuple[Optional[int], Optional[int]]:
    try:
        with Image.open(filepath) as img:
            return img.size
    except Exception:
        return None, None


async def _gif_to_mp4(gif_path: str) -> Optional[str]:
    mp4_path = os.path.splitext(gif_path)[0] + '.gif.mp4'
    if await async_gif_to_mp4(gif_path, mp4_path):
        return mp4_path
    return None


async def _ensure_video(f_path: str) -> str:
    if is_telegram_compatible_video_ext(f_path):
        return f_path
    converted = await async_ensure_telegram_video(f_path, timeout=cfg("VIDEO_CONVERT_TIMEOUT"))
    return converted or f_path


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
                elif filename_lower.endswith(ANIMATION_EXTS):
                    anim_kwargs = dict(upload_kwargs)
                    width, height = _get_image_dims(f_path)
                    if width and height:
                        anim_kwargs.setdefault('width', width)
                        anim_kwargs.setdefault('height', height)
                    anim_path = await _gif_to_mp4(f_path) or f_path
                    await context.bot.send_animation(chat_id=chat_id, animation=anim_path, **anim_kwargs)
                elif filename_lower.endswith(VIDEO_EXTS):
                    video_path = await _ensure_video(f_path)
                    await context.bot.send_video(chat_id=chat_id, video=video_path, supports_streaming=True, **upload_kwargs)
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
                elif filename_lower.endswith(VIDEO_EXTS) or filename_lower.endswith(ANIMATION_EXTS):
                    video_path = await _ensure_video(f_path) if filename_lower.endswith(VIDEO_EXTS) else f_path
                    media_group.append(InputMediaVideo(media=video_path, parse_mode='HTML', caption=item_caption))

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
