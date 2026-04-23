"""Testes dos helpers puros do dispatcher."""
import os
from pathlib import Path

from downloaders.dispatcher import (
    Platform,
    _apply_format_selection,
    _attempt_order,
    _build_caption,
    _build_lang_buttons,
    _detect_platform,
    _list_downloaded_files,
    _normalize_youtube_url,
    _parse_lang_from_format,
    _wipe_folder,
)


def test_detect_platform_youtube():
    assert _detect_platform("https://youtube.com/watch?v=x").youtube is True
    assert _detect_platform("https://youtu.be/abc").youtube is True
    assert _detect_platform("https://youtu.be/abc").reddit is False


def test_detect_platform_reddit_short_and_full():
    assert _detect_platform("https://reddit.com/r/pics/").reddit is True
    assert _detect_platform("https://redd.it/xyz").reddit is True


def test_detect_platform_threads_and_instagram():
    assert _detect_platform("https://www.threads.net/@user/post/1").threads is True
    assert _detect_platform("https://threads.com/@user/post/1").threads is True
    assert _detect_platform("https://www.instagram.com/p/abc/").instagram is True


def test_detect_platform_rejects_lookalike_domains():
    """URLs com domínios parecidos (fakeinstagram.com) não devem ser confundidos."""
    assert _detect_platform("https://fakeinstagram.com/p/abc/").instagram is False
    assert _detect_platform("https://notreddit.com/r/pics/").reddit is False
    assert _detect_platform("https://youtube.com.phishing.xyz/watch?v=x").youtube is False


def test_detect_platform_accepts_legitimate_subdomains():
    """Subdomínios legítimos (m.youtube.com, old.reddit.com) devem casar."""
    assert _detect_platform("https://m.youtube.com/watch?v=x").youtube is True
    assert _detect_platform("https://music.youtube.com/watch?v=x").youtube is True
    assert _detect_platform("https://old.reddit.com/r/pics/").reddit is True


def test_detect_platform_handles_garbage_input():
    """Entradas inválidas não devem explodir."""
    plat = _detect_platform("not a url")
    assert not any([plat.threads, plat.instagram, plat.youtube, plat.reddit])
    plat = _detect_platform("")
    assert not any([plat.threads, plat.instagram, plat.youtube, plat.reddit])


def test_normalize_youtube_strips_si_param():
    url = "https://youtu.be/abc123?si=xxxxxx"
    assert _normalize_youtube_url(url) == "https://youtu.be/abc123"


def test_normalize_youtube_converts_shorts_to_watch():
    url = "https://youtube.com/shorts/abc123"
    assert _normalize_youtube_url(url) == "https://www.youtube.com/watch?v=abc123"


def test_normalize_youtube_handles_non_youtube_untouched():
    assert _normalize_youtube_url("https://example.com/foo") == "https://example.com/foo"


def test_attempt_order_target_lang_specific_starts_with_cookie():
    assert _attempt_order(has_firefox_cookie=True, target_lang='pt') == ["with_cookie", "no_cookie"]


def test_attempt_order_original_prefers_anonymous():
    assert _attempt_order(has_firefox_cookie=True, target_lang='original') == ["no_cookie", "with_cookie"]
    assert _attempt_order(has_firefox_cookie=True, target_lang=None) == ["no_cookie", "with_cookie"]


def test_attempt_order_without_cookie():
    assert _attempt_order(has_firefox_cookie=False, target_lang='pt') == ["no_cookie"]
    assert _attempt_order(has_firefox_cookie=False, target_lang=None) == ["no_cookie"]


def test_apply_format_youtube_with_lang():
    opts = {}
    _apply_format_selection(opts, Platform(youtube=True), target_lang='pt')
    assert '[language^=pt]' in opts['format']
    assert opts['merge_output_format'] == 'mp4'


def test_apply_format_instagram_uses_best():
    opts = {}
    _apply_format_selection(opts, Platform(instagram=True), target_lang=None)
    assert opts['format'] == 'best'
    assert opts['noplaylist'] is False


