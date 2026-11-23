import handlers


def _set(monkeypatch, enabled="yes", ms=1000):
    handlers._rate_last.clear()
    vals = {"RATE_LIMIT_ENABLED": enabled, "RATE_LIMIT_INTERVAL_MS": ms}
    monkeypatch.setattr(handlers, "cfg", lambda key, chat_id=None, user_id=None: vals[key])


def test_primeira_passa_e_dentro_da_janela_ignora(monkeypatch):
    _set(monkeypatch)
    assert handlers._rate_limited(1, 9, now=100.0) is False
    assert handlers._rate_limited(1, 9, now=100.5) is True
    assert handlers._rate_limited(1, 9, now=100.99) is True


def test_ignorada_nao_estende_a_janela(monkeypatch):
    _set(monkeypatch)
    handlers._rate_limited(1, 9, now=100.0)
    handlers._rate_limited(1, 9, now=100.9)
    assert handlers._rate_limited(1, 9, now=101.0) is False


def test_chats_independentes(monkeypatch):
    _set(monkeypatch)
    assert handlers._rate_limited(1, 9, now=100.0) is False
    assert handlers._rate_limited(2, 9, now=100.1) is False


def test_desligado_nunca_ignora(monkeypatch):
    _set(monkeypatch, enabled="no")
    assert handlers._rate_limited(1, 9, now=100.0) is False
    assert handlers._rate_limited(1, 9, now=100.0) is False


def test_intervalo_configuravel_e_zero_desliga_na_pratica(monkeypatch):
    _set(monkeypatch, ms=250)
    assert handlers._rate_limited(1, 9, now=100.0) is False
    assert handlers._rate_limited(1, 9, now=100.2) is True
    assert handlers._rate_limited(1, 9, now=100.25) is False
    _set(monkeypatch, ms=0)
    assert handlers._rate_limited(1, 9, now=200.0) is False
    assert handlers._rate_limited(1, 9, now=200.0) is False


import asyncio
from types import SimpleNamespace


def _update(chat_id=1, user_id=9):
    msg = SimpleNamespace(id=5, set_reaction=lambda **kw: asyncio.sleep(0))
    return SimpleNamespace(
        effective_chat=SimpleNamespace(id=chat_id),
        effective_user=SimpleNamespace(id=user_id),
        message=msg,
    )


def _run(monkeypatch, enabled, urls):
    _set(monkeypatch, enabled=enabled)
    chamadas = []

    async def fake_process(context, chat_id, message_id, url, **kw):
        chamadas.append(url)

    monkeypatch.setattr(handlers, "ALLOW_ALL", "yes")
    monkeypatch.setattr(handlers, "_extract_urls_from_update", lambda u: list(urls))
    monkeypatch.setattr(handlers, "msg_list", lambda k: [])
    monkeypatch.setattr(handlers, "process_media_request", fake_process)

    async def go():
        await handlers.handle_message(_update(), SimpleNamespace())
        await asyncio.gather(*list(handlers.state.background_tasks))

    asyncio.run(go())
    return chamadas


def test_so_o_primeiro_link_da_mensagem_com_rate_limit(monkeypatch):
    assert _run(monkeypatch, "yes", ["a", "b", "c"]) == ["a"]


def test_sem_rate_limit_baixa_todos(monkeypatch):
    assert _run(monkeypatch, "no", ["a", "b", "c"]) == ["a", "b", "c"]
