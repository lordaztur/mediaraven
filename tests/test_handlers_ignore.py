"""Ignorar o download (botão "não"): link único troca a reação da mensagem e apaga a
pergunta, sem mandar texto. Com vários links, ou se o chat recusar a reação, o texto volta."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import handlers
from messages import msg


def _context(react_ok=True):
    ctx = MagicMock()
    ctx.bot.set_message_reaction = AsyncMock(
        return_value=True if react_ok else None,
        side_effect=None if react_ok else RuntimeError("REACTION_INVALID"),
    )
    return ctx


async def _ignorar(ctx, total):
    status_msg = MagicMock()
    status_msg.edit_text = AsyncMock()
    status_msg.delete = AsyncMock()
    with patch.object(handlers, "should_show_prompt", return_value=True), \
         patch.object(handlers, "_ask_yes_no", new=AsyncMock(return_value=("no", status_msg))):
        result = await handlers._initial_status_message(
            ctx, chat_id=1, message_id=99, suffix="", user_id=7, idx=1, skip_confirm=False, total=total,
        )
    return result, status_msg


@pytest.mark.asyncio
async def test_link_unico_reage_e_apaga_a_pergunta():
    ctx = _context()
    result, status_msg = await _ignorar(ctx, total=1)

    assert result is None
    ctx.bot.set_message_reaction.assert_awaited_once_with(1, 99, reaction=msg("reaction_ignored"))
    status_msg.delete.assert_awaited_once()
    status_msg.edit_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_varios_links_mantem_o_texto():
    ctx = _context()
    result, status_msg = await _ignorar(ctx, total=2)

    assert result is None
    ctx.bot.set_message_reaction.assert_not_awaited()
    status_msg.edit_text.assert_awaited_once()
    status_msg.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_reacao_recusada_cai_no_texto():
    ctx = _context(react_ok=False)
    result, status_msg = await _ignorar(ctx, total=1)

    assert result is None
    status_msg.edit_text.assert_awaited_once()
    status_msg.delete.assert_not_awaited()
