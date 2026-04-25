import json
import os

import pytest

from downloaders.instagram_embed import (
    _best_image_url,
    _extract_caption,
    _extract_shortcode,
    _find_shortcode_media,
    _has_unembedded_music,
    _media_from_node,
    _parse_context_json,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "instagram")


def _load(name: str) -> dict:
    with open(os.path.join(FIXTURES_DIR, f"{name}.json")) as f:
        return json.load(f)


@pytest.mark.parametrize("url,expected", [
    ("https://www.instagram.com/p/DXgdNpFkSdi/", "DXgdNpFkSdi"),
    ("https://www.instagram.com/p/DXgdNpFkSdi/embed/captioned/", "DXgdNpFkSdi"),
    ("https://www.instagram.com/reel/ABC123/", "ABC123"),
    ("https://instagram.com/reels/XYZ-_9/", "XYZ-_9"),
    ("https://www.instagram.com/tv/foobar/", "foobar"),
    ("https://www.instagram.com/p/CODE/?igsh=foo", "CODE"),
    ("https://www.instagram.com/user/", None),
    ("https://example.com/", None),
])
def test_extract_shortcode(url, expected):
    assert _extract_shortcode(url) == expected


def test_media_from_reel_returns_video():
    media = _load("reel")
    items = _media_from_node(media)
    assert len(items) == 1
    kind, url = items[0]
    assert kind == "video"
    assert ".mp4" in url
    assert url.startswith("https://")


def test_media_from_carousel_mixed_returns_all_items_in_order():
    media = _load("carousel_mixed")
    items = _media_from_node(media)
    assert len(items) == 3
    kinds = [k for k, _ in items]
    assert kinds == ["video", "image", "image"]


def test_media_picks_highest_res_display_resource():
    media = _load("carousel_mixed")
    sidecar_edges = media["edge_sidecar_to_children"]["edges"]
    photo_node = next(e["node"] for e in sidecar_edges if not e["node"].get("is_video"))

    items = _media_from_node(photo_node)
    assert len(items) == 1

    drs = photo_node["display_resources"]
    max_w = max(r.get("config_width") or 0 for r in drs)
    expected = next(r["src"] for r in drs if r.get("config_width") == max_w)
    assert items[0][1] == expected


def test_best_image_url_falls_back_to_display_url_when_no_resources():
    node = {"display_url": "https://x.cdn/photo.jpg"}
    assert _best_image_url(node) == "https://x.cdn/photo.jpg"


def test_best_image_url_prefers_resources_over_display_url():
    node = {
        "display_url": "https://x.cdn/small.jpg",
        "display_resources": [
            {"config_width": 320, "src": "https://x.cdn/m.jpg"},
            {"config_width": 1080, "src": "https://x.cdn/big.jpg"},
            {"config_width": 640, "src": "https://x.cdn/h.jpg"},
        ],
    }
    assert _best_image_url(node) == "https://x.cdn/big.jpg"


def test_extract_caption_from_real_fixture():
    media = _load("carousel_mixed")
    caption = _extract_caption(media)
    assert caption.startswith("Hell yeah")
    assert "creed" in caption.lower()


def test_extract_caption_handles_missing():
    assert _extract_caption({}) == ""
    assert _extract_caption({"edge_media_to_caption": {}}) == ""
    assert _extract_caption({"edge_media_to_caption": {"edges": []}}) == ""


def test_find_shortcode_media_in_gql_data():
    data = {"gql_data": {"shortcode_media": {"id": "1", "is_video": False}}}
    assert _find_shortcode_media(data) == {"id": "1", "is_video": False}


def test_find_shortcode_media_falls_back_to_context():
    data = {"context": {"media": {"id": "2"}}}
    assert _find_shortcode_media(data) == {"id": "2"}


def test_find_shortcode_media_returns_none_when_absent():
    assert _find_shortcode_media({}) is None
    assert _find_shortcode_media({"gql_data": {}}) is None


def test_media_from_empty_node_returns_empty():
    assert _media_from_node({}) == []
    assert _media_from_node({"display_url": None}) == []


def test_parse_context_json_extracts_nested_json():
    payload = {"a": 1, "b": "hello"}
    inner_str = json.dumps(payload)
    embedded = json.dumps(inner_str)
    html = 'before {"contextJSON":' + embedded + ',"other":"x"} after'
    parsed = _parse_context_json(html)
    assert parsed == payload


def test_parse_context_json_returns_none_when_absent():
    assert _parse_context_json("nothing here") is None
    assert _parse_context_json('"contextJSON":"not_valid_json"') is None


def test_has_unembedded_music_skips_photo_with_music_attribution():
    media = {
        "is_video": False,
        "__typename": "GraphImage",
        "clips_music_attribution_info": {"artist_name": "X", "song_name": "Y"},
    }
    assert _has_unembedded_music(media) is True


def test_has_unembedded_music_returns_false_for_video_with_music():
    media = _load("reel")
    assert media["is_video"] is True
    assert media.get("clips_music_attribution_info") is not None
    assert _has_unembedded_music(media) is False


def test_has_unembedded_music_returns_false_for_carousel_without_music():
    media = _load("carousel_mixed")
    assert _has_unembedded_music(media) is False


def test_has_unembedded_music_returns_false_for_plain_photo():
    media = {"is_video": False, "clips_music_attribution_info": None}
    assert _has_unembedded_music(media) is False


def test_has_unembedded_music_handles_empty_dict_attribution():
    media = {"is_video": False, "clips_music_attribution_info": {}}
    assert _has_unembedded_music(media) is False


def test_caption_format_has_title_text_and_link():
    from downloaders._caption import _build_caption
    media = _load("carousel_mixed")
    raw = _extract_caption(media)
    username = media["owner"]["username"]
    info = {"title": f"@{username}", "description": raw}
    caption, _ = _build_caption(info, "https://www.instagram.com/p/DXb_4eviZ7J/")
    assert "@" in caption
    assert "<b>" in caption and "</b>" in caption
    assert "<a href=" in caption
    assert "https://www.instagram.com/p/DXb_4eviZ7J/" in caption
    assert "Hell yeah" in caption


def test_caption_includes_link_when_only_username_known():
    from downloaders._caption import _build_caption
    info = {"title": "@someuser", "description": ""}
    caption, _ = _build_caption(info, "https://www.instagram.com/p/X/")
    assert "@someuser" in caption
    assert "<a href=" in caption
