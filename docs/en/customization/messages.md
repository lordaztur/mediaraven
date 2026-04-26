# UI Messages

Every string the bot sends to Telegram (buttons, prompts, status, callback alerts) lives in `messages.json`. You customize by translating, changing emoji, or tweaking tone.

```bash
cp messages.example.en.json messages.json
# edit at will
```

Reload: bot restart. Without `messages.json`, the bot uses `messages.example.en.json` as fallback.

## Structure

Top-level groups:

```json
{
  "startup":           { "token_missing": "...", "connecting": "...", "ready": "..." },
  "buttons":           { "download_yes": "...", "caption_yes": "...", ... },
  "prompts":           { "link_detected": "...", "caption_found": "...", ... },
  "callback_alerts":   { "dl_expired": "...", "dl_wrong_user": "...", ... },
  "status":            { "downloading": "...", "sending": "...", ... },
  "status_cycle":      [ "...", "...", "..." ],
  "downloader_status": { "ytdlp_success": "...", "scraper": "...", ... },
  "media_type_labels": { "ig_video": "...", "scraper_images": "...", ... },
  "caption":           { "link_original_label": "...", "title_prefix": "📄 ", ... },
  "reactions":         [ "🔥", "⚡", ... ]
}
```

## Placeholders

Strings can have `{var}` substituted at runtime via `.format(**kwargs)`. Examples:

- `prompts.link_detected: "🔗 Link detected{suffix}"` — `{suffix}` becomes `" [2/5]"` when there are multiple URLs
- `downloader_status.scraper: "🕸️ Scraper Deep Search ({media_type}) [{count} files]"` — `{media_type}` and `{count}` come from code

If you remove a placeholder the code expects, `msg()` will raise a format error. **Keep the `{vars}` in your override.**

## Languages

There's a `messages.example.json` file in Portuguese. To use:

```bash
cp messages.example.json messages.json
```

You can mix — copy the EN, translate some fields to another language, leave others in English.

## Reactions

The `reactions` array defines emojis the bot reacts to the original message with when starting to process. Bot picks one randomly per request:

```json
"reactions": ["🔥", "⚡", "👀", "🗿", "👨‍💻"]
```

Empty list (`[]`) disables reactions.

## Tip: status cycle

During download, the bot edits the status message cycling between texts in `status_cycle`. Default has 5 messages. Add/remove as many as you want:

```json
"status_cycle": [
  "📥 Downloading media...{suffix}",
  "📥 Processing content...{suffix}",
  "📥 Almost there...{suffix}",
  "📥 Hang tight, almost done...{suffix}"
]
```

Interval between rotations = `STATUS_CYCLE_INTERVAL` (in [Customization](keys.md)).
