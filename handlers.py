import asyncio
import logging
import os
import random
from typing import Any, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import state
from config import (
    cfg,
    ALLOW_ALL,
    ALLOWED_CHAT_ID,
    ALLOWED_USER_ID,
    BASE_DOWNLOAD_DIR,
    request_context,
    should_show_prompt,
)
from downloaders.dispatcher import download_media
from downloaders.fallback import take_page_screenshot
from lifecycle import get_chat_lock
from messages import lmsg, msg, msg_list
from telegram_io import send_downloaded_media
from utils import cycle_status_message, safe_cleanup, safe_url

logger = logging.getLogger(__name__)


async def _resolve_future_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    store_key: str,
    expired_msg: str,
    wrong_user_msg: str,
) -> None:
    query = update.callback_query
    _, req_key, value = query.data.split('|')

    data = context.bot_data.get(store_key, {}).get(req_key)
    if not data:
        await query.answer(expired_msg, show_alert=True)
        return

    if query.from_user.id != data['user_id']:
        await query.answer(wrong_user_msg, show_alert=True)
        return

    future = data['future']
    if not future.done():
        future.set_result(value)
    await query.answer()


async def download_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _resolve_future_callback(
        update, context, 'dl_futures',
        msg("callback_alerts.dl_expired"),
        msg("callback_alerts.dl_wrong_user"),
    )


async def lang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _resolve_future_callback(
        update, context, 'lang_futures',
        msg("callback_alerts.lang_expired"),
        msg("callback_alerts.lang_wrong_user"),
    )


async def caption_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _resolve_future_callback(
        update, context, 'caption_futures',
        msg("callback_alerts.caption_expired"),
        msg("callback_alerts.caption_wrong_user"),
    )


async def screenshot_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _resolve_future_callback(
        update, context, 'screenshot_futures',
        msg("callback_alerts.screenshot_expired"),
        msg("callback_alerts.screenshot_wrong_user"),
    )


async def retry_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    retry_id = query.data

    if retry_id not in context.bot_data.get('retries', {}):
        await query.answer(msg("callback_alerts.retry_expired"), show_alert=True)
        await query.edit_message_text(msg("callback_alerts.retry_expired"))
        return

    retry_data = context.bot_data['retries'][retry_id]

    if query.from_user.id != retry_data.get('user_id'):
        await query.answer(msg("callback_alerts.retry_wrong_user"), show_alert=True)
        return

    context.bot_data['retries'].pop(retry_id)
    await query.answer()
    await query.message.delete()
    request_context.set((query.message.chat_id, retry_data['user_id']))
    await process_media_request(
        context, query.message.chat_id, retry_data['msg_id'], retry_data['url'],
        target_lang=retry_data.get('target_lang'),
        user_id=retry_data['user_id'], is_retry=True,
    )


async def _ask_via_future(
    context: ContextTypes.DEFAULT_TYPE,
    store_key: str,
    req_key: str,
    markup: InlineKeyboardMarkup,
    user_id: Optional[int],
    timeout: float,
    default: str,
) -> str:
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    context.bot_data.setdefault(store_key, {})[req_key] = {'future': future, 'user_id': user_id}
    try:
        return await asyncio.wait_for(future, timeout=timeout)
    except asyncio.TimeoutError:
        return default
    finally:
        context.bot_data[store_key].pop(req_key, None)


def _yes_no_markup(prefix: str, req_key: str, yes_label: str, no_label: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(yes_label, callback_data=f"{prefix}|{req_key}|yes"),
        InlineKeyboardButton(no_label, callback_data=f"{prefix}|{req_key}|no"),
    ]])


async def _ask_download_confirmation(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: int,
    suffix: str,
    user_id: Optional[int],
    idx: int,
) -> tuple[str, Any]:
    req_key = f"dl_{message_id}_{idx}"
    markup = _yes_no_markup(
        "dl", req_key,
        msg("buttons.download_yes"), msg("buttons.download_no"),
    )
    status_msg = await context.bot.send_message(
        chat_id,
        msg("prompts.link_detected", suffix=suffix),
        parse_mode='HTML',
        reply_markup=markup,
        reply_to_message_id=message_id,
        disable_web_page_preview=True,
    )
    choice = await _ask_via_future(
        context, 'dl_futures', req_key, markup, user_id,
        timeout=cfg("ASK_DL_TIMEOUT"), default=cfg("ASK_DL_DEFAULT"),
    )
    return choice, status_msg


