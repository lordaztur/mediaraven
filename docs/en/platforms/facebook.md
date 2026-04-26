# Facebook

Facebook **has no dedicated downloader** — passes directly through `yt-dlp` generic. The bot does only one specific thing first: resolve share URLs (`fb.watch/X`, `m.facebook.com/share/X`) to canonical URL.

## What works well

- ✅ Single video (FB Watch, Reels, public video post)
- ✅ Video + long caption text
- ✅ Shortened URL `fb.watch` (auto-resolved)

## What does NOT work well

- ❌ **Photo carousel** — yt-dlp historically weak with FB carousels. Typically gets only one photo (the first or `og:image`).
- ❌ Private posts / login-required
- ❌ Stories

## When yt-dlp fails

Falls into generic scraper. But **`_drop_facebook_image_only`** discards image-only results from FB (heuristic to avoid sending FB UI chrome as if it were the post photo). Practical result: for FB image-only, the bot frequently returns "no media found".

## Caption

From `info_dict["description"]` extracted by yt-dlp. Same format as the others:

```
📄 Title
Description here...

🔗 Original Link
```

## Common failures

- **Post requires login** → FB blocked anonymous access to a lot of stuff in 2024+. Firefox cookies from a logged-in session help, but not 100%.
- **Carousel became single photo** → real yt-dlp limitation. No simple fix.
- **Video stalls in download** → bump `YTDLP_SOCKET_TIMEOUT` or change `YTDLP_YT_CLIENTS` (FB shares some clients with YouTube).
