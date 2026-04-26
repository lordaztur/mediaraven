from unittest.mock import AsyncMock, patch

import pytest

from downloaders import fallback


PAYWALL_HTML = """
<html><body>
<p>Subscribe to read this article. Sign in to continue.</p>
</body></html>
"""

CLEAN_HTML = """
<html><body>
<article><p>Conteúdo livre do artigo, sem paywall nenhum aqui.</p></article>
</body></html>
"""


@pytest.mark.asyncio
async def test_no_paywall_returns_normal_immediately():
    async def fake_fetch(url, timeout, user_agent=None):
        return CLEAN_HTML
    with patch.object(fallback, "_fetch_html", new=AsyncMock(side_effect=fake_fetch)) as m:
        html, source = await fallback._fetch_html_with_paywall_bypass("https://x.com/a", 10)
    assert html == CLEAN_HTML
    assert source == "normal"
    assert m.await_count == 1


@pytest.mark.asyncio
async def test_paywall_bypassed_by_googlebot():
    calls = []

    async def fake_fetch(url, timeout, user_agent=None):
        calls.append(user_agent)
        if user_agent and "Googlebot" in user_agent:
            return CLEAN_HTML
        return PAYWALL_HTML

    with patch.object(fallback, "_fetch_html", new=AsyncMock(side_effect=fake_fetch)):
        html, source = await fallback._fetch_html_with_paywall_bypass("https://nytimes.com/x", 10)

    assert html == CLEAN_HTML
    assert source == "googlebot"
    assert calls == [None, fallback._GOOGLEBOT_UA]


@pytest.mark.asyncio
async def test_paywall_falls_to_archive_when_googlebot_blocked():
    seen_urls = []

    async def fake_fetch(url, timeout, user_agent=None):
        seen_urls.append(url)
        if "archive.ph" in url:
            return CLEAN_HTML
        return PAYWALL_HTML

    with patch.object(fallback, "_fetch_html", new=AsyncMock(side_effect=fake_fetch)):
        html, source = await fallback._fetch_html_with_paywall_bypass("https://ft.com/a", 10)

    assert html == CLEAN_HTML
    assert source == "archive"
    assert any("archive.ph" in u for u in seen_urls)


@pytest.mark.asyncio
async def test_returns_original_when_all_bypass_fail():
    async def fake_fetch(url, timeout, user_agent=None):
        return PAYWALL_HTML

    with patch.object(fallback, "_fetch_html", new=AsyncMock(side_effect=fake_fetch)):
        html, source = await fallback._fetch_html_with_paywall_bypass("https://wsj.com/a", 10)

    assert html == PAYWALL_HTML
    assert source == "normal"


@pytest.mark.asyncio
async def test_bypass_disabled_returns_original_paywall():
    async def fake_fetch(url, timeout, user_agent=None):
        return PAYWALL_HTML

    with patch.object(fallback, "SCRAPE_PAYWALL_BYPASS", "no"), \
         patch.object(fallback, "_fetch_html", new=AsyncMock(side_effect=fake_fetch)) as m:
        html, source = await fallback._fetch_html_with_paywall_bypass("https://wsj.com/a", 10)

    assert html == PAYWALL_HTML
    assert source == "normal"
    assert m.await_count == 1


@pytest.mark.asyncio
async def test_first_fetch_returns_none_propagates():
    async def fake_fetch(url, timeout, user_agent=None):
        return None

    with patch.object(fallback, "_fetch_html", new=AsyncMock(side_effect=fake_fetch)):
        html, source = await fallback._fetch_html_with_paywall_bypass("https://x.com/a", 10)

    assert html is None
    assert source == ""
