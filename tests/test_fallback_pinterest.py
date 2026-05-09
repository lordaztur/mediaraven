from unittest.mock import AsyncMock, patch

import pytest

from downloaders import fallback


def test_is_pinterest_detects_pin_it():
    assert fallback._is_pinterest("https://pin.it/6dN5bPvYt") is True


def test_is_pinterest_detects_pinterest_com():
    assert fallback._is_pinterest("https://www.pinterest.com/pin/123456/") is True


def test_is_pinterest_detects_regional_subdomain():
    assert fallback._is_pinterest("https://br.pinterest.com/pin/123/") is True


def test_is_pinterest_rejects_other_hosts():
    assert fallback._is_pinterest("https://example.com/pin/abc") is False
    assert fallback._is_pinterest("https://twitter.com/x") is False


def test_is_pinterest_handles_invalid_url():
    assert fallback._is_pinterest("not a url at all") is False


_PINTEREST_HTML = """
<html><head>
<meta property="og:image" content="https://i.pinimg.com/736x/aa/bb/cc/aabbcc.jpg" />
<meta property="og:image:width" content="736" />
<meta property="twitter:image:src" content="https://i.pinimg.com/736x/aa/bb/cc/aabbcc.jpg" />
</head><body>
<img src="https://i.pinimg.com/236x/recommended1.jpg">
<img src="https://i.pinimg.com/236x/recommended2.jpg">
<img src="https://i.pinimg.com/236x/recommended3.jpg">
</body></html>
"""


@pytest.mark.asyncio
async def test_scrape_fallback_pinterest_uses_only_og_image(tmp_path):
    folder = str(tmp_path / "pin")

    captured: dict = {}

    async def fake_download_all(prepared, url, unique_folder):
        captured["prepared"] = list(prepared)
        return ["fake.jpg"], 0

    with patch.object(fallback, "_fetch_html_with_paywall_bypass",
                      new=AsyncMock(return_value=(_PINTEREST_HTML, "fast"))), \
         patch.object(fallback, "_gather_media_via_playwright",
                      new=AsyncMock(return_value=([("image", f"https://i.pinimg.com/236x/junk{i}.jpg") for i in range(60)], [], _PINTEREST_HTML))), \
         patch.object(fallback, "fetch_article_caption",
                      new=AsyncMock(return_value=("", ""))), \
         patch.object(fallback, "_download_all", new=fake_download_all), \
         patch.object(fallback.state, "PW_BROWSER", True), \
         patch.object(fallback.state, "PW_CONTEXT", True):
        files, status, short, full, is_article = await fallback.scrape_fallback(
            "https://pin.it/6dN5bPvYt", folder,
        )

    assert is_article is False
    assert len(captured["prepared"]) == 1
    assert "pinimg.com" in captured["prepared"][0][1]


@pytest.mark.asyncio
async def test_scrape_fallback_non_pinterest_keeps_generic_path(tmp_path):
    folder = str(tmp_path / "page")

    captured: dict = {}

    async def fake_download_all(prepared, url, unique_folder):
        captured["prepared"] = list(prepared)
        return ["fake.jpg"], 0

    pw_media = [("image", f"https://example.com/img{i}.jpg") for i in range(5)]

    with patch.object(fallback, "_fetch_html_with_paywall_bypass",
                      new=AsyncMock(return_value=("<html></html>", "fast"))), \
         patch.object(fallback, "_gather_media_via_playwright",
                      new=AsyncMock(return_value=(pw_media, [], ""))), \
         patch.object(fallback, "fetch_article_caption",
                      new=AsyncMock(return_value=("", ""))), \
         patch.object(fallback, "_download_all", new=fake_download_all), \
         patch.object(fallback.state, "PW_BROWSER", True), \
         patch.object(fallback.state, "PW_CONTEXT", True):
        files, status, short, full, is_article = await fallback.scrape_fallback(
            "https://example.com/gallery", folder,
        )

    assert is_article is False
    assert len(captured["prepared"]) == 5
