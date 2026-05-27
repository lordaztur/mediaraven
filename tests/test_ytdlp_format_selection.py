from unittest.mock import patch

from downloaders import _ytdlp
from downloaders._platform import Platform


def test_calc_max_tbr_kbps_basic():
    assert _ytdlp._calc_max_tbr_kbps(6798, 2000) == 2289


def test_calc_max_tbr_kbps_short_video():
    result = _ytdlp._calc_max_tbr_kbps(60, 2000)
    assert result is not None and result > 200_000


def test_calc_max_tbr_kbps_no_duration():
    assert _ytdlp._calc_max_tbr_kbps(0, 2000) is None
    assert _ytdlp._calc_max_tbr_kbps(None, 2000) is None
    assert _ytdlp._calc_max_tbr_kbps(-10, 2000) is None


def test_calc_max_tbr_kbps_floor():
    assert _ytdlp._calc_max_tbr_kbps(10**9, 2000) == 50


def test_is_hls_only_true():
    formats = [
        {'protocol': 'm3u8_native', 'vcodec': 'avc1', 'height': 720},
        {'protocol': 'm3u8_native', 'vcodec': 'avc1', 'height': 1080},
    ]
    assert _ytdlp._is_hls_only(formats) is True


def test_is_hls_only_ignores_audio_only():
    formats = [
        {'protocol': 'https', 'vcodec': 'none', 'acodec': 'mp4a'},
        {'protocol': 'm3u8_native', 'vcodec': 'avc1'},
    ]
    assert _ytdlp._is_hls_only(formats) is True


def test_is_hls_only_false_when_progressive_present():
    formats = [
        {'protocol': 'https', 'vcodec': 'avc1', 'height': 720},
        {'protocol': 'm3u8_native', 'vcodec': 'avc1', 'height': 1080},
    ]
    assert _ytdlp._is_hls_only(formats) is False


def test_is_hls_only_empty():
    assert _ytdlp._is_hls_only([]) is False


def test_is_hls_only_dash_counts_as_streamed():
    formats = [{'protocol': 'http_dash_segments', 'vcodec': 'avc1', 'height': 1080}]
    assert _ytdlp._is_hls_only(formats) is True


def test_build_format_selector_no_lang_no_tbr():
    sel = _ytdlp._build_format_selector(1080, 2000, "", target_lang=None, youtube=False)
    assert 'bestvideo[height<=1080]' in sel
    assert '[filesize_approx<1900M]' in sel
    assert '[filesize_approx<2000M]' in sel
    assert 'tbr' not in sel
    assert sel.endswith('/best')


def test_build_format_selector_with_tbr():
    sel = _ytdlp._build_format_selector(720, 2000, "[tbr<=2289]", target_lang=None, youtube=False)
    assert 'best[height<=720][tbr<=2289]' in sel
    assert 'best[tbr<=2289]' in sel


def test_build_format_selector_youtube_with_lang():
    sel = _ytdlp._build_format_selector(1080, 2000, "", target_lang="pt", youtube=True)
    assert '[language^=pt]' in sel
    assert '[filesize_approx<2000M]' in sel


def test_apply_format_selection_no_info_falls_back_to_static_cap():
    opts = {}
    platform = Platform(youtube=True)
    with patch.object(_ytdlp, 'cfg', lambda k: {'YTDLP_MAX_HEIGHT': 1920, 'TELEGRAM_MAX_UPLOAD_MB': 2000, 'YTDLP_HLS_MAX_HEIGHT': 720}.get(k)):
        _ytdlp._apply_format_selection(opts, platform, None)
    assert 'bestvideo[height<=1920]' in opts['format']
    assert 'tbr' not in opts['format']


def test_apply_format_selection_hls_only_caps_height():
    opts = {}
    platform = Platform(youtube=True)
    info = {
        'duration': 6798,
        'formats': [{'protocol': 'm3u8_native', 'vcodec': 'avc1', 'height': 1094, 'tbr': 4561}],
    }
    with patch.object(_ytdlp, 'cfg', lambda k: {'YTDLP_MAX_HEIGHT': 1920, 'TELEGRAM_MAX_UPLOAD_MB': 2000, 'YTDLP_HLS_MAX_HEIGHT': 720}.get(k)):
        _ytdlp._apply_format_selection(opts, platform, None, info=info)
    assert '[height<=720]' in opts['format']
    assert '[tbr<=2289]' in opts['format']


def test_apply_format_selection_progressive_keeps_max_height():
    opts = {}
    platform = Platform(youtube=True)
    info = {
        'duration': 600,
        'formats': [
            {'protocol': 'https', 'vcodec': 'avc1', 'height': 1080, 'filesize_approx': 100_000_000},
            {'protocol': 'm3u8_native', 'vcodec': 'avc1', 'height': 1080},
        ],
    }
    with patch.object(_ytdlp, 'cfg', lambda k: {'YTDLP_MAX_HEIGHT': 1920, 'TELEGRAM_MAX_UPLOAD_MB': 2000, 'YTDLP_HLS_MAX_HEIGHT': 720}.get(k)):
        _ytdlp._apply_format_selection(opts, platform, None, info=info)
    assert '[height<=1920]' in opts['format']


def test_apply_format_selection_reddit_sets_impersonate_by_default():
    opts = {}
    platform = Platform(reddit=True)
    with patch.object(_ytdlp, 'cfg', lambda k: {'YTDLP_MAX_HEIGHT': 1920, 'TELEGRAM_MAX_UPLOAD_MB': 2000, 'YTDLP_HLS_MAX_HEIGHT': 720}.get(k)):
        _ytdlp._apply_format_selection(opts, platform, None)
    assert 'impersonate' in opts


