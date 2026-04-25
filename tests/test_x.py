import html
import json
import os

import pytest

from downloaders.x import (
    _build_caption,
    _extract_tweet_id,
    _extract_tweet_text,
    _find_in_initial_state,
    _media_from_extended_entities,
    _normalize_x_url,
    _walk_for_tweet_media,
    _walk_for_tweet_obj,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "x")


def _load_tweet(name: str) -> dict:
    with open(os.path.join(FIXTURES_DIR, f"{name}.json")) as f:
        return json.load(f)


@pytest.mark.parametrize("url,expected", [
    ("https://x.com/i/status/123", "123"),
    ("https://x.com/user/status/456", "456"),
    ("https://twitter.com/user/status/789?s=20", "789"),
    ("https://fxtwitter.com/i/status/2043260334933410139", "2043260334933410139"),
    ("https://x.com/user/status/123/photo/1", "123"),
    ("https://x.com/user", None),
    ("https://example.com/", None),
])
def test_extract_tweet_id(url, expected):
    assert _extract_tweet_id(url) == expected


@pytest.mark.parametrize("input_url,expected", [
    ("https://twitter.com/i/status/123", "https://x.com/i/status/123"),
    ("https://fxtwitter.com/u/status/456", "https://x.com/u/status/456"),
    ("https://vxtwitter.com/u/status/456", "https://x.com/u/status/456"),
    ("https://www.fxtwitter.com/u/status/456", "https://x.com/u/status/456"),
    ("https://mobile.twitter.com/u/status/456", "https://x.com/u/status/456"),
    ("https://x.com/u/status/456", "https://x.com/u/status/456"),
])
def test_normalize_x_url(input_url, expected):
    assert _normalize_x_url(input_url) == expected


def test_media_from_photo_only_uses_orig_resolution():
    tweet = _load_tweet("photo_single")
    media = tweet["extended_entities"]["media"]
    items = _media_from_extended_entities(media)
    assert len(items) == 1
    kind, url = items[0]
    assert kind == "image"
    assert "name=orig" in url
    assert url.startswith("https://pbs.twimg.com/")


def test_media_from_video_picks_highest_bitrate_mp4():
    tweet = _load_tweet("video")
    media = tweet["extended_entities"]["media"]
    items = _media_from_extended_entities(media)
    assert len(items) == 1
    kind, url = items[0]
    assert kind == "video"
    assert url.endswith(".mp4") or ".mp4?" in url
    assert "&#x3D;" not in url and "&amp;" not in url

    variants = media[0]["video_info"]["variants"]
    mp4s = [v for v in variants if (v.get("content_type") or "").startswith("video/mp4")]
    max_br = max(v.get("bitrate") or 0 for v in mp4s)
    expected_raw = next(v["url"] for v in mp4s if v.get("bitrate") == max_br)
    assert url == html.unescape(expected_raw)


def test_media_unescapes_html_entities_in_urls():
    media = [{"type": "video", "video_info": {"variants": [
        {"content_type": "video/mp4", "bitrate": 1000,
         "url": "https://video.twimg.com/x.mp4?tag&#x3D;19&amp;v&#x3D;372"},
    ]}}]
    items = _media_from_extended_entities(media)
    assert items == [("video", "https://video.twimg.com/x.mp4?tag=19&v=372")]

    media_photo = [{"type": "photo", "media_url_https": "https://pbs.twimg.com/x.jpg?foo&#x3D;1"}]
    items = _media_from_extended_entities(media_photo)
    assert items == [("image", "https://pbs.twimg.com/x.jpg?foo=1&name=orig")]


def test_media_skips_when_no_mp4_variants():
    media = [{"type": "video", "video_info": {"variants": [
        {"content_type": "application/x-mpegURL", "url": "x.m3u8"},
    ]}}]
    assert _media_from_extended_entities(media) == []


def test_media_handles_animated_gif_like_video():
    media = [{"type": "animated_gif", "video_info": {"variants": [
        {"content_type": "video/mp4", "bitrate": 0, "url": "https://video.twimg.com/x.mp4"},
    ]}}]
    items = _media_from_extended_entities(media)
    assert items == [("video", "https://video.twimg.com/x.mp4")]


def test_media_appends_query_param_correctly_when_already_has_query():
    media = [{"type": "photo", "media_url_https": "https://pbs.twimg.com/x.jpg?foo=1"}]
    items = _media_from_extended_entities(media)
    assert items == [("image", "https://pbs.twimg.com/x.jpg?foo=1&name=orig")]


