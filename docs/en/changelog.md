# Changelog

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
