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
from config import cfg
from messages import lmsg, msg_list

logger = logging.getLogger(__name__)


def chunk_html_text(text: str, limit: int) -> list[str]:
    """Quebra texto em pedaços ≤ limit, preferindo \\n\\n > \\n > '. ' > espaço.

    Assume que tags HTML do input ficam em linhas próprias (caso do
    _build_caption: <b>...</b> no header, <a>...</a> no rodapé). Quebrar em
    \\n\\n ou \\n preserva tags balanceadas.
    """
    if not text:
        return []
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    remaining = text
    min_split = max(1, limit // 3)
    while len(remaining) > limit:
        split_at = -1
        for sep in ("\n\n", "\n", ". ", " "):
            pos = remaining.rfind(sep, 0, limit)
            if pos >= min_split:
                split_at = pos + (1 if sep == ". " else 0)
                break
        if split_at <= 0:
            split_at = limit
        chunk = remaining[:split_at].rstrip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[split_at:].lstrip()

    if remaining:
        chunks.append(remaining)
    return chunks


def safe_url(url: str, max_length: Optional[int] = None) -> str:
    if max_length is None:
        max_length = cfg("SAFE_URL_MAX_LENGTH")
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
                logger.warning(lmsg(
                    "utils.skip_image_too_small",
                    width=width, height=height, min_size=min_size, filepath=filepath,
                ))
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
        logger.debug(lmsg("utils.normalize_image_falhou", filepath=filepath, e=e))
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
                    logger.warning(lmsg("utils.falha_final_ao", folder=folder, e=e), exc_info=True)
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
            url, timeout=cfg("DOWNLOAD_TIMEOUT_SECONDS"), headers=headers,
        ) as response:
            ct = (response.headers.get('Content-Type') or '').lower()
            if response.status == 200:
                if ct.startswith(('text/html', 'application/json')):
                    logger.warning(lmsg("utils.skip_content_type", ct=ct, url=url))
                    return (False, ct) if return_content_type else False

                async with aiofiles.open(filepath, 'wb') as f:
                    async for chunk in response.content.iter_chunked(DOWNLOAD_CHUNK_SIZE):
                        await f.write(chunk)

                try:
                    if os.path.getsize(filepath) == 0:
                        logger.debug(lmsg("utils.download_produziu_arquivo", filepath=filepath))
                        os.remove(filepath)
                        return (False, ct) if return_content_type else False
                except OSError:
                    return (False, ct) if return_content_type else False
                return (True, ct) if return_content_type else True
            logger.warning(lmsg("utils.skip_http_x", arg0=response.status, url=url))
            return (False, ct) if return_content_type else False
    except Exception as e:
        logger.warning(lmsg("utils.erro_no_aiohttp", url=url, e=e))
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
        logger.warning(lmsg("utils.erro_pw_request", e=e))
        return False
    try:
        if resp.status != 200:
            logger.warning(lmsg("utils.skip_pw_http", arg0=resp.status, url=url))
            return False
        body = await resp.body()
        if not body:
            logger.warning(lmsg("utils.skip_pw_corpo", url=url))
            return False
        async with aiofiles.open(filepath, 'wb') as f:
            await f.write(body)
        return os.path.getsize(filepath) > 0
    except Exception as e:
        logger.warning(lmsg("utils.erro_escrevendo_pw", e=e))
        return False
    finally:
        try:
            await resp.dispose()
        except Exception:
            pass


async def async_gif_to_mp4(input_path: str, output_path: str, timeout: int = 60) -> bool:
    process = None
    ffmpeg_bin = state.FFMPEG_PATH or 'ffmpeg'
    try:
        cmd = [
            ffmpeg_bin, '-y', '-i', input_path,
            '-movflags', '+faststart',
            '-pix_fmt', 'yuv420p',
            '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2',
            '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23',
            output_path,
        ]
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        if process.returncode != 0:
            err = stderr.decode('utf-8', errors='ignore')
            logger.warning(lmsg("utils.gif_to_mp4_falhou", arg0=err[-400:]))
            return False
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except asyncio.TimeoutError:
        logger.warning(lmsg("utils.gif_to_mp4_timeout", timeout=timeout, input_path=input_path))
        if process:
            try:
                process.kill()
                await process.wait()
            except Exception:
                pass
        return False
    except Exception as e:
        logger.warning(lmsg("utils.gif_to_mp4_erro", e=e), exc_info=True)
        return False


_TG_COMPATIBLE_VIDEO_EXTS = ('.mp4', '.m4v', '.mov')
_TG_COMPATIBLE_VCODECS = ('h264', 'avc1', 'avc')
_TG_COMPATIBLE_ACODECS = ('aac',)


def is_telegram_compatible_video_ext(filepath: str) -> bool:
    return filepath.lower().endswith(_TG_COMPATIBLE_VIDEO_EXTS)