async def _ask_language_choice(
    context: ContextTypes.DEFAULT_TYPE,
    status_msg: Any,
    message_id: int,
    lang_buttons: list,
    suffix: str,
    user_id: Optional[int],
    idx: int,
) -> str:
    req_key = f"{message_id}_{idx}"
    buttons = [
        InlineKeyboardButton(label, callback_data=f"lang|{req_key}|{code}")
        for code, label in lang_buttons
    ]
    keyboard = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    markup = InlineKeyboardMarkup(keyboard)
    await status_msg.edit_text(
        msg("prompts.language_detected", suffix=suffix),
        parse_mode='HTML',
        reply_markup=markup,
    )
    return await _ask_via_future(
        context, 'lang_futures', req_key, markup, user_id,
        timeout=cfg("ASK_LANG_TIMEOUT"), default='original',
    )


async def _ask_caption_inclusion(
    context: ContextTypes.DEFAULT_TYPE,
    status_msg: Any,
    message_id: int,
    suffix: str,
    user_id: Optional[int],
    idx: int,
    timeout: Optional[float] = None,
    default: Optional[str] = None,
) -> bool:
    if timeout is None:
        timeout = cfg("ASK_CAPTION_TIMEOUT")
    if default is None:
        default = cfg("ASK_CAPTION_DEFAULT")
    req_key = f"cap_{message_id}_{idx}"
    markup = _yes_no_markup(
        "cap", req_key,
        msg("buttons.caption_yes"), msg("buttons.caption_no"),
    )
    await status_msg.edit_text(
        msg("prompts.caption_found", suffix=suffix),
        parse_mode='HTML',
        reply_markup=markup,
    )
    choice = await _ask_via_future(
        context, 'caption_futures', req_key, markup, user_id,
        timeout=timeout, default=default,
    )
    return choice == 'yes'


async def _ask_screenshot_offer(
    context: ContextTypes.DEFAULT_TYPE,
    status_msg: Any,
    message_id: int,
    suffix: str,
    user_id: Optional[int],
    idx: int,
) -> bool:
    req_key = f"scrn_{message_id}_{idx}"
    markup = _yes_no_markup(
        "scrn", req_key,
        msg("buttons.screenshot_yes"), msg("buttons.screenshot_no"),
    )
    await status_msg.edit_text(
        msg("prompts.screenshot_offer", suffix=suffix),
        parse_mode='HTML',
        reply_markup=markup,
    )
    choice = await _ask_via_future(
        context, 'screenshot_futures', req_key, markup, user_id,
        timeout=cfg("ASK_SCREENSHOT_TIMEOUT"), default=cfg("ASK_SCREENSHOT_DEFAULT"),
    )
    return choice == 'yes'


async def _try_screenshot_offer(
    context: ContextTypes.DEFAULT_TYPE,
    status_msg: Any,
    message_id: int,
    suffix: str,
    user_id: Optional[int],
    idx: int,
    unique_folder: Optional[str],
    url: str,
    is_retry: bool,
) -> list:
    if is_retry or cfg("SCRAPE_SCREENSHOT_FALLBACK") != "yes" or unique_folder is None:
        return []
    try:
        wants = await _ask_screenshot_offer(context, status_msg, message_id, suffix, user_id, idx)
    except Exception as e:
        logger.debug(lmsg("handlers.falha_no_prompt", e=e))
        return []
    if not wants:
        return []
    await _safe_edit(status_msg, msg("status.screenshot_taking", suffix=suffix), parse_mode='HTML')
    shot = await take_page_screenshot(os.path.join(unique_folder, "content"), url)
    if shot:
        return [shot]
    logger.warning(lmsg("handlers.screenshot_falhou_para", url=url))
    return []


async def _acquire_chat_lock(status_msg: Any, chat_id: int, suffix: str) -> asyncio.Lock:
    lock = get_chat_lock(chat_id)
    if lock.locked():
        try:
            await status_msg.edit_text(msg("status.queue_busy", suffix=suffix))
        except Exception as e:
            logger.debug(lmsg("handlers.falha_ao_atualizar", e=e))
    await lock.acquire()
    return lock


async def _safe_edit(status_msg: Any, text: str, **kwargs) -> None:
    try:
        await status_msg.edit_text(text, **kwargs)
    except Exception as e:
        logger.debug(lmsg("handlers.falha_silenciosa_em", e=e))


async def _safe_delete(status_msg: Any) -> None:
    try:
        await status_msg.delete()
    except Exception as e:
        logger.debug(lmsg("handlers.falha_silenciosa_em_2", e=e))


