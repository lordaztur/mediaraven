# Logging

## Setup

`config.setup_logging()` is called once at boot:

- **Format**: `%(asctime)s - %(levelname)s - %(name)s:%(lineno)d - %(message)s`
- **Handlers**: `RotatingFileHandler(bot.log)` + `StreamHandler(stderr)`
- **Rotation**: 20 MB per file, 5 rotating files (`bot.log`, `bot.log.1`, ..., `bot.log.5`)
- **Captures warnings**: `logging.captureWarnings(True)` redirects the `warnings` module to the logger

## Levels

```ini
LOG_LEVEL=INFO    # default
LOG_LEVEL=DEBUG   # one-off debug, generates a lot of volume
LOG_LEVEL=WARNING # tight production
```

Levels follow standard hierarchy: `DEBUG < INFO < WARNING < ERROR < CRITICAL`. Setting to `WARNING` hides INFOs from scraper, etc.

## Silenced libs

When `LOG_LEVEL > DEBUG`, these loggers are forced to `WARNING`:

```python
_NOISY_LIBS = (
    'httpx', 'httpcore', 'urllib3', 'asyncio', 'PIL',
    'gallery_dl', 'telegram._utils', 'telegram.ext._updater',
    'apscheduler', 'instagrapi.mixins', 'public_request',
    'private_request', 'curl_cffi', 'playwright',
    'trafilatura', 'htmldate', 'courlan', 'charset_normalizer',
)
```

Without this, `httpx` alone generates ~3 lines per HTTP request from PTB to Telegram. With `LOG_LEVEL=DEBUG`, all come back (useful for investigating).

## Stack traces

Catches of "fatal" exceptions (unexpected, not network) use `exc_info=True` to include full stack trace:

```python
try:
    ...
except Exception as e:
    logger.error(lmsg("module.fatal_error", e=e), exc_info=True)
```

Catches of expected errors (network timeout, 404, paywall) **don't** use `exc_info=True` — stack trace only pollutes without adding info. Just gets the message.

Locations with `exc_info=True`:

- `telegram_io.send_downloaded_media` — upload failures
- `cookies.extract_firefox_cookies` — failure reading SQLite
- `utils.safe_cleanup`, `async_ffmpeg_remux`, `async_merge_audio_image` — filesystem/ffmpeg ops
- `lifecycle/instagram_login.py`, `lifecycle/playwright_refresh.py`, `lifecycle/startup.py`
- `downloaders/instagram.py` — Instagrapi errors
- `downloaders/reddit_json.py` — JSON parse errors
- `downloaders/fallback.py` — `❌ Erro Scraper Playwright`
- `handlers.process_media_request` — top-level exception handler

## Message customization

Every log message (180+) is customizable via `log_messages.json`. See [Log messages](../customization/logs.md).

Stack traces are NOT customizable — they come straight from Python.

## Where to read logs

Local: `bot.log` (in project directory). Rotated: `bot.log.1`, ..., `bot.log.5`.

```bash
# Tail in realtime
tail -f bot.log

# Search recent errors
grep -E "ERROR|WARNING" bot.log | tail -50

# Stats by level
grep -oE "INFO|WARNING|ERROR|DEBUG|CRITICAL" bot.log | sort | uniq -c
```

## Aggregated metrics

Every `METRICS_LOG_INTERVAL_MIN` (default 30 min), the bot logs a summary:

```
📊 metrics | youtube: 12 ok / 1 fail (avg 8.3s) | instagram: 5 ok / 0 fail | ...
```

Useful to see success rate per platform without parsing detailed logs.