async def async_ffprobe_codecs(filepath: str, timeout: int = 30) -> tuple[Optional[str], Optional[str]]:
    ffprobe_bin = state.FFPROBE_PATH
    if not ffprobe_bin:
        return None, None
    process = None
    try:
        cmd = [
            ffprobe_bin, '-v', 'error',
            '-show_entries', 'stream=codec_type,codec_name',
            '-of', 'default=nw=1',
            filepath,
        ]
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        if process.returncode != 0:
            err = stderr.decode('utf-8', errors='ignore')
            logger.warning(lmsg("utils.ffprobe_falhou", arg0=err[-200:]))
            return None, None
        vcodec: Optional[str] = None
        acodec: str = ''
        cur_type: Optional[str] = None
        cur_name: Optional[str] = None
        for line in stdout.decode('utf-8', errors='ignore').splitlines():
            if '=' not in line:
                continue
            k, v = line.split('=', 1)
            k, v = k.strip(), v.strip().lower()
            if k == 'codec_type':
                cur_type = v
            elif k == 'codec_name':
                cur_name = v
            if cur_type and cur_name:
                if cur_type == 'video' and vcodec is None:
                    vcodec = cur_name
                elif cur_type == 'audio' and not acodec:
                    acodec = cur_name
                cur_type = cur_name = None
        return vcodec, acodec
    except asyncio.TimeoutError:
        logger.warning(lmsg("utils.ffprobe_timeout", timeout=timeout, filepath=filepath))
        if process:
            try:
                process.kill()
                await process.wait()
            except Exception:
                pass
        return None, None
    except Exception as e:
        logger.warning(lmsg("utils.ffprobe_erro", e=e))
        return None, None


async def async_ensure_telegram_video(filepath: str, timeout: int = 600) -> Optional[str]:
    if is_telegram_compatible_video_ext(filepath):
        return filepath

    if not state.FFMPEG_PATH:
        logger.warning(lmsg("utils.video_convert_no_ffmpeg", filepath=filepath))
        return None

    out_path = os.path.splitext(filepath)[0] + '.tg.mp4'
    vcodec, acodec = await async_ffprobe_codecs(filepath)

    if vcodec in _TG_COMPATIBLE_VCODECS:
        v_args = ['-c:v', 'copy']
    else:
        v_args = ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23', '-pix_fmt', 'yuv420p']

    if acodec == '':
        a_args = ['-an']
    elif acodec in _TG_COMPATIBLE_ACODECS:
        a_args = ['-c:a', 'copy']
    else:
        a_args = ['-c:a', 'aac', '-b:a', '192k']

    cmd = [state.FFMPEG_PATH, '-y', '-i', filepath, *v_args, *a_args, '-movflags', '+faststart', out_path]
    logger.info(lmsg(
        "utils.video_convert_iniciando",
        filepath=filepath, vcodec=vcodec or 'unknown', acodec=acodec or 'none',
        v_args=' '.join(v_args), a_args=' '.join(a_args),
    ))

    process = None
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        if process.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            logger.info(lmsg("utils.video_convert_ok", out_path=out_path))
            return out_path
        err = stderr.decode('utf-8', errors='ignore')
        logger.warning(lmsg("utils.video_convert_falhou", arg0=err[-400:]))
    except asyncio.TimeoutError:
        logger.warning(lmsg("utils.video_convert_timeout", timeout=timeout, filepath=filepath))
        if process:
            try:
                process.kill()
                await process.wait()
            except Exception:
                pass
    except Exception as e:
        logger.warning(lmsg("utils.video_convert_erro", e=e))

    if 'copy' in v_args:
        logger.info(lmsg("utils.video_convert_retry_reencode", filepath=filepath))
        cmd_retry = [
            state.FFMPEG_PATH, '-y', '-i', filepath,
            '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23', '-pix_fmt', 'yuv420p',
            *a_args, '-movflags', '+faststart', out_path,
        ]
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd_retry, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            if process.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                logger.info(lmsg("utils.video_convert_ok", out_path=out_path))
                return out_path
            err = stderr.decode('utf-8', errors='ignore')
            logger.warning(lmsg("utils.video_convert_falhou", arg0=err[-400:]))
        except asyncio.TimeoutError:
            logger.warning(lmsg("utils.video_convert_timeout", timeout=timeout, filepath=filepath))
            if process:
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass
        except Exception as e:
            logger.warning(lmsg("utils.video_convert_erro", e=e))

    return None


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
            logger.warning(lmsg("utils.ffmpeg_remux_falhou", arg0=err[-400:]))
            return False
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except asyncio.TimeoutError:
        logger.warning(lmsg("utils.ffmpeg_remux_timeout", timeout=timeout, input_url=input_url))
        try:
            if process:
                process.kill()
                await process.wait()
        except Exception:
            pass
        return False
    except Exception as e:
        logger.warning(lmsg("utils.erro_fatal_no", e=e), exc_info=True)
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
            logger.error(lmsg("utils.erro_ffmpeg_x", err_msg=err_msg))
            return False

        return True
    except asyncio.TimeoutError:
        logger.error(lmsg("utils.ffmpeg_travou_e"))
        try:
            if process:
                process.kill()
                await process.wait()
        except Exception:
            pass
        return False
    except Exception as e:
        logger.error(lmsg("utils.erro_fatal_no_2", e=e), exc_info=True)
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
            await asyncio.sleep(cfg("STATUS_CYCLE_INTERVAL"))
            idx = (idx + 1) % len(messages)
    except asyncio.CancelledError:
        pass
