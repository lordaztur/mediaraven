"""Mensagens user-facing do bot, carregadas de messages.json (fallback: messages.example.json)."""
import json
import os
from typing import Any

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_USER_FILE = os.path.join(_BASE_DIR, "messages.json")
_EXAMPLE_FILE = os.path.join(_BASE_DIR, "messages.example.json")
_LOG_USER_FILE = os.path.join(_BASE_DIR, "log_messages.json")
_LOG_EXAMPLE_FILE = os.path.join(_BASE_DIR, "log_messages.example.json")


def _load(path: str) -> dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


_MESSAGES: dict[str, Any] = _load(_USER_FILE)
# Chave nova que o messages.json do usuário ainda não tem cai no texto do exemplo,
# em vez de derrubar o download com KeyError depois de uma atualização.
_EXAMPLE_MESSAGES: dict[str, Any] = _load(_EXAMPLE_FILE)


def _lookup(tree: dict[str, Any], parts: list[str]) -> Any:
    node: Any = tree
    for p in parts:
        node = node[p]
    return node


def _resolve(key: str) -> Any:
    parts = key.split(".")
    for tree in (_MESSAGES, _EXAMPLE_MESSAGES):
        try:
            return _lookup(tree, parts)
        except (KeyError, TypeError):
            continue
    raise KeyError(f"messages key not found: {key!r}")


def msg(key: str, **kwargs) -> str:
    node = _resolve(key)
    if kwargs:
        return node.format(**kwargs)
    return node


def msg_list(key: str) -> list:
    return list(_resolve(key))


def _load_log() -> dict[str, Any]:
    path = _LOG_USER_FILE if os.path.exists(_LOG_USER_FILE) else _LOG_EXAMPLE_FILE
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


_LOG_MESSAGES: dict[str, Any] = _load_log()


def lmsg(key: str, **kwargs) -> str:
    parts = key.split(".")
    node: Any = _LOG_MESSAGES
    for p in parts:
        try:
            node = node[p]
        except (KeyError, TypeError):
            return f"<<missing log key: {key}>>"
    if not isinstance(node, str):
        return f"<<invalid log key: {key}>>"
    if kwargs:
        try:
            return node.format(**kwargs)
        except (KeyError, IndexError) as e:
            return f"{node} <<format error: {e}>>"
    return node
