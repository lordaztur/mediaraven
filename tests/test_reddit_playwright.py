import pytest

from downloaders.reddit_playwright import _force_old_reddit


@pytest.mark.parametrize("input_url,expected", [
    ("https://reddit.com/r/foo/comments/abc/x/", "https://old.reddit.com/r/foo/comments/abc/x/"),
    ("https://www.reddit.com/r/foo/comments/abc/x/", "https://old.reddit.com/r/foo/comments/abc/x/"),
    ("https://new.reddit.com/r/foo/comments/abc/x/", "https://old.reddit.com/r/foo/comments/abc/x/"),
    ("https://np.reddit.com/r/foo/comments/abc/x/", "https://old.reddit.com/r/foo/comments/abc/x/"),
    ("https://www.reddit.com/r/pics/comments/abc/?utm_source=share", "https://old.reddit.com/r/pics/comments/abc/?utm_source=share"),
])
def test_force_old_reddit_swaps_to_old(input_url, expected):
    assert _force_old_reddit(input_url) == expected


@pytest.mark.parametrize("url", [
    "https://old.reddit.com/r/foo/",
    "https://i.redd.it/abc.jpg",
    "https://v.redd.it/xyz/DASH_720.mp4",
    "https://redd.it/abc",
    "https://example.com/r/foo/",
])
def test_force_old_reddit_leaves_other_hosts_unchanged(url):
    assert _force_old_reddit(url) == url


def test_force_old_reddit_handles_invalid_url():
    assert _force_old_reddit("") == ""
    assert _force_old_reddit("not-a-url") == "not-a-url"
