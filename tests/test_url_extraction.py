"""Testa a extração de URLs do update. Cobre os ramos do _extract_urls_from_update."""
from dataclasses import dataclass
from typing import Optional

import pytest

import config
from handlers import _extract_urls_from_update


@dataclass(eq=False)
class FakeEntity:
    type: str
    url: Optional[str] = None


@dataclass
class FakeMessage:
    text: Optional[str] = None
    caption: Optional[str] = None
    _entities: dict = None
    _caption_entities: dict = None

    def parse_entities(self, types):
        return {e: text for e, text in (self._entities or {}).items() if e.type in types}

    def parse_caption_entities(self, types):
        return {e: text for e, text in (self._caption_entities or {}).items() if e.type in types}


@dataclass
class FakeUpdate:
    message: Optional[FakeMessage] = None


def test_no_message_returns_empty():
    assert _extract_urls_from_update(FakeUpdate(message=None)) == []


def test_plain_url_without_scheme_gets_https():
    entity = FakeEntity(type='url')
    msg = FakeMessage(text="veja isto: example.com/foo", _entities={entity: "example.com/foo"})
    assert _extract_urls_from_update(FakeUpdate(message=msg)) == ["https://example.com/foo"]


def test_plain_url_keeps_existing_scheme():
    entity = FakeEntity(type='url')
    msg = FakeMessage(text="http://site.local", _entities={entity: "http://site.local"})
    assert _extract_urls_from_update(FakeUpdate(message=msg)) == ["http://site.local"]


def test_mention_starting_with_at_is_skipped():
    entity = FakeEntity(type='url')
    msg = FakeMessage(text="@usuario foo", _entities={entity: "@usuario"})
    assert _extract_urls_from_update(FakeUpdate(message=msg)) == []


def test_text_link_uses_embedded_url():
    entity = FakeEntity(type='text_link', url="https://hidden.example/path")
    msg = FakeMessage(text="clique aqui", _entities={entity: "aqui"})
    assert _extract_urls_from_update(FakeUpdate(message=msg)) == ["https://hidden.example/path"]


def test_duplicates_are_removed_preserving_order():
    e1 = FakeEntity(type='url')
    e2 = FakeEntity(type='url')
    e3 = FakeEntity(type='url')
    msg = FakeMessage(
        text="https://a.com https://b.com https://a.com",
        _entities={
            e1: "https://a.com",
            e2: "https://b.com",
            e3: "https://a.com",
        },
    )
    assert _extract_urls_from_update(FakeUpdate(message=msg)) == [
        "https://a.com",
        "https://b.com",
    ]


def test_falls_back_to_caption_when_no_text():
    entity = FakeEntity(type='url')
    msg = FakeMessage(
        text=None,
        caption="https://captioned.example",
        _caption_entities={entity: "https://captioned.example"},
    )
    assert _extract_urls_from_update(FakeUpdate(message=msg)) == ["https://captioned.example"]


@pytest.fixture
def set_ignored_domains(monkeypatch):
    def _apply(domains):
        monkeypatch.setitem(config._CUSTOMIZATION["default"], "IGNORED_DOMAINS", domains)
    return _apply


def test_ignored_domain_is_dropped_silently(set_ignored_domains):
    set_ignored_domains(["twitch.tv"])
    e1 = FakeEntity(type='url')
    e2 = FakeEntity(type='url')
    msg = FakeMessage(
        text="https://twitch.tv/live https://youtube.com/watch?v=1",
        _entities={e1: "https://twitch.tv/live", e2: "https://youtube.com/watch?v=1"},
    )
    assert _extract_urls_from_update(FakeUpdate(message=msg)) == [
        "https://youtube.com/watch?v=1",
    ]


def test_ignored_domain_matches_subdomain(set_ignored_domains):
    set_ignored_domains(["twitch.tv"])
    entity = FakeEntity(type='url')
    msg = FakeMessage(text="https://www.twitch.tv/x", _entities={entity: "https://www.twitch.tv/x"})
    assert _extract_urls_from_update(FakeUpdate(message=msg)) == []


def test_all_urls_ignored_returns_empty(set_ignored_domains):
    set_ignored_domains(["twitch.tv", "spotify.com"])
    e1 = FakeEntity(type='url')
    e2 = FakeEntity(type='text_link', url="https://open.spotify.com/track/abc")
    msg = FakeMessage(
        text="https://twitch.tv/a link",
        _entities={e1: "https://twitch.tv/a", e2: "link"},
    )
    assert _extract_urls_from_update(FakeUpdate(message=msg)) == []


def test_empty_ignore_list_processes_everything(set_ignored_domains):
    set_ignored_domains([])
    entity = FakeEntity(type='url')
    msg = FakeMessage(text="https://twitch.tv/x", _entities={entity: "https://twitch.tv/x"})
    assert _extract_urls_from_update(FakeUpdate(message=msg)) == ["https://twitch.tv/x"]
