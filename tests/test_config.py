"""Testes de config: parsing resiliente e validação."""
from unittest.mock import patch

import config


def test_csv_ints_ignores_garbage():
    assert config._csv_ints("1, 2, abc, 3", "TEST") == [1, 2, 3]


def test_csv_ints_empty_string():
    assert config._csv_ints("", "TEST") == []


def test_csv_ints_only_spaces():
    assert config._csv_ints("  ,  , ", "TEST") == []


def test_env_int_uses_default_on_garbage(monkeypatch):
    monkeypatch.setenv("NON_INT_TEST_VAR", "hello")
    assert config._env_int("NON_INT_TEST_VAR", 42) == 42


def test_env_int_parses_valid(monkeypatch):
    monkeypatch.setenv("INT_TEST_VAR", "123")
    assert config._env_int("INT_TEST_VAR", 0) == 123


def test_env_int_uses_default_when_unset(monkeypatch):
    monkeypatch.delenv("UNSET_TEST_VAR", raising=False)
    assert config._env_int("UNSET_TEST_VAR", 7) == 7


def test_validate_runtime_config_catches_empty_base_dir():
    with patch.object(config, "BASE_DOWNLOAD_DIR", ""), \
         patch.object(config, "LOCAL_API_HOST", "x"):
        errors = config.validate_runtime_config()
        assert any("BASE_DOWNLOAD_DIR" in e for e in errors)


def test_validate_runtime_config_catches_relative_base_dir():
    with patch.object(config, "BASE_DOWNLOAD_DIR", "./downloads"), \
         patch.object(config, "LOCAL_API_HOST", "x"):
        errors = config.validate_runtime_config()
        assert any("absoluto" in e for e in errors)


def test_validate_runtime_config_catches_empty_api_host(tmp_path):
    with patch.object(config, "BASE_DOWNLOAD_DIR", str(tmp_path)), \
         patch.object(config, "LOCAL_API_HOST", ""):
        errors = config.validate_runtime_config()
        assert any("LOCAL_API_HOST" in e for e in errors)


def test_validate_runtime_config_ok(tmp_path):
    with patch.object(config, "BASE_DOWNLOAD_DIR", str(tmp_path)), \
         patch.object(config, "LOCAL_API_HOST", "127.0.0.1:8081"):
        assert config.validate_runtime_config() == []


def test_should_show_prompt_default_true():
    assert config.should_show_prompt("download", 1, 1) is True
    assert config.should_show_prompt("caption", 1, 1) is True
    assert config.should_show_prompt("lang", 1, 1) is True


def test_should_show_prompt_chat_off():
    with patch.dict(config._PROMPT_OFF_CHATS, {"download": {123}}):
        assert config.should_show_prompt("download", 123, 99) is False
        assert config.should_show_prompt("download", 456, 99) is True


def test_should_show_prompt_user_on_overrides_chat_off():
    with patch.dict(config._PROMPT_OFF_CHATS, {"download": {123}}), \
         patch.dict(config._PROMPT_ON_USERS, {"download": {99}}):
        assert config.should_show_prompt("download", 123, 99) is True
        assert config.should_show_prompt("download", 123, 42) is False


def test_should_show_prompt_user_off_overrides_everything():
    with patch.dict(config._PROMPT_OFF_CHATS, {"download": set()}), \
         patch.dict(config._PROMPT_ON_USERS, {"download": {99}}), \
         patch.dict(config._PROMPT_OFF_USERS, {"download": {99}}):
        assert config.should_show_prompt("download", 1, 99) is False


def test_should_show_prompt_unknown_kind_defaults_true():
    assert config.should_show_prompt("does-not-exist", 1, 1) is True
