from downloaders.facebook import facebook_owner_mismatch


def test_facebook_owner_mismatch_returns_false_when_no_info():
    assert facebook_owner_mismatch("https://www.facebook.com/123/posts/456/", None) is False
    assert facebook_owner_mismatch("https://www.facebook.com/123/posts/456/", {}) is False


def test_facebook_owner_mismatch_detects_mismatch():
    url = "https://www.facebook.com/1835413968/posts/10226577231697088/"
    info = {"uploader_id": "100057316996511", "uploader": "COD3R"}
    assert facebook_owner_mismatch(url, info) is True


def test_facebook_owner_mismatch_accepts_match():
    url = "https://www.facebook.com/1835413968/posts/10226577231697088/"
    info = {"uploader_id": "1835413968", "uploader": "Real User"}
    assert facebook_owner_mismatch(url, info) is False


def test_facebook_owner_mismatch_skips_when_url_has_no_numeric_id():
    url = "https://www.facebook.com/share/abc123/"
    info = {"uploader_id": "1234", "uploader": "X"}
    assert facebook_owner_mismatch(url, info) is False


def test_facebook_owner_mismatch_skips_when_yt_no_uploader_id():
    url = "https://www.facebook.com/1835413968/posts/x/"
    info = {"uploader": "X"}
    assert facebook_owner_mismatch(url, info) is False
