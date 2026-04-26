# Customization

Anything affecting UX (timeouts, prompts, quality, scraper, etc.) is customizable **per chat** and **per user** via `customization.json`. System-level configs (token, paths, pools) live in `.env` and are not per-chat.

## Precedence

```
user > chat > customization.default > .env (module-level constant)
```

For each lookup, `cfg(key)` resolves in this order. If the key exists in the `user_id` override, uses that. Else checks `chat_id`. Else `default`. Else falls back to the `.env` constant.

## File structure

```bash
cp customization.example.en.json customization.json
```

```json
{
  "default": {
    "ASK_DL_TIMEOUT": 5.0,
    "YTDLP_MAX_HEIGHT": 1920
  },
  "chats": {
    "-1001234567890": {
      "YTDLP_MAX_HEIGHT": 720,
      "PROMPT_DOWNLOAD_ENABLED": false
    }
  },
  "users": {
    "555": {
      "ASK_CAPTION_DEFAULT": "yes",
      "YTDLP_MAX_HEIGHT": 4320
    }
  }
}
```

**In this example:**

| Scenario | Effective YTDLP_MAX_HEIGHT |
|---|---|
| User 555 sends link in any chat | 4320 (user override) |
| Other user sends link in chat -1001234567890 | 720 (chat override) |
| Other user in any other chat | 1920 (default) |

## Reload

The JSON is loaded at boot. To apply changes, **restart the bot** (no auto-watch).

## Internal ContextVar

Each request sets `request_context = (chat_id, user_id)` at the start of `handle_message`. Every `cfg(key)` call throughout the download reads this context. Works automatically across `await` chains and `loop.run_in_executor`.

## Pages

- [Config keys](keys.md) — all 42 customizable keys
- [UI messages](messages.md) — `messages.json` (user-facing text)
- [Log messages](logs.md) — `log_messages.json` (~180 log strings)