def test_apply_format_selection_reddit_skips_impersonate_when_disabled():
    opts = {}
    platform = Platform(reddit=True)
    with patch.object(_ytdlp, 'cfg', lambda k: {'YTDLP_MAX_HEIGHT': 1920, 'TELEGRAM_MAX_UPLOAD_MB': 2000, 'YTDLP_HLS_MAX_HEIGHT': 720}.get(k)):
        _ytdlp._apply_format_selection(opts, platform, None, use_impersonate=False)
    assert 'impersonate' not in opts


def test_apply_format_selection_pops_existing_impersonate_when_disabled():
    from yt_dlp.networking.impersonate import ImpersonateTarget
    opts = {'impersonate': ImpersonateTarget('chrome')}
    platform = Platform(reddit=True)
    with patch.object(_ytdlp, 'cfg', lambda k: {'YTDLP_MAX_HEIGHT': 1920, 'TELEGRAM_MAX_UPLOAD_MB': 2000, 'YTDLP_HLS_MAX_HEIGHT': 720}.get(k)):
        _ytdlp._apply_format_selection(opts, platform, None, use_impersonate=False)
    assert 'impersonate' not in opts


def test_apply_format_selection_facebook_keeps_impersonate_even_with_use_imp_false():
    opts = {}
    platform = Platform(facebook=True)
    with patch.object(_ytdlp, 'cfg', lambda k: {'YTDLP_MAX_HEIGHT': 1920, 'TELEGRAM_MAX_UPLOAD_MB': 2000, 'YTDLP_HLS_MAX_HEIGHT': 720}.get(k)):
        _ytdlp._apply_format_selection(opts, platform, None)
    assert 'impersonate' in opts
    opts2 = {}
    with patch.object(_ytdlp, 'cfg', lambda k: {'YTDLP_MAX_HEIGHT': 1920, 'TELEGRAM_MAX_UPLOAD_MB': 2000, 'YTDLP_HLS_MAX_HEIGHT': 720}.get(k)):
        _ytdlp._apply_format_selection(opts2, platform, None, use_impersonate=False)
    assert 'impersonate' not in opts2


def test_expand_attempts_reddit_tries_no_imp_first():
    attempts = ['no_cookie', 'with_cookie']
    expanded = _ytdlp._expand_attempts_with_impersonate(attempts, Platform(reddit=True))
    assert expanded == [
        ('no_cookie', False), ('with_cookie', False),
        ('no_cookie', True), ('with_cookie', True),
    ]


def test_expand_attempts_facebook_and_instagram_also_try_no_imp_first():
    attempts = ['no_cookie', 'with_cookie']
    for plat in (Platform(facebook=True), Platform(instagram=True)):
        expanded = _ytdlp._expand_attempts_with_impersonate(attempts, plat)
        assert expanded == [
            ('no_cookie', False), ('with_cookie', False),
            ('no_cookie', True), ('with_cookie', True),
        ]


def test_expand_attempts_youtube_and_other_skip_no_imp_path():
    attempts = ['no_cookie', 'with_cookie']
    for plat in (Platform(youtube=True), None):
        expanded = _ytdlp._expand_attempts_with_impersonate(attempts, plat)
        assert expanded == [('no_cookie', True), ('with_cookie', True)]


def test_classify_ytdlp_errors_private():
    err = ["ERROR: [youtube] xyz: Private video. Sign in if you've been granted access"]
    assert _ytdlp._classify_ytdlp_errors(err) == 'private'


def test_classify_ytdlp_errors_geo_blocked():
    err = ["ERROR: Video is not available in your country."]
    assert _ytdlp._classify_ytdlp_errors(err) == 'geo_blocked'


def test_classify_ytdlp_errors_removed():
    err = ["This video has been removed by the uploader"]
    assert _ytdlp._classify_ytdlp_errors(err) == 'removed'


def test_classify_ytdlp_errors_members_only():
    err = ["Join this channel to get access to members-only content"]
    assert _ytdlp._classify_ytdlp_errors(err) == 'members_only'


def test_classify_ytdlp_errors_age_restricted():
    err = ["Sign in to confirm your age"]
    assert _ytdlp._classify_ytdlp_errors(err) == 'age_restricted'


def test_classify_ytdlp_errors_rate_limited():
    err = ["HTTP Error 429: Too Many Requests"]
    assert _ytdlp._classify_ytdlp_errors(err) == 'rate_limited'


def test_classify_ytdlp_errors_returns_none_when_unrecognized():
    err = ["Generic network error"]
    assert _ytdlp._classify_ytdlp_errors(err) is None
    assert _ytdlp._classify_ytdlp_errors([]) is None


def test_classify_ytdlp_errors_first_pattern_wins():
    err = ["Private video. Sign in if you've been granted access. Also age-restricted"]
    assert _ytdlp._classify_ytdlp_errors(err) == 'private'


def test_classify_ytdlp_errors_facebook_registered_users():
    err = ["ERROR: [facebook] 123: This video is only available for registered users. Use --cookies-from-browser"]
    assert _ytdlp._classify_ytdlp_errors(err) == 'sign_in_required'


def test_classify_ytdlp_errors_use_cookies_hint():
    err = ["ERROR: [extractor] Something failed. Use --cookies to authenticate"]
    assert _ytdlp._classify_ytdlp_errors(err) == 'sign_in_required'


def test_classify_ytdlp_errors_too_many_requests():
    err = ["ERROR: 429 Too Many Requests"]
    assert _ytdlp._classify_ytdlp_errors(err) == 'rate_limited'


def test_classify_ytdlp_errors_private_account():
    err = ["This account is private"]
    assert _ytdlp._classify_ytdlp_errors(err) == 'private'
