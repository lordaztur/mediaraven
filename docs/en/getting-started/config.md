# Configuration

## 1. Local Bot API (required)

Without it, Telegram caps uploads at **50 MB**. With it, **2 GB** (4 GB if the bot owner account is Premium).

```bash
docker run -d --name telegram-bot-api -p 8081:8081 \
  -e TELEGRAM_API_ID=YOUR_API_ID -e TELEGRAM_API_HASH=YOUR_API_HASH \
  -e TELEGRAM_LOCAL=1 \
  -v telegram-bot-api-data:/var/lib/telegram-bot-api \
  aiogram/telegram-bot-api:latest
```

Get `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` at **[my.telegram.org](https://my.telegram.org)** → API development tools.

## 2. Telegram Bot

1. Talk to **[@BotFather](https://t.me/BotFather)** → `/newbot` → save the token.
2. **Bot Settings → Group Privacy → OFF** (otherwise the bot only replies to direct `/` commands).

## 3. `.env`

```bash
cp .env_example.en .env
```

Minimum required:

```ini
TELEGRAM_BOT_TOKEN="123456789:ABC-DEF..."
ALLOWED_CHAT_ID=-1001234567890       # from https://api.telegram.org/bot<TOKEN>/getUpdates
ALLOWED_USER_IDS=123456789           # from @userinfobot
LOCAL_API_HOST=127.0.0.1:8081
BASE_DOWNLOAD_DIR=/absolute/path/downloads
```

!!! warning "BASE_DOWNLOAD_DIR must be absolute"
    The bot rejects relative paths at boot. Linux: `/mnt/...`. Windows: `C:/...`.

### Public bot

If you want to expose the bot to anyone (public), add:

```ini
ALLOW_ALL=yes
```

Then `ALLOWED_CHAT_ID` and `ALLOWED_USER_IDS` are ignored — anyone who finds the bot's handle can use it.

### Useful optionals

- `IG_USER` / `IG_PASS` — throwaway Instagram account for Instagrapi (fallback when yt-dlp fails).
- `FIREFOX_PROFILE_PATH` — profile path to reuse cookies. See [Firefox cookies](#firefox-cookies-recommended-on-server) below.

## 4. Customization (optional)

Anything affecting UX (timeouts, quality, scraper, prompts) lives in `customization.json`, **not** in `.env`. See [Customization](../customization/index.md).

```bash
cp customization.example.en.json customization.json
# edit to change global defaults or add per-chat/user overrides
```

## 5. Run

```bash
python mediaraven.py
```

You'll see in the terminal:
```
🔌 MediaRaven v1.1.0 — Connecting to Local Server at: http://127.0.0.1:8081/bot
🤖 Bot started...
```

Done. Send a YouTube/Instagram/Reddit/X/Threads/Facebook link or any site in chat — bot downloads and returns.

## Firefox cookies (recommended on server)

If you're running on a server without display, spin up a dockerized Firefox with web VNC:

```bash
docker run -d --name firefox-bot --restart unless-stopped \
  -p 5800:5800 -v /path/firefox-bot:/config --shm-size 2g \
  jlesage/firefox
```

Visit `http://localhost:5800`, log in to the sites you want (Instagram, Twitter, Reddit, paywalled sites), then point:

```bash
docker exec firefox-bot ls /config/.mozilla/firefox/ | grep default-release
# → xxxxxxxx.default-release
```

```ini
FIREFOX_PROFILE_PATH=/path/firefox-bot/.mozilla/firefox/xxxxxxxx.default-release
```

!!! tip "Use the host path"
    Not the container path — the bot reads `cookies.sqlite` directly from disk. You can stop the container when not needed; the bot keeps reading.
