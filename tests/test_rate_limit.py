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