def _build_suffix(idx: int, total: int, target_lang: Optional[str]) -> str:
    suffix = f" (Link {idx}/{total})" if total > 1 else ""
    if target_lang:
        suffix += f" [Idioma: {target_lang.upper()}]"
    return suffix


async def _initial_status_message(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: int,
    suffix: str,
    user_id: Optional[int],
    idx: int,
    skip_confirm: bool,
) -> Optional[Any]:
    prompt_enabled = should_show_prompt("download", chat_id, user_id or 0)
    if skip_confirm or not prompt_enabled:
        return await context.bot.send_message(
            chat_id,
            msg("status.queue_busy", suffix=suffix),
            reply_to_message_id=message_id,
        )

    choice, status_msg = await _ask_download_confirmation(
        context, chat_id, message_id, suffix, user_id, idx
    )
    if choice == 'no':
        await _safe_edit(status_msg, msg("status.download_ignored", suffix=suffix))
        return None
    await _safe_edit(status_msg, msg("status.queue_busy", suffix=suffix))
    return status_msg


async def _register_retry_and_prompt(
    context: ContextTypes.DEFAULT_TYPE,
    status_msg: Any,
    message_id: int,
    idx: int,
    url: str,
    user_id: Optional[int],
    target_lang: Optional[str],
    suffix: str,
) -> None:
    retry_id = f"retry_{message_id}_{idx}"
    context.bot_data['retries'][retry_id] = {
        'url': url, 'msg_id': message_id, 'user_id': user_id,
        'target_lang': target_lang,
    }
    markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton(msg("buttons.retry"), callback_data=retry_id)]]
    )
    text = f"{msg('downloader_status.generic_fail')}{suffix}"
    await _safe_edit(status_msg, text, parse_mode='HTML', reply_markup=markup)


async def _send_files_and_cleanup_status(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: int,
    status_msg: Any,
    files: list,
    desc_text: str,
    suffix: str,
    user_id: Optional[int],
    idx: int,
    is_article: bool = False,
) -> None:
    caption_to_send = None
    if desc_text:
        timeout = cfg("ASK_ARTICLE_TIMEOUT") if is_article else cfg("ASK_CAPTION_TIMEOUT")
        default = cfg("ASK_ARTICLE_DEFAULT") if is_article else cfg("ASK_CAPTION_DEFAULT")
        if should_show_prompt("caption", chat_id, user_id or 0):
            if await _ask_caption_inclusion(
                context, status_msg, message_id, suffix, user_id, idx,
                timeout=timeout, default=default,
            ):
                caption_to_send = desc_text
        elif default == 'yes':
            caption_to_send = desc_text

    await _safe_edit(status_msg, msg("status.sending", count=len(files), suffix=suffix))

    upload_kwargs = {
        'read_timeout': cfg("TELEGRAM_UPLOAD_TIMEOUT"),
        'write_timeout': cfg("TELEGRAM_UPLOAD_TIMEOUT"),
        'parse_mode': 'HTML',
        'reply_to_message_id': message_id,
    }
    await send_downloaded_media(
        context, chat_id, files, message_id, upload_kwargs, caption=caption_to_send
    )
    await _safe_delete(status_msg)


