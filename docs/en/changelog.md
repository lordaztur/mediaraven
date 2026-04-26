# Changelog

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