def test_build_caption_escapes_html():
    info = {'title': '<script>', 'description': 'desc & stuff'}
    caption, text_content = _build_caption(info, 'https://x.test')
    assert '<script>' not in caption
    assert '&lt;script&gt;' in caption
    assert 'desc &amp; stuff' in caption
    assert 'x.test' in caption
    assert 'x.test' in text_content


def test_build_caption_truncates_long_description():
    """Descrição gigante deve ser truncada ANTES de virar HTML.

    O truncamento acontece no conteúdo da descrição (com '...' no meio do
    caption, antes do link), não no final — assim as tags <b>...</b> ficam
    sempre balanceadas.
    """
    info = {'title': 't', 'description': 'x' * 2000}
    caption, _ = _build_caption(info, 'https://x.test')
    assert '...' in caption
    assert len(caption) <= 1024
    # Tags balanceadas: toda <b> tem </b>, todo <a...> tem </a>.
    assert caption.count('<b>') == caption.count('</b>')
    assert caption.count('<a ') == caption.count('</a>')


def test_build_caption_handles_html_special_chars_in_title():
    """Título com <, >, & não pode virar tag HTML depois do truncamento."""
    info = {'title': '<script>alert(1)</script>', 'description': 'ok'}
    caption, _ = _build_caption(info, 'https://x.test')
    assert '<script>' not in caption
    assert '&lt;script&gt;' in caption


def test_build_caption_tags_balanced_even_when_description_is_enormous():
    """Mesmo com descrição 100k chars, tags HTML devem ficar balanceadas."""
    info = {'title': 'T' * 500, 'description': 'D' * 100_000}
    caption, text = _build_caption(info, 'https://x.test?token=secret')
    for out in (caption, text):
        assert out.count('<b>') == out.count('</b>')
        assert out.count('<a ') == out.count('</a>')


def test_build_caption_empty_when_no_info():
    caption, text_content = _build_caption({}, 'https://x.test')
    assert caption == ""
    assert 'x.test' in text_content


def test_parse_lang_from_format_language_field():
    clean, untagged = _parse_lang_from_format({
        'acodec': 'aac', 'language': 'pt-BR', 'format_id': '140',
    })
    assert clean == 'pt'
    assert untagged is False


def test_parse_lang_from_format_id_based():
    clean, _ = _parse_lang_from_format({'acodec': 'aac', 'format_id': '251-pt'})
    assert clean == 'pt'


def test_parse_lang_from_format_untagged():
    clean, untagged = _parse_lang_from_format({'acodec': 'aac', 'format_id': '140'})
    assert clean is None
    assert untagged is True


def test_parse_lang_from_format_no_audio():
    clean, untagged = _parse_lang_from_format({'acodec': 'none', 'format_id': '137'})
    assert clean is None
    assert untagged is False


def test_build_lang_buttons_returns_empty_for_single_lang():
    assert _build_lang_buttons({'pt'}, None, False) == []


def test_build_lang_buttons_marks_original():
    buttons = _build_lang_buttons({'pt', 'en'}, 'pt', False)
    labels = dict(buttons)
    assert labels['original'] == 'ORIGINAL [PT]'
    assert labels['en'] == 'EN'


def test_build_lang_buttons_prepends_original_if_untagged():
    buttons = _build_lang_buttons({'pt', 'en'}, None, True)
    assert buttons[0] == ('original', 'ORIGINAL')


def test_list_downloaded_files_ignores_partials(tmp_path):
    (tmp_path / "good.mp4").write_text("x")
    (tmp_path / "progress.part").write_text("x")
    (tmp_path / "cache.ytdl").write_text("x")
    (tmp_path / "file.temp").write_text("x")
    result = _list_downloaded_files(str(tmp_path))
    assert len(result) == 1
    assert result[0].endswith("good.mp4")


def test_list_downloaded_files_missing_folder():
    assert _list_downloaded_files("/does/not/exist/xyz") == []


def test_wipe_folder_removes_files_only(tmp_path):
    subdir = tmp_path / "sub"
    subdir.mkdir()
    (tmp_path / "a.txt").write_text("x")
    (tmp_path / "b.txt").write_text("x")
    _wipe_folder(str(tmp_path))
    assert Path(tmp_path).exists()
    assert subdir.exists()
    assert not any(p.is_file() for p in tmp_path.iterdir())
