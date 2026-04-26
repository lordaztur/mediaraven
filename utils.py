import asyncio
import logging
import os
import shutil
import time
from typing import Any, Optional
from urllib.parse import urlparse, urlunparse

import aiofiles
from PIL import Image
from telegram.error import RetryAfter

import state
from config import (
    DOWNLOAD_TIMEOUT_SECONDS,
    SAFE_URL_MAX_LENGTH,
    STATUS_CYCLE_INTERVAL,
)
from messages import msg_list

logger = logging.getLogger(__name__)


def safe_url(url: str, max_length: int = SAFE_URL_MAX_LENGTH) -> str:
    if not isinstance(url, str) or not url:
        return "<invalid-url>"
    try:
        parsed = urlparse(url)
        cleaned = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
    except Exception:
        return "<invalid-url>"
    if len(cleaned) > max_length:
        return cleaned[:max_length] + "...(truncated)"
    return cleaned


def normalize_image(filepath: str, min_size: int = 50, quality: int = 95) -> Optional[str]:
    try:
        with Image.open(filepath) as img:
            width, height = img.size
            if width < min_size or height < min_size:
                logger.warning(
                    f"⏭️ Skip (imagem {width}x{height} < min_size {min_size}): {filepath}"
                )
                try:
                    os.remove(filepath)
                except OSError:
                    pass
                return None

            needs_convert = img.format in ('WEBP', 'TIFF') or img.mode in ('RGBA', 'P', 'LA', 'CMYK')
            if not needs_convert:
                return filepath

            rgb_im = img.convert('RGB')

        new_filepath = filepath.rsplit('.', 1)[0] + '.jpg'
        rgb_im.save(new_filepath, 'JPEG', quality=quality)
        if filepath != new_filepath:
            try:
                os.remove(filepath)
            except OSError:
                pass
        return new_filepath
    except Exception as e:
        logger.debug(f"normalize_image falhou para {filepath}: {e}")
        try:
            os.remove(filepath)
        except OSError:
            pass
        return None


async def safe_cleanup(folder: str) -> None:
    def _cleanup():
        if not os.path.exists(folder):
            return
        for attempt in range(3):
            try:
                shutil.rmtree(folder)
                break
            except Exception as e:
                if attempt == 2:
                    logger.warning(f"⚠️ Falha final ao limpar pasta '{folder}': {e}")
                else:
                    time.sleep(1)

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(state.IO_POOL, _cleanup)


DOWNLOAD_CHUNK_SIZE = 8192


async def async_download_file(
    url: str,
    filepath: str,
    headers: Optional[dict] = None,
    return_content_type: bool = False,
):
    """Baixa via aiohttp. Se return_content_type=True, retorna (ok, content_type)."""
    ct = ''
    try:
        async with state.AIOHTTP_SESSION.get(
            url, timeout=DOWNLOAD_TIMEOUT_SECONDS, headers=headers,
        ) as response:
            ct = (response.headers.get('Content-Type') or '').lower()
            if response.status == 200:
                if ct.startswith(('text/html', 'application/json')):
                    logger.warning(f"⏭️ Skip (Content-Type {ct}): {url}")
                    return (False, ct) if return_content_type else False

                async with aiofiles.open(filepath, 'wb') as f:
                    async for chunk in response.content.iter_chunked(DOWNLOAD_CHUNK_SIZE):
                        await f.write(chunk)

                try:
                    if os.path.getsize(filepath) == 0:
                        logger.debug(f"Download produziu arquivo vazio: {filepath}")
                        os.remove(filepath)
                        return (False, ct) if return_content_type else False
                except OSError:
                    return (False, ct) if return_content_type else False
                return (True, ct) if return_content_type else True
            logger.warning(f"⏭️ Skip (HTTP {response.status}): {url}")
            return (False, ct) if return_content_type else False
    except Exception as e:
        logger.warning(f"⚠️ Erro no aiohttp download ({url}): {e}")
    return (False, ct) if return_content_type else False


