from utils import translate_error


def test_login_required_message():
    assert "privado" in translate_error("Sign in to confirm you're not a bot")


def test_login_required_message_case_insensitive():
    assert "privado" in translate_error("LOGIN REQUIRED")


def test_video_unavailable():
    assert "indisponível" in translate_error("Video unavailable")


def test_403_forbidden():
    assert "403" in translate_error("HTTP Error 403: Forbidden")
    assert "403" in translate_error("Access Forbidden")


def test_generic_fallback():
    assert translate_error("algum erro qualquer") == "⚠️ Erro ao processar o link."


def test_accepts_exception_objects():
    err = RuntimeError("sign in para continuar")
    assert "privado" in translate_error(err)
