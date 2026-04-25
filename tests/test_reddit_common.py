"""Testes dos helpers compartilhados entre os extratores de Reddit."""
from downloaders.reddit_common import (
    build_reddit_caption,
    clean_reddit_media_url,
    is_reddit_media_url,
    looks_like_image,
)


def test_clean_unescapes_entities():
    raw = "https://preview.redd.it/x.jpg?amp;width=640&amp;crop=smart"
    out = clean_reddit_media_url(raw)
    assert out == "https://i.redd.it/x.jpg"


def test_clean_replaces_preview_with_i():
    raw = "https://preview.redd.it/abc.jpg"
    assert clean_reddit_media_url(raw) == "https://i.redd.it/abc.jpg"


def test_clean_strips_query():
    raw = "https://i.redd.it/abc.png?foo=1"
    assert clean_reddit_media_url(raw) == "https://i.redd.it/abc.png"


def test_clean_returns_none_for_falsy():
    assert clean_reddit_media_url("") is None
    assert clean_reddit_media_url(None) is None


def test_is_reddit_media_accepts_redd_it():
    assert is_reddit_media_url("https://i.redd.it/abc.jpg") is True
    assert is_reddit_media_url("https://preview.redd.it/xyz.png") is True


def test_is_reddit_media_rejects_junk():
    assert is_reddit_media_url("https://i.redd.it/snoovatar/xyz.png") is False
    assert is_reddit_media_url("https://i.redd.it/award_images/foo.png") is False
    assert is_reddit_media_url("https://i.redd.it/icon/xyz.png") is False


def test_is_reddit_media_rejects_other_hosts():
    assert is_reddit_media_url("https://example.com/x.jpg") is False
    assert is_reddit_media_url("") is False


def test_looks_like_image_detects_extensions():
    assert looks_like_image("https://x.com/a.jpg") is True
    assert looks_like_image("https://x.com/a.PNG") is True
    assert looks_like_image("https://x.com/a.webp?foo=1") is True
    assert looks_like_image("https://x.com/a.gif?x") is True
    assert looks_like_image("https://x.com/page") is False
    assert looks_like_image("") is False


def test_build_reddit_caption_with_title_and_selftext():
    caption = build_reddit_caption(
        "Cute puppy playing",
        "Found this little guy in my yard today.",
        "https://reddit.com/r/aww/comments/x/",
    )
    assert "Cute puppy playing" in caption
    assert "Found this little guy" in caption
    assert "<b>" in caption
    assert "<a href=" in caption


def test_build_reddit_caption_only_title():
    caption = build_reddit_caption("Just a photo", "", "https://reddit.com/r/pics/comments/x/")
    assert "Just a photo" in caption
    assert "<a href=" in caption


def test_build_reddit_caption_empty_returns_empty_string():
    caption = build_reddit_caption("", "", "https://reddit.com/r/x/comments/y/")
    assert caption == ""


def test_build_reddit_caption_html_escapes_specials():
    caption = build_reddit_caption("Title <with> & stuff", "body & <stuff>", "https://reddit.com/r/x/comments/y/")
    assert "&lt;" in caption
    assert "&amp;" in caption
    assert "<with>" not in caption
