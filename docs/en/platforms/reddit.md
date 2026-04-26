# Reddit

Reddit has **two dedicated paths**:

## 1. Reddit JSON (`reddit_json.py`)

Adds `.json?raw_json=1` to the URL and parses. Covers:

- ✅ Single image posts
- ✅ Galleries (`media_metadata` + `gallery_data`)
- ✅ Reposts from other subs
- ❌ Videos (delegates to yt-dlp because DASH needs merge)
- ❌ NSFW posts without login → falls into Playwright
- ❌ Spoilers blurred → falls into Playwright

Firefox cookies are auto-injected into the `aiohttp` session when available.

## 2. Reddit Playwright (`reddit_playwright.py`)

When JSON fails (NSFW gate, spoilers, "no preview"), opens `old.reddit.com` in Playwright:

- ✅ Auto-clicks the NSFW button
- ✅ Removes spoiler blur (including Shadow DOM)
- ✅ Extracts media from Shadow Tree
- ❌ Videos (same reason: DASH)

## Relevant configs

| Key | Default | What it does |
|---|---|---|
| `REDDIT_JSON_UA` | Firefox 123 UA | UA used in JSON API. Reddit detects bot UAs — use a realistic one. |

## Caption

Comes from `title` + `selftext`:

```
📄 Post title
Self-text here (if any)...

🔗 Original Link
```

Username/subreddit aren't in the caption today (could be added — open an issue if you want).

## Reddit videos

URL like `v.redd.it/xxx` or post with `is_video=true` → `reddit_json` detects and **returns empty on purpose**, making the dispatcher fall into `yt-dlp`. yt-dlp downloads the DASH stream (separate video + audio) and mixes.

Video caption comes from yt-dlp's `info_dict` (title + description).

## NSFW

Bot can download NSFW if you have Firefox cookies from a logged-in session with NSFW enabled in Reddit preferences. Without cookies, `reddit_playwright` clicks the NSFW button automatically as fallback.

## Common failures

- **403 / "blocked"** → you need cookies; Reddit closed anonymous access to a lot of stuff in 2023+.
- **Gallery with some images missing** → API sometimes returns partial `media_metadata`. Bot uses what came.
- **`v.redd.it` returns no audio** → yt-dlp + ffmpeg should mix. If not, ffmpeg isn't in PATH or DASH failed. Enable `LOG_LEVEL=DEBUG`.
