# Internal helpers

Three functions do 90% of the configuration and message work:

## `cfg(key, chat_id=None, user_id=None)`

Resolves a customizable config. Precedence:

```
user > chat > customization.default > globals() (.env constant)
```

```python
from config import cfg

timeout = cfg("ASK_DL_TIMEOUT")  # uses request_context if called inside a request
height = cfg("YTDLP_MAX_HEIGHT", chat_id=-1001234, user_id=555)  # explicit
```

If neither ID is passed, reads from `request_context` ContextVar (set in `handle_message`).

If the key doesn't exist anywhere: returns `None`. Doesn't crash.

## `request_context`

ContextVar carrying `(chat_id, user_id)` during a request lifecycle.

```python
from config import request_context

request_context.set((chat_id, user_id))
# ... every cfg() call from here on (at any call stack depth)
# uses this context, INCLUDING in coroutines spawned via asyncio.gather
# or loop.run_in_executor.
```

ContextVars are auto-copied when you create a Task or run something in the executor (Python 3.7+ asyncio).

Set in:

- `handlers.handle_message` (new message arrives)
- `handlers.retry_callback` ("Try again" button)
- `handlers.process_media_request` (defensive)

## `msg(key, **kwargs)`

Reads string from `messages.json` (user-facing UI). Crashes with `KeyError` if the key doesn't exist — intentional, we want to know if `messages.example.json` is out of sync.

```python
from messages import msg

await status_msg.edit_text(msg("status.downloading", suffix=" [2/5]"))
```

Auto validation at boot: if `messages.json` has missing keys vs `messages.example.json`, logs warning.

## `lmsg(key, **kwargs)`

Reads string from `log_messages.json` (internal logs). **Doesn't crash** if key doesn't exist — returns `<<missing log key: X>>` (graceful degradation, log keeps appearing).

```python
from messages import lmsg

logger.info(lmsg("fallback.iniciando_scraping_multi", arg0=safe_url(url)))
```

Difference vs `msg()`: logs are for developers, better to degrade than crash the entire request for a missing key.

## `_build_caption(info_dict, url)` — in `_caption.py`

Universal caption builder. Receives dict with:

- `uploader` (or `uploader_id`, or `channel`) — first header
- `title` (or `alt_title`) — second header (in bold)
- `description` (or `comment`, or `caption`) — body

Returns `(caption_string, text_string)`. Caption has 1024 chars max (Telegram limit). Text has 4096 chars max (for `sendMessage` when no media).

Heuristics:

- **YouTube Shorts**: detected via `original_url`/`webpage_url` containing `/shorts/` → collapses title into desc
- **Redundant title**: if `title` is prefix of `description`, drops title (Shorts case)
- **Title without uploader**: promotes title to primary slot (articles without author)

## `should_show_prompt(kind, chat_id=None, user_id=None)`

Wrapper over `cfg()`:

```python
should_show_prompt("download")  # = cfg("PROMPT_DOWNLOAD_ENABLED")
should_show_prompt("caption")   # = cfg("PROMPT_CAPTION_ENABLED")
should_show_prompt("lang")      # = cfg("PROMPT_LANG_ENABLED")
```

Default `True` when key is unknown (vs `bool(None) = False`).

## `safe_url(url, max_length=None)` — in `utils.py`

Sanitizes URL for logging:

- Strips query string and fragment (hides tokens, secrets in URL)
- Truncates to `cfg("SAFE_URL_MAX_LENGTH")` chars with `"...(truncated)"` at end
- Returns `"<invalid-url>"` for non-string input

```python
safe_url("https://example.com/path?token=secret")  # → "https://example.com/path"
```

Always use `safe_url()` in logs instead of the raw URL.
