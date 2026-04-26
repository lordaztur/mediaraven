# Threads

Extraction via **JSON SSR** served in initial HTML. Since Threads is a heavy SPA, curl_cffi can't handle it — the bot opens it in Playwright and parses the embedded JSON scripts.

## What works

- ✅ Single photo posts
- ✅ Video posts
- ✅ Carousels (mixed photo+video)
- ✅ Reposts (delegates to original post via `quoted_attachment_post`)
- ✅ **Text-only posts** → become formatted text messages (no media)
- ❌ Stories
- ❌ Deleted posts

## Relevant configs

| Key | Default | What it does |
|---|---|---|
| `THREADS_MIN_IMAGE_SIZE` | `500` | Min (px) of smallest dimension to keep — filters UI thumbnails. |
| `PW_GOTO_TIMEOUT_MS` | `25000` | Playwright `page.goto()` timeout. |

## Caption

Pulls `post["caption"]["text"]` + `post["user"]["username"]`:

```
📄 @username
Post text...

🔗 Original Link
```

## Text-only posts

When the post has no media but has text, the bot:

1. Builds the caption normally (`@user + text + link`)
2. Returns `(files=[], status="threads_text_only", caption=text)`
3. Handler detects `not files and caption` → sends caption as a **text message** (not as media caption)
4. Logged status: `🧵 Threads (Text)`

Details in [Text-only posts](../architecture/text-only-posts.md).

## Large carousels

Threads carousel has up to **10 items** (same Telegram `sendMediaGroup` limit). Bot downloads all in parallel and sends as a single album with the caption on the first item.

If the carousel mixes photo+video, Telegram accepts both in the same group — no problem.

## Common failures

- **"Post X not found in HTML JSON scripts"** → Threads changed the SSR format. Open an issue.
- **UI images being sent** → bump `THREADS_MIN_IMAGE_SIZE` (default 500px filters most).
- **Page doesn't load** → bump `PW_GOTO_TIMEOUT_MS`.