def test_find_in_initial_state_returns_tweet():
    state = {"entities": {"tweets": {"entities": {"123": {"id_str": "123", "full_text": "hi"}}}}}
    found = _find_in_initial_state(state, "123")
    assert found is not None
    assert found["id_str"] == "123"


def test_find_in_initial_state_returns_none_when_absent():
    assert _find_in_initial_state({}, "999") is None
    assert _find_in_initial_state({"entities": {}}, "999") is None
    assert _find_in_initial_state({"entities": {"tweets": {"entities": {}}}}, "999") is None


def test_walk_for_tweet_media_finds_in_graphql_shape():
    graphql_response = {
        "data": {
            "threaded_conversation_with_injections_v2": {
                "instructions": [{
                    "entries": [{
                        "content": {
                            "itemContent": {
                                "tweet_results": {
                                    "result": {
                                        "rest_id": "555",
                                        "legacy": {
                                            "id_str": "555",
                                            "extended_entities": {
                                                "media": [
                                                    {"type": "photo", "media_url_https": "https://pbs.twimg.com/a.jpg"},
                                                ]
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }]
                }]
            }
        }
    }
    medias = list(_walk_for_tweet_media(graphql_response, "555"))
    assert len(medias) >= 1
    items = _media_from_extended_entities(medias[0])
    assert items == [("image", "https://pbs.twimg.com/a.jpg?name=orig")]


def test_walk_for_tweet_media_skips_unrelated_tweets():
    response = {
        "tweet_a": {"id_str": "111", "extended_entities": {"media": [{"type": "photo", "media_url_https": "u1"}]}},
        "tweet_b": {"id_str": "222", "extended_entities": {"media": [{"type": "photo", "media_url_https": "u2"}]}},
    }
    medias = list(_walk_for_tweet_media(response, "222"))
    assert len(medias) == 1
    assert medias[0][0]["media_url_https"] == "u2"


def test_full_pipeline_with_real_video_fixture():
    tweet = _load_tweet("video")
    initial_state = {"entities": {"tweets": {"entities": {"2043472628770275518": tweet}}}}
    found = _find_in_initial_state(initial_state, "2043472628770275518")
    assert found is not None
    items = _media_from_extended_entities(found["extended_entities"]["media"])
    assert len(items) == 1
    assert items[0][0] == "video"


def test_extract_tweet_text_uses_display_text_range_to_strip_trailing_url():
    tweet = _load_tweet("video")
    text = _extract_tweet_text(tweet)
    assert text.startswith("O bolo")
    assert "https://t.co/" not in text


def test_extract_tweet_text_returns_empty_for_media_only_post():
    tweet = _load_tweet("photo_single")
    assert _extract_tweet_text(tweet) == ""


def test_extract_tweet_text_handles_legacy_wrapping():
    wrapped = {"legacy": {"full_text": "hello", "display_text_range": [0, 5]}}
    assert _extract_tweet_text(wrapped) == "hello"


def test_extract_tweet_text_strips_trailing_tco_when_no_range():
    tweet = {"full_text": "Olha isso https://t.co/abc"}
    assert _extract_tweet_text(tweet) == "Olha isso"


def test_extract_tweet_text_unescapes_html_entities():
    tweet = {"full_text": "isso &amp; aquilo", "display_text_range": [0, 17]}
    assert _extract_tweet_text(tweet) == "isso & aquilo"


def test_extract_tweet_text_handles_none():
    assert _extract_tweet_text(None) == ""
    assert _extract_tweet_text({}) == ""


def test_build_caption_with_text():
    tweet = {"full_text": "Hello <world>", "display_text_range": [0, 13]}
    caption = _build_caption(tweet, "https://x.com/u/status/1")
    assert "Hello &lt;world&gt;" in caption
    assert "https://x.com/u/status/1" in caption
    assert "<a href=" in caption


def test_build_caption_without_text_just_returns_link():
    caption = _build_caption(None, "https://x.com/u/status/1")
    assert "<a href=" in caption
    assert "https://x.com/u/status/1" in caption
    assert "\n\n" not in caption


def test_build_caption_truncates_very_long_text():
    long_text = "a" * 1500
    tweet = {"full_text": long_text, "display_text_range": [0, 1500]}
    caption = _build_caption(tweet, "https://x.com/u/status/1")
    assert "..." in caption
    assert len(caption) < 1500


def test_walk_for_tweet_obj_finds_in_graphql_legacy_shape():
    response = {
        "data": {
            "result": {
                "rest_id": "999",
                "legacy": {"id_str": "999", "full_text": "found me"}
            }
        }
    }
    found = list(_walk_for_tweet_obj(response, "999"))
    assert len(found) >= 1
    assert any(t.get("full_text") == "found me" or t.get("rest_id") == "999" for t in found)