async def async_download_via_playwright(
    url: str,
    filepath: str,
    referer: Optional[str] = None,
) -> bool:
    """Fallback de download usando o contexto do Playwright (herda cookies + UA).

    Útil quando o aiohttp leva 403 por falta de Referer/cookie de sessão.
    """
    if not state.PW_CONTEXT:
        return False
    headers = {'Referer': referer} if referer else None
    try:
        resp = await state.PW_CONTEXT.request.get(url, headers=headers)
    except Exception as e:
        logger.warning(f"⚠️ Erro PW request: {e}")
        return False
    try:
        if resp.status != 200:
            logger.warning(f"⏭️ Skip PW (HTTP {resp.status}): {url}")
            return False
        body = await resp.body()
        if not body:
            logger.warning(f"⏭️ Skip PW (corpo vazio): {url}")
            return False
        async with aiofiles.open(filepath, 'wb') as f:
            await f.write(body)
        return os.path.getsize(filepath) > 0
    except Exception as e:
        logger.warning(f"⚠️ Erro escrevendo PW download: {e}")
        return False
    finally:
        try:
            await resp.dispose()
        except Exception:
            pass


async def async_ffmpeg_remux(
    input_url: str,
    output_path: str,
    timeout: int = 180,
    headers: Optional[dict] = None,
) -> bool:
    """Mux HLS/DASH/qualquer URL stream pra mp4 via ffmpeg copy (sem re-encode)."""
    process = None
    ffmpeg_bin = state.FFMPEG_PATH or 'ffmpeg'
    try:
        cmd = [ffmpeg_bin, '-y']
        if headers:
            header_blob = ''.join(f"{k}: {v}\r\n" for k, v in headers.items())
            cmd.extend(['-headers', header_blob])
        cmd.extend([
            '-i', input_url,
            '-c', 'copy',
            '-bsf:a', 'aac_adtstoasc',
            '-movflags', '+faststart',
            output_path,
        ])
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        if process.returncode != 0:
            err = stderr.decode('utf-8', errors='ignore')
            logger.warning(f"⚠️ ffmpeg remux falhou: {err[-400:]}")
            return False
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except asyncio.TimeoutError:
        logger.warning(f"⚠️ ffmpeg remux timeout ({timeout}s) pra {input_url}")
        try:
            if process:
                process.kill()
                await process.wait()
        except Exception:
            pass
        return False
    except Exception as e:
        logger.warning(f"⚠️ Erro fatal no ffmpeg remux: {e}")
        return False


async def async_merge_audio_image(
    image_path: str,
    audio_path: str,
    output_path: str,
    start_time: Optional[float] = None,
    duration: Optional[float] = None,
) -> bool:
    process = None
    ffmpeg_bin = state.FFMPEG_PATH or 'ffmpeg'
    try:
        cmd = [ffmpeg_bin, '-y', '-loop', '1', '-framerate', '1', '-i', image_path]

        if start_time is not None:
            cmd.extend(['-ss', str(start_time)])

        cmd.extend(['-i', audio_path])
        cmd.extend(['-map', '0:v:0', '-map', '1:a:0'])

        if duration is not None:
            cmd.extend(['-t', str(duration)])

        cmd.extend([
            '-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'stillimage',
            '-c:a', 'aac', '-b:a', '192k',
            '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2',
            '-pix_fmt', 'yuv420p', '-shortest',
            output_path
        ])

        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)

        if process.returncode != 0:
            err_msg = stderr.decode('utf-8', errors='ignore')
            logger.error(f"⚠️ Erro FFmpeg: {err_msg}")
            return False

        return True
    except asyncio.TimeoutError:
        logger.error("⚠️ FFmpeg travou e foi interrompido (Timeout 60s).")
        try:
            if process:
                process.kill()
                await process.wait()
        except Exception:
            pass
        return False
    except Exception as e:
        logger.error(f"⚠️ Erro fatal no FFmpeg Merge: {e}")
        return False


async def cycle_status_message(status_msg: Any, suffix: str = "") -> None:
    messages = [m.format(suffix=suffix) for m in msg_list("status_cycle")]
    idx = 1 % len(messages)
    try:
        while True:
            try:
                await status_msg.edit_text(messages[idx])
            except RetryAfter as e:
                await asyncio.sleep(e.retry_after)
                continue
            except Exception as str_err:
                err_msg = str(str_err).lower()
                if "not found" in err_msg or "deleted" in err_msg or "message to edit not found" in err_msg:
                    break
            await asyncio.sleep(STATUS_CYCLE_INTERVAL)
            idx = (idx + 1) % len(messages)
    except asyncio.CancelledError:
        pass
