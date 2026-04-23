import asyncio

import state


def get_chat_lock(chat_id: int) -> asyncio.Lock:
    """Retorna o Lock do chat, criando dentro do event loop ativo.

    Armazenado em state.chat_locks (WeakValueDictionary) para que seja coletado
    pelo GC quando nenhum download estiver segurando o lock — evita leak em
    bots que conversam com muitos chats distintos.
    """
    lock = state.chat_locks.get(chat_id)
    if lock is None:
        lock = asyncio.Lock()
        state.chat_locks[chat_id] = lock
    return lock