async def process_media_request(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: int,
    url: str,
    target_lang: Optional[str] = None,
    request_id: Optional[str] = None,
    idx: int = 1,
    total: int = 1,
    user_id: Optional[int] = None,
    is_retry: bool = False,
) -> None:
    request_context.set((chat_id, user_id))
    suffix = _build_suffix(idx, total, target_lang)

    skip_confirm = is_retry or bool(target_lang)
    status_msg = await _initial_status_message(
        context, chat_id, message_id, suffix, user_id, idx, skip_confirm,
    )
    if status_msg is None:
        return

    status_task: Optional[asyncio.Task] = None
    unique_folder: Optional[str] = None
    lock = await _acquire_chat_lock(status_msg, chat_id, suffix)
    lock_acquired = True

    try:
        await _safe_edit(status_msg, msg("status.downloading", suffix=suffix), parse_mode='HTML')
        status_task = asyncio.create_task(cycle_status_message(status_msg, suffix))

        unique_folder = os.path.join(BASE_DOWNLOAD_DIR, f"task_{chat_id}_{message_id}_{idx}")
        link_folder = os.path.join(unique_folder, "content")

        detect_lang = should_show_prompt("lang", chat_id, user_id or 0)
        files, status_or_error, desc_text, is_article = await download_media(
            url, link_folder, target_lang, detect_languages=detect_lang,
        )

        if status_task is not None:
            status_task.cancel()
            status_task = None

        if status_or_error == "MULTILANG":
            lock.release()
            lock_acquired = False

            chosen_lang = await _ask_language_choice(
                context, status_msg, message_id, files, suffix, user_id, idx
            )
            await _safe_delete(status_msg)

            return await process_media_request(
                context, chat_id, message_id, url,
                target_lang=chosen_lang,
                request_id=request_id, idx=idx, total=total,
                user_id=user_id, is_retry=is_retry,
            )

        if status_or_error:
            outcome = "✅" if files else "❌"
            logger.info(lmsg("handlers.x_x_x", outcome=outcome, status_or_error=status_or_error, arg0=safe_url(url)))

        if not files and desc_text:
            await context.bot.send_message(
                chat_id=chat_id,
                text=desc_text,
                parse_mode='HTML',
                reply_to_message_id=message_id,
                disable_web_page_preview=False,
            )
            await _safe_delete(status_msg)
            return

        if not files:
            shot_files = await _try_screenshot_offer(
                context, status_msg, message_id, suffix, user_id, idx,
                unique_folder, url, is_retry,
            )
            if shot_files:
                files = shot_files
            else:
                if is_retry:
                    await _safe_edit(
                        status_msg,
                        msg("status.retry_failed", suffix=suffix),
                        parse_mode='HTML',
                    )
                else:
                    await _register_retry_and_prompt(
                        context, status_msg, message_id, idx, url, user_id, target_lang,
                        suffix,
                    )
                return

        await _send_files_and_cleanup_status(
            context, chat_id, message_id, status_msg, files, desc_text, suffix, user_id, idx,
            is_article=is_article,
        )

    except Exception:
        logger.exception("⚠️ Erro ao processar link")
        await _safe_edit(status_msg, msg("status.internal_error", suffix=suffix))

    finally:
        if status_task is not None:
            status_task.cancel()
        if unique_folder is not None:
            await safe_cleanup(unique_folder)
        if lock_acquired:
            lock.release()


def _extract_urls_from_update(update: Update) -> list[str]:
    if not update.message:
        return []

    if update.message.text:
        entities = update.message.parse_entities(types=['url', 'text_link'])
    elif update.message.caption:
        entities = update.message.parse_caption_entities(types=['url', 'text_link'])
    else:
        entities = {}

    urls: list[str] = []
    for entity, extracted_text in entities.items():
        if entity.type == 'text_link':
            candidate = entity.url
        elif entity.type == 'url':
            if extracted_text.startswith('@'):
                continue
            candidate = extracted_text
            if not candidate.startswith(('http://', 'https://')):
                candidate = f"https://{candidate}"
        else:
            continue

        if not candidate or not candidate.lower().startswith(('http://', 'https://')):
            continue
        urls.append(candidate)

    deduped = list(dict.fromkeys(urls))
    if len(deduped) > cfg("MAX_URLS_PER_MESSAGE"):
        logger.warning(lmsg(
            "handlers.urls_exceed_limit",
            n=len(deduped), max=cfg("MAX_URLS_PER_MESSAGE"),
        ))
        return deduped[:cfg("MAX_URLS_PER_MESSAGE")]
    return deduped


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id if update.effective_user else 0
    request_context.set((chat_id, user_id))

    is_allowed_user = user_id in ALLOWED_USER_ID
    is_whitelisted_chat = chat_id in ALLOWED_CHAT_ID
    if not (ALLOW_ALL == "yes" or is_allowed_user or is_whitelisted_chat):
        return

    urls = _extract_urls_from_update(update)
    if not urls:
        return

    if is_allowed_user and not is_whitelisted_chat:
        logger.info(lmsg(
            "handlers.allowed_user_outside_whitelist",
            user_id=user_id, chat_id=chat_id, n=len(urls),
        ))

    try:
        reactions = msg_list("reactions")
        if reactions:
            await update.message.set_reaction(reaction=random.choice(reactions))
    except Exception as e:
        logger.debug(lmsg("handlers.falha_ao_setar", e=e))

    total_urls = len(urls)
    for idx, url in enumerate(urls, start=1):
        task = asyncio.create_task(
            process_media_request(
                context, chat_id, update.message.id, url,
                user_id=user_id, idx=idx, total=total_urls,
            )
        )
        state.background_tasks.add(task)
        task.add_done_callback(state.background_tasks.discard)
