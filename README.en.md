<div align="center">

<img src="assets/banner.svg" alt="MediaRaven" width="720"/>

**Telegram bot that downloads any media from the internet and sends it straight to your chat.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-22.7-26A5E4?style=flat&logo=telegram&logoColor=white)](https://python-telegram-bot.org/)
[![yt-dlp](https://img.shields.io/badge/powered%20by-yt--dlp-red?style=flat)](https://github.com/yt-dlp/yt-dlp)
[![Playwright](https://img.shields.io/badge/playwright-1.58-2EAD33?style=flat&logo=playwright&logoColor=white)](https://playwright.dev/)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat)](LICENSE)

🇧🇷 [Português](README.md)

</div>

---

## ✨ What it does

Paste a link, get the media. Supports **YouTube** (with language selection when there's dubbing), **Instagram**, **Reddit** (including NSFW), **Threads**, **X/Twitter**, **Facebook**, and **any other site** via generic scraper (HTTP + Playwright in parallel, with yt-dlp generic and gallery-dl as fallbacks).

- Sends files up to **2 GB** via local Bot API (**4 GB** if the bot owner account is Telegram Premium)
- Reuses **Firefox** cookies to bypass blocks
- **Soft paywall bypass** (Googlebot UA + archive.ph) and article body extraction as caption
- **Text-only posts** (Threads, X) become formatted text messages with `📄 @user` + body + link
- 100% customizable user-facing messages via `messages.json`
- Per-chat and per-user whitelist
- 80+ tuning envs (timeouts, concurrency, quality, etc.)
- **"Try again"** button on failure + optional **page screenshot** prompt when the scraper finds nothing

---

## 🚀 Quick install

**Prerequisites:** Python 3.11+, ffmpeg, git. Optional: Deno (YouTube JS bypass), Firefox (cookies).

```bash
# Linux
sudo apt install -y python3.11 python3.11-venv ffmpeg git

# macOS
brew install python@3.11 ffmpeg git

# Windows (Chocolatey)
choco install python311 ffmpeg git -y
```

```bash
git clone https://github.com/YOUR_USERNAME/mediaraven.git
cd mediaraven
python3.11 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

---

## 🔧 Setup

### 1. Local Bot API (required — without it, Telegram caps at 50MB)

```bash
docker run -d --name telegram-bot-api -p 8081:8081 \
  -e TELEGRAM_API_ID=YOUR_API_ID -e TELEGRAM_API_HASH=YOUR_API_HASH \
  -e TELEGRAM_LOCAL=1 \
  -v telegram-bot-api-data:/var/lib/telegram-bot-api \
  aiogram/telegram-bot-api:latest
```

Get `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` at https://my.telegram.org → **API development tools**.

### 2. Telegram Bot

Talk to [@BotFather](https://t.me/BotFather) → `/newbot` → save the token.
Then: **Bot Settings → Group Privacy → OFF** (otherwise the bot only replies to direct commands).

### 3. Minimal `.env`

```bash
cp .env_example.en .env
```

```ini
TELEGRAM_BOT_TOKEN="123456789:ABC-DEF..."
ALLOWED_CHAT_ID=-1001234567890       # from https://api.telegram.org/bot<TOKEN>/getUpdates
ALLOWED_USER_IDS=123456789           # from @userinfobot
LOCAL_API_HOST=127.0.0.1:8081
BASE_DOWNLOAD_DIR=/absolute/path/downloads
```

> ⚠️ `BASE_DOWNLOAD_DIR` must be **absolute**.

Useful optionals:
- `IG_USER` / `IG_PASS` — throwaway Instagram account (fallback)
- `FIREFOX_PROFILE_PATH` — profile path to reuse cookies

### 4. Run

```bash
python mediaraven.py
```

---

## ⚙️ Customization

**Messages:** copy `messages.example.en.json` to `messages.json` (bot interface) or `log_messages.example.en.json` to `log_messages.json` (internal logs) and edit. Reloads on restart. Missing keys become `<<missing log key: X>>` (doesn't crash).

**Envs:** `.env_example.en` documents each one with sensible defaults. Highlights:

```ini
YTDLP_MAX_HEIGHT=1920          # 1080p (use 720 on slow connection, 4320 for 8K)
YTDLP_WORKERS=5                # simultaneous downloads
PW_CONCURRENCY=3               # simultaneous Playwright pages
SCRAPE_GALLERY_DL_ENABLE=yes   # gallery-dl in the generic scraper
SCRAPE_SCREENSHOT_FALLBACK=yes # offer screenshot when nothing works
SCRAPE_PAYWALL_BYPASS=yes      # Googlebot UA + archive.ph on soft paywalls
SCRAPE_ARTICLE_EXTRACT=yes     # extract article body as caption
LOG_LEVEL=DEBUG                # one-off debug
```

**Per-chat/user prompts:** `PROMPT_DOWNLOAD_OFF_CHATS`, `PROMPT_CAPTION_ON_USERS`, etc. — precedence `OFF_USERS > ON_USERS > OFF_CHATS > default`.

> 🔒 **Technical privacy:** what the user sees on Telegram doesn't expose `yt-dlp`/`Playwright`/`gallery-dl`. Only "downloading…" → "sending N files" → message disappears, or a generic failure message + retry. Logs (`bot.log`) preserve everything for debug.

<details>
<summary><b>🦊 Dockerized Firefox for cookies (recommended on a server)</b></summary>

Instead of using your personal Firefox, spin up an isolated one with web VNC:

```bash
docker run -d --name firefox-bot --restart unless-stopped \
  -p 5800:5800 -v /path/firefox-bot:/config --shm-size 2g \
  jlesage/firefox
```

Visit `http://localhost:5800`, log in to the sites, then point:

```bash
docker exec firefox-bot ls /config/.mozilla/firefox/ | grep default-release
# → xxxxxxxx.default-release
```

```ini
FIREFOX_PROFILE_PATH=/path/firefox-bot/.mozilla/firefox/xxxxxxxx.default-release
```

Use the **host** path (not the container path — the bot reads `cookies.sqlite` directly). You can stop the container when not needed; the bot keeps reading the file.
</details>

---

## 🧪 Tests

```bash
pip install -r requirements-dev.txt
pytest
```

---

## 📂 Structure

```
mediaraven.py            entry point
version.py               __version__
config.py                .env + 80+ envs + setup_logging
handlers.py              Telegram orchestration
telegram_io.py           media upload
utils.py                 download/ffmpeg/images
messages.json            user-facing strings
log_messages.json        log strings (~180 keys)
downloaders/
  dispatcher.py          orchestrator
  _platform.py _ytdlp.py _languages.py _caption.py
  instagram_embed.py     IG via /embed/ (no login)
  instagram.py           IG via Instagrapi (with login)
  reddit_json.py         public Reddit API
  reddit_playwright.py   headless Reddit (NSFW/spoilers)
  threads.py             Threads via JSON SSR
  x.py                   X via __INITIAL_STATE__ + GraphQL
  fallback.py            generic cascading scraper
  _scrape_helpers.py     URL rewrite, dedupe, parsers
lifecycle/               init, shutdown, refresh, metrics
```

---

## ❓ Common issues

- **`BASE_DOWNLOAD_DIR must be absolute`** → use a path starting with `/` or `C:/`.
- **Bot doesn't reply in groups** → turn off Group Privacy in BotFather.
- **`ffmpeg not found`** → install it; without it, IG posts with standalone music don't work.
- **`Invalid file http url specified`** → local Bot API isn't reachable; check Docker and `LOCAL_API_HOST`.
- **Instagram asks for login/challenge** → use a throwaway account; delete `ig_session.json` and restart if it locks up.

---

## 📜 License

[MIT](LICENSE). Respect each platform's ToS when downloading content.
