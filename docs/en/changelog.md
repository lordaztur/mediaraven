# Changelog

## v1.2.10 — Dedicated Facebook handler (carousels via gallery-dl) + yt-dlp uploader validation + unified attempt order + broader classifier coverage

**Major changes:**

- 📘 **New dedicated Facebook handler in `downloaders/facebook.py`**. For any FB link, the dispatcher now tries `gallery-dl` first (with Firefox cookies) — gallery-dl extracts image carousels correctly via SSR API, avoiding timeline scraping. If gallery-dl finds files → uses it directly with status `📘 Facebook Gallery [N files]`. Otherwise falls through to the normal flow (yt-dlp for video). Confirmed: a 20-image carousel post that returned the wrong video now comes complete (~250KB each).
- 🛡️ **`facebook_owner_mismatch` validation after yt-dlp success on FB.** Facebook extractor in yt-dlp has a bug: when the original post is image-only, it "finds" any embedded video on the page (sponsored/recommendation/comment) and returns it as "success". Practical result: user sends a carousel link and receives a random video from another user. Now: we compare `uploader_id` returned by yt-dlp against the numeric user_id from the URL (`facebook.com/<UID>/posts/...`). On mismatch, we discard the result and continue to fallbacks.
- 🍪 **`_gallery_dl_run` now injects Firefox cookies** (via `gdl_config.set(('extractor',), 'cookies', ('firefox', profile))`). Needed for FB; no side effects on other platforms (Pinterest/Imgur already worked without auth).
- 🖼️ **Facebook image carousels download even without login.** The `_drop_facebook_image_only` heuristic (introduced in v1.0.x to avoid 50+ UI thumbnails when user sent video links) was too aggressive: it discarded ANY FB post without `.mp4` as "UI junk", which included legit photo/carousel posts. **Function removed.** Replaced by expanding `is_junk_url` with known FB/Reddit UI hosts/paths (`static.xx.fbcdn.net`, `static.cdninstagram.com`, `styles.redditmedia.com`, `alb.reddit.com`, `id.rlcdn.com`, `/rsrc.php/`, `/safe_image.php`, `headshot`, `snoovatar`, `_profile`, `communityicon`, `profileicon`, `awardicon`) — UI is now filtered at the source (before download) and real post images pass through.
- 🔁 **`_expand_attempts_with_impersonate` now applies the "no_imp first, imp as fallback" pattern to Facebook/Instagram too** (previously Reddit-only). For FB/IG/Reddit: 4 attempts `[no_cookie+no_imp, with_cookie+no_imp, no_cookie+imp, with_cookie+imp]`. For YouTube/others (don't use impersonate): 2 attempts as before. Why: manual tests with Facebook showed that `impersonate=chrome` makes FB return a heavy SPA that yt-dlp can't parse (`"Cannot parse data"`), while without impersonate it returns a semantic error (`"No video formats found"`) that the classifier can recognize and respond to correctly.
- 🛑 **Facebook with "This video is only available for registered users" wasn't being classified by v1.2.9** — fell through to the scraper and the heuristic discarded everything. Added patterns: `only available for registered users`, `only available for registered`, `only available to registered`, `use --cookies`, `requires login`, `please log in`. Other new patterns: `this account is private` → `private`, `restricted to subscribers` → `members_only`, `this content isn't available`/`this tweet is unavailable`/`no video formats found`/`no media found`/`cannot parse data` → `unavailable`, `this video is no longer available` → `removed`, `too many requests` → `rate_limited`.

**Removed:**

- `_drop_facebook_image_only` function in `downloaders/fallback.py` (and 4 call sites)
- Log key `fallback.facebook_image_only_dropped` (PT/EN)

**Added:**

- New module `downloaders/facebook.py` with `download_facebook_gallery` and `facebook_owner_mismatch`
- UI message `downloader_status.facebook_gallery` (PT/EN) and 2 log keys `facebook.tentando_gallery_dl`, `facebook.gallery_dl_ok`, `dispatcher.facebook_owner_mismatch`
- 5 tests in `tests/test_facebook.py` (mismatch detection: no info / match / mismatch / share URL / no uploader_id)
- 4 tests in `tests/test_ytdlp_format_selection.py` (registered users / use --cookies / 429 / private account)
- `test_expand_attempts_facebook_and_instagram_also_try_no_imp_first` in `tests/test_ytdlp_format_selection.py`
- 3 tests in `tests/test_scrape_helpers.py` covering new junk patterns (FB static, Reddit UI, real FB post image)

## v1.2.9 — Detect unrecoverable yt-dlp errors (private/removed/geo/etc.) and skip fallbacks

**Major changes:**

- 🛑 **Private/removed/geo-blocked/etc. videos now return a clear message** instead of falling through to the generic scraper (which was picking up the YouTube/Google logo from the error page as if it were the media). Before: private video link → yt-dlp fails → scraper scrapes page → sends Google logo to chat. Now: yt-dlp captures the error, classifies it as `private`/`removed`/`geo_blocked`/`members_only`/`age_restricted`/`sign_in_required`/`live_not_started`/`unavailable`/`rate_limited`, and the dispatcher stops immediately with a specific message.
- 🪵 **yt-dlp error capture via `logger=` opts** instead of fiddling with `ignoreerrors`. Each extraction call now returns `(info, error_messages)` when `capture_errors=True`. The classifier matches against 21 known patterns (case-insensitive) and returns the category.

**Refactors:**

- `_yt_dlp_extract` takes `capture_errors: bool = False`; when True returns `(info, errors)` tuple instead of just `info`
- New helper `_classify_ytdlp_errors(error_messages) -> Optional[str]` in `downloaders/_ytdlp.py` with patterns for: `private`, `members_only`, `age_restricted`, `geo_blocked`, `removed`, `live_not_started`, `unavailable`, `sign_in_required`, `rate_limited`
- `_run_ytdlp_with_cookie_fallback` now returns `(files, info, unrecoverable_reason)`. Instead of just listing files, it accumulates errors from all attempts and classifies at the end
- `dispatcher.download_media` checks `unrecoverable_reason` before calling fallbacks; if set, returns `msg("downloader_status.ytdlp_{reason}")` directly

**Added:**

- 9 UI messages (PT/EN) under `downloader_status.ytdlp_{private,unavailable,removed,geo_blocked,members_only,age_restricted,sign_in_required,live_not_started,rate_limited}`
- 2 log keys: `_ytdlp.unrecoverable_reason`, `dispatcher.unrecoverable_skip_fallbacks`
- 9 tests in `tests/test_ytdlp_format_selection.py` (classifier per category + None fallback) + 1 integration test in `tests/test_dispatcher_integration.py`

## v1.2.8 — Threads: extract media from `linked_inline_media` (media_type=19 posts)

**Major changes:**

- 🧵 **Threads posts with `media_type=19` (audio-augmented / new format) had media in `text_post_app_info.linked_inline_media`**, a field `_extract_media` didn't cover. The post has `video_versions` at root level as falsy/empty and `image_versions2.candidates: []`, so the bot fell into the "no media, caption only" branch and replied with text. Now `_extract_media` recurses into `linked_inline_media` (same structure: `carousel_media`/`video_versions`/`image_versions2`) before the `share_info.quoted_post` fallback. Direct media still takes precedence.

**Added:**

- 3 tests in `tests/test_threads.py` (`linked_inline_media` with video, with image, direct-media precedence)

## v1.2.7 — AIORateLimiter actually retries now (max_retries=3)

**Major changes:**

- 🐛 **In v1.2.4 the `AIORateLimiter` was added, but with `max_retries=0` (default).** Result: on flood control (`Retry in N seconds`), the limiter only logged `Rate limit hit after maximum of 0 retries` and re-raised `RetryAfter`, making the original request fail and the handler blow up — exactly the symptom v1.2.4 tried to fix. The status_msg got stuck on "downloading" because `_safe_edit` to "internal_error" hit the same flood. Now `AIORateLimiter(max_retries=3)`: the limiter waits for `Retry-After` from Telegram and retries up to 3 times automatically.

## v1.2.6 — Reddit: try without impersonate first (fixes IP-block)

**Major changes:**

- 🐛 **Reddit was returning `Your IP address is unable to access the Reddit API` when yt-dlp was called with `impersonate=ImpersonateTarget('chrome')`** (enabled for Reddit in v1.0.x). Result: `bestvideo+bestaudio/best` failed on any video post, and the bot fell through to the generic scraper which grabbed avatars/community icons instead of the video. Now, for Reddit, attempts are expanded to `[no_cookie+no_imp, with_cookie+no_imp, no_cookie+imp, with_cookie+imp]` — impersonate becomes a fallback instead of default. Facebook/Instagram unchanged (always impersonate).
- 🧪 Manually verified: without impersonate, yt-dlp downloads Reddit video normally (~5 MB in 2s); with impersonate, returns IP-block.

**Refactors:**

- `_apply_format_selection` got `use_impersonate: bool = True` parameter in `downloaders/_ytdlp.py` — when False, does `opts.pop('impersonate', None)` (just gating the add isn't enough since the dispatcher injects impersonate into `base_opts` before the loop, and `current_opts.copy()` inherits it)
- New helper `_expand_attempts_with_impersonate(attempts, platform)` — for Reddit returns `[(m, False) for m in attempts] + [(m, True) for m in attempts]`; for others keeps `[(m, True) for m in attempts]`
- Main loop in `_run_ytdlp_with_cookie_fallback` now iterates `(mode, use_imp)`, calls `_apply_format_selection` on every iteration (not only when pre-extract info is present — otherwise the gating is skipped), and skips `_pre_extract` for Reddit (Reddit uses `format='bestvideo+bestaudio/best'` directly)
- Attempt log includes `_imp`/`_noimp` suffix in `mode` for diagnostics

**Added:**

- 6 tests in `tests/test_ytdlp_format_selection.py` (impersonate gating + pop when inherited + expand_attempts)

## v1.2.5 — Automatic video conversion to MP4 when needed

**Major changes:**

- 🎞️ **Videos in formats not supported by Telegram's native player are converted to MP4 before sending.** Telegram only guarantees a streaming player for MP4 H.264+AAC ([Bot API docs](https://core.telegram.org/bots/api#sendvideo): "other formats may be sent as Document"). Previously, `.webm`/`.mkv`/`.avi`/`.flv` would land as documents with no player; now they become MP4 before `send_video`.
- 🧠 **Smart strategy (probe + minimal remux/re-encode)**: `ffprobe` detects vcodec/acodec. If already H.264 → `-c:v copy` (instant, lossless). If AAC → `-c:a copy`. Otherwise, re-encode only the incompatible stream. If remux fails (codec doesn't fit MP4 container), auto-fallback to full re-encode.
- ✅ Compatible extensions (`.mp4`/`.m4v`/`.mov`) pass through with no ffprobe/ffmpeg call.

**Added:**

- `state.FFPROBE_PATH` + `init_ffmpeg` now discovers both `ffmpeg` and `ffprobe` in PATH in `lifecycle/startup.py`
- `is_telegram_compatible_video_ext`, `async_ffprobe_codecs`, `async_ensure_telegram_video` in `utils.py`
- `_ensure_video` helper in `telegram_io.py` (single-file and media_group)
- Config `VIDEO_CONVERT_TIMEOUT` (default 900s) in `config.py` + `customization.example.{json,en.json}`
- 13 new log keys (PT/EN): `startup.ffprobe_*`, `utils.ffprobe_*`, `utils.video_convert_*`
- 11 tests in `tests/test_video_convert.py` + 4 tests in `tests/test_telegram_io_timeouts.py`

## v1.2.4 — Rate limiter to prevent Flood control exceeded

**Major changes:**

- 🚦 **`AIORateLimiter` enabled** in `ApplicationBuilder`. Previously, when Telegram returned `RetryAfter: Flood control exceeded. Retry in N seconds` (on `edit_text`/`send_*`), the exception bubbled up without retry and the user's request failed. Now PTB respects `Retry-After` on all requests automatically — waits N+ε and retries, without propagating errors to the handler.

**Added:**

- `builder.rate_limiter(AIORateLimiter())` in `mediaraven.py`
- `python-telegram-bot[rate-limiter]==22.7` in `requirements.txt` (pulls `aiolimiter` as a transitive dependency)

## v1.2.3 — GIFs sent as animation (not buggy video)

**Major changes:**

- 🎞️ **GIFs now go through `send_animation`** instead of `send_video`. Telegram was treating GIFs as videos (no autoplay, no loop, ugly player). With `send_animation`, they become native animations.
- 🎞️ **GIFs are converted to MP4 (H.264) via ffmpeg before sending**. Telegram converts raw GIFs with quality loss and renders them small; silent MP4 is Telegram's native "animated GIF" format (the same one the official client uses) — much better quality and full size.
- 📐 Dimensions (`width`/`height`) extracted from the original GIF via PIL and passed to `send_animation` — ensures correct rendering even when ffmpeg is unavailable.

**Added:**

- `_ANIMATION_EXTS_DEFAULT = ('.gif',)` in `config.py` (extensible via env `ANIMATION_EXTS_EXTRA`); `.gif` removed from `VIDEO_EXTS_DEFAULT`
- `async_gif_to_mp4(input_path, output_path, timeout=60)` in `utils.py` (ffmpeg `-c:v libx264 -pix_fmt yuv420p -an -movflags +faststart`)
- Helper `_get_image_dims` + `send_animation` branch in `telegram_io.py` (with fallback to original `.gif` if ffmpeg fails)
- 6 log keys `utils.gif_to_mp4_*` in PT/EN
- 3 tests in `tests/test_telegram_io_timeouts.py` (gif→animation route, successful conversion, fallback on ffmpeg failure)

## v1.2.2 — Dynamic cap for HLS / finished YouTube lives

**Major changes:**

- 📺 **Finished YouTube live now fits**: ended lives (`live_status: post_live`) only expose HLS formats without `filesize_approx` declared. Previously the selector fell back to `best` and picked 1094p (~3.8 GB for 1h53min) → `File_parts_invalid` on upload. Now, **pre-extract** discovers `duration` + formats and:
    - Applies a **dynamic bitrate cap** `[tbr<=N]` computed as `(TELEGRAM_MAX_UPLOAD_MB × 8 × 1024) ÷ duration_s × 0.95`. For a 1h53min live with 2 GB cap → `tbr<=2289 kbps`.
    - Detects **HLS-only** (all video-bearing formats are `m3u8_native`/`http_dash_segments`) and applies a conservative height cap via the new config `YTDLP_HLS_MAX_HEIGHT` (default 720).
- 🎯 **Tiered format selector**: 1) DASH with filesize cap → 2) progressive with filesize cap → 3) progressive with tbr cap → 4) plain fallback. Ensures normal VODs still pick the best quality within the limit.

**Refactors:**

- Helpers extracted in `downloaders/_ytdlp.py`: `_calc_max_tbr_kbps`, `_is_hls_only`, `_build_format_selector`, `_pre_extract`.
- `_apply_format_selection` accepts `info: Optional[dict]` and adjusts the selector dynamically.
- `_run_ytdlp_with_cookie_fallback` accepts an optional `platform`; when passed, runs a pre-extract per attempt (cookie/no-cookie) and re-applies format selection with the real info.

**Added:**

- Config `YTDLP_HLS_MAX_HEIGHT` (default 720) in `customization.example.{json,en.json}`
- 3 new log keys: `_ytdlp.hls_only_height_cap`, `_ytdlp.tbr_cap`, `_ytdlp.pre_extract_falhou`
- 15 tests in `tests/test_ytdlp_format_selection.py`

## v1.2.1 — Upload size cap to prevent File_parts_invalid

**Major changes:**

- 📤 **Size cap in yt-dlp**: new config `TELEGRAM_MAX_UPLOAD_MB` (default 2000) applied as `[filesize_approx<...M]` in the format selector. Previously, long YouTube videos in 1440p60 could exceed 2 GB and fail with `BadRequest: File_parts_invalid` on upload (Telegram's hard limit for bots; **Premium does not affect bots** — [tdlib/telegram-bot-api#583](https://github.com/tdlib/telegram-bot-api/issues/583)). The selector now reserves ~100 MB for audio + container and falls back to 1080p when 1440p would exceed the cap.
- 📤 **PTB local_mode**: `telegram_io.send_downloaded_media` now passes the **path as a string** instead of a file handle. With `telegram-bot-api --local`, PTB sends a `file:///path` URI and the server reads from the filesystem directly, with no multipart upload — avoids timeouts on large but in-limit files. Confirmed by `parse_file_input` (telegram/_utils/files.py:145-149).
- 📚 **Doc corrected**: README/site/`.env_example` mentioned "4 GB with Premium" — false. Bots cannot be Premium; the limit is always 2 GB.

**Refactors:**

- `telegram_io.py` applies `TELEGRAM_UPLOAD_TIMEOUT` to `read_timeout`/`write_timeout`/`connect_timeout` in the single-file path (previously only media_group applied it).
- `_apply_format_selection` in `downloaders/_ytdlp.py` and `download_with_ytdlp_generic` in `downloaders/fallback.py` now build the selector with a filesize cap.

**Added:**

- Config `TELEGRAM_MAX_UPLOAD_MB` in `customization.example.json` + `.example.en.json` (default 2000, min 50, max 2000)
- 5 tests in `tests/test_telegram_io_timeouts.py`

## v1.2.0 — Pinterest, Kwai and chunked captions

**Major changes:**

- 📌 **Pinterest**: pin links (`pin.it/XXX`, `pinterest.com/pin/<id>`, regional like `br.pinterest.com`) now download only the pin media via `og:image`/`og:video`/JSON-LD filter with cap=1. Previously they pulled 60+ recommended images from the page.
- 🎬 **Kwai / SnackVideo**: shortlinks (`kwai-video.com/p/XXX`, `s.kw.ai`, `snackvideo.com/in`) resolved before yt-dlp; tracking query string stripped to avoid `File name too long` from the ID generated by the generic extractor. Hosts covered: `kwai-video.com`, `kwai.com`, `m.kwai.com`, `kw.ai`, `s.kw.ai`, `snackvideo.com`, `snackvideo.in`.
- ✂️ **Long captions in chunks**: captions over 1024 chars are no longer truncated. The media goes without caption and the full text is sent in chunks of up to 4096 chars (preferred separators: `\n\n` > `\n` > `". "` > `" "`). Captions that fit in 1024 are still attached to the media as before. No text duplication.
- 📰 **Article media filtering**: when an article is detected by trafilatura, only `og:image`/`og:video`/JSON-LD are considered (cap=1), instead of all scraped images. Previously banners, ads, related articles came along.

**Refactors:**

- `_build_caption` now returns a `(short, full)` tuple propagated through every downloader (Threads, X, Reddit, Instagram, Instagram Embed, fallback). `short` ≤ 1024, `full` not truncated.
- New helper `chunk_html_text(text, limit)` in `utils.py` splits text preserving semantic boundaries (paragraph > line > sentence > word).
- `_send_text_in_chunks` in `handlers.py` sends chunks sequentially with configurable delay.

**Added:**

- `_is_pinterest()` in `downloaders/fallback.py`
- `_is_kwai_host()` + `_resolve_kwai_url()` in `downloaders/_platform.py`
- 4 new log keys: `fallback.pinterest_media_filtered`, `_platform.resolvendo_kwai`, `_platform.kwai_resolvido`, `_platform.falha_ao_resolver_kwai`
- 16 new tests: `tests/test_fallback_pinterest.py` (7), `tests/test_kwai_resolver.py` (9)
- 6 new tests for `chunk_html_text` in `tests/test_utils_helpers.py`

## v1.1.0 — Granular customization + article extraction + paywall bypass

**Major changes:**

- 🎚️ **42 customizable configs per chat and per user** via `customization.json`. Precedence `user > chat > default > .env`. Includes timeouts, prompt defaults, quality, scraper, caption, platforms. Helper `cfg(key)` + ContextVar `request_context` allow transparent lookup without propagating IDs.
- 🌐 **180+ customizable log strings** via `log_messages.json` (separate from UI messages). Helper `lmsg(key, **kw)` with graceful fallback for missing keys.
- 🔒 **Soft paywall bypass** (Googlebot UA + archive.ph) toggleable via `SCRAPE_PAYWALL_BYPASS=yes`. Covers NYT, Folha, FT, Estadão, etc.
- 📰 **Article extraction via trafilatura** as caption. Auto-detects on any URL with >= 300 chars of text. Dedicated opt-in prompt (`ASK_ARTICLE_*`).
- 📝 **Text-only posts** (Threads, X) become formatted text messages (`📄 @user` + body + link), instead of "fail".
- 🌍 **Bilingual PT/EN documentation** + docs site with MkDocs Material.
- 🛡️ **`ALLOW_ALL`** env to run as public bot (whitelist ignored).

**Refactors:**

- `_build_caption` redesigned to have separate `uploader` + `title`. YT Shorts detected (no title duplication in body). Threads/X now use `@username` in header.
- Generic scraper parallelizes HTTP fast path + Playwright deep scrape (`asyncio.gather`).
- Logs with line numbers (`%(name)s:%(lineno)d`) + noisy libs silenced (httpx, urllib3, playwright, etc.).
- `exc_info=True` in ~10 fatal exception catches — stack traces preserved in log.
- Removed `MIN_CONTENT_LENGTH_BYTES` (20KB filter was nuking legit avatars).

**Added:**

- `version.py` (`__version__ = "1.1.0"`)
- `customization.example.json` + `.example.en.json` (PT/EN, with inline `_doc_KEY`)
- `log_messages.example.json` + `.example.en.json`
- `messages.example.en.json`
- `.env_example.en`
- `README.en.md`
- `gallery-dl` as scraper tier 3
- `trafilatura` as dependency (article extraction)
- 5 additional README badges (gallery-dl, trafilatura, instagrapi, curl-cffi, ffmpeg)

**Removed:**

- Envs `PROMPT_*_OFF_CHATS / ON_USERS / OFF_USERS` (replaced by `PROMPT_*_ENABLED` in `customization.json`)
- 25+ envs moved to `customization.json` (all ASK_*, SCRAPE_*, MEDIA_GROUP_*, etc.)

## v1.0.0 — Initial release

- Telegram bot with local Bot API
- Platforms: YouTube, Instagram, Reddit, Threads, X, Facebook
- Generic cascading scraper (HTTP + yt-dlp generic + gallery-dl + Playwright)
- 100% customizable messages via `messages.json`
- Per-chat and per-user whitelist
- ~80 tuning envs
