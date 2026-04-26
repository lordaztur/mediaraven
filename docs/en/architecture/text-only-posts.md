# Text-only posts

Tweets / threads that **have no media** but have text don't disappear — the bot sends the text as a **formatted text message**.

## How it works

When `download_x` or `download_threads` detects the post has no media but has text:

```python
if not media_items:
    if caption:
        return [], "x_text_only", caption  # or "threads_text_only"
```

Dispatcher propagates `(files=[], status, caption)` (doesn't call `_finalize_success` because there are no files to enrich). Handler detects `not files and caption`:

```python
if not files and desc_text:
    await context.bot.send_message(
        chat_id=chat_id,
        text=desc_text,
        parse_mode='HTML',
        reply_to_message_id=message_id,
    )
```

Skips screenshot offer and retry prompt — text goes directly.

## Format

Same pattern as other captions:

```
📄 @username
Tweet/thread text here...

🔗 Original Link
```

The difference is it goes as `sendMessage` (4096 char limit) instead of `caption` (1024 char limit).

## Supported platforms

- ✅ **X (Twitter)** — `x_text_only`
- ✅ **Threads** — `threads_text_only`
- ❌ Instagram — Instagram doesn't have pure text posts
- ❌ Reddit — `reddit_json` returns `selftext` but as caption of something else
- ❌ Facebook — yt-dlp doesn't differentiate
- ❌ YouTube — n/a

To add support in other platforms, the downloader just needs to return `(files=[], status, caption)` when it has text without media. Handler already handles it.

## Logs

```
🐦 X (Text)
🧵 Threads (Text)
```

## Common failures

- **Text-only tweet didn't come** → tweet is a quote/repost with media in another tweet. The bot fetches the tweet pointed by the URL.
- **Truncated message** → text exceeded 4096 chars from `sendMessage`. Premium tweets can have up to 4096 but the bot truncates. Solution: increase truncation in `_build_caption`.
- **HTML didn't render** → special chars without escape. Bot escapes via `html.escape()`. If it still breaks, it's zero-width or similar character.
