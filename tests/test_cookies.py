import os
import sqlite3
import tempfile
from unittest.mock import patch

import cookies
import state


def _make_firefox_db(path: str, rows: list[tuple]) -> None:
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE moz_cookies (
            name TEXT, value TEXT, host TEXT, path TEXT,
            expiry INTEGER, isSecure INTEGER, isHttpOnly INTEGER
        )
    """)
    conn.executemany(
        "INSERT INTO moz_cookies VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


def test_extract_firefox_cookies_missing_file(tmp_path):
    fake_profile = tmp_path / "does-not-exist"
    with patch.object(cookies, "FIREFOX_PROFILE_PATH", str(fake_profile)):
        assert cookies.extract_firefox_cookies() == []


def test_extract_firefox_cookies_reads_rows(tmp_path):
    profile = tmp_path / "profile"
    profile.mkdir()
    db_path = profile / "cookies.sqlite"
    _make_firefox_db(
        str(db_path),
        rows=[
            ("session", "abc", ".reddit.com", "/", 9999999999, 1, 1),
            ("pref", "xyz", ".example.com", "/", 0, 0, 0),
        ],
    )

    with patch.object(cookies, "FIREFOX_PROFILE_PATH", str(profile)):
        result = cookies.extract_firefox_cookies()

    by_name = {c['name']: c for c in result}
    assert by_name['session']['domain'] == ".reddit.com"
    assert by_name['session']['secure'] is True
    assert by_name['session']['httpOnly'] is True
    assert by_name['pref']['expires'] == -1


def test_extract_firefox_cookies_clamps_future_date(tmp_path):
    profile = tmp_path / "profile"
    profile.mkdir()
    db_path = profile / "cookies.sqlite"
    bogus_future = 9999999999999
    _make_firefox_db(str(db_path), rows=[("bogus", "v", "x.com", "/", bogus_future, 0, 0)])

    with patch.object(cookies, "FIREFOX_PROFILE_PATH", str(profile)):
        result = cookies.extract_firefox_cookies()

    assert result[0]['expires'] == 253402300799


def test_get_aiohttp_cookies_filters_by_domain():
    state.FIREFOX_COOKIES_CACHE = [
        {'name': 'a', 'value': '1', 'domain': '.reddit.com'},
        {'name': 'b', 'value': '2', 'domain': '.example.com'},
        {'name': 'c', 'value': '3', 'domain': 'reddit.com'},
    ]
    try:
        got = cookies.get_aiohttp_cookies_for_url("https://www.reddit.com/r/pics/")
        assert got == {'a': '1', 'c': '3'}
    finally:
        state.FIREFOX_COOKIES_CACHE = []


def test_get_aiohttp_cookies_empty_when_no_match():
    state.FIREFOX_COOKIES_CACHE = [
        {'name': 'a', 'value': '1', 'domain': '.reddit.com'},
    ]
    try:
        got = cookies.get_aiohttp_cookies_for_url("https://instagram.com/foo")
        assert got == {}
    finally:
        state.FIREFOX_COOKIES_CACHE = []
