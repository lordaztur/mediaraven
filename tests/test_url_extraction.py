"""Testa a extração de URLs do update. Cobre os ramos do _extract_urls_from_update."""
from dataclasses import dataclass
from typing import Optional

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
