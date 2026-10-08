# Instagram

Instagram has **three dedicated paths**, in order:

## 1. IG Embed (no login)

URL `instagram.com/p/<shortcode>/embed/captioned/` returns HTML with embedded `contextJSON`. Works for:

- ✅ Single-photo posts
- ✅ Carousels (multiple items)
- ✅ Reels
- ❌ Posts with **external music** (needs audio download + ffmpeg mix → delegates to the web API)
- ❌ Stories (different URL)

No login needed. Fails silently if the post is private / removed.

## 2. Web API (Firefox session)

When the embed can't handle it, the bot fetches the post at `/api/v1/media/{pk}/info/` with the **web session** from the Firefox cookies (`FIREFOX_PROFILE_PATH`) — the same one yt-dlp and gallery-dl use. The JSON is the same the app API returns.

- ✅ Everything the embed does
- ✅ Posts with external music (downloads audio + mixes with the photo into a video)
- ✅ Stories (`/stories/<user>/<id>/`)
- ✅ Login-required posts and reels

Status shows as `📸 Instagram Web (...)`. Without an Instagram session in Firefox this path doesn't run — log in to Instagram in the configured Firefox profile.

!!! warning "Use a throwaway account"
    Instagram bans accounts that appear doing mass downloads. Use a secondary account, logged in only in the bot's Firefox.

!!! note "Why not instagrapi"
    Up to v1.2.35 this path was instagrapi (app API, password login). Since Oct/2026 fresh password logins get **429** for everyone ([instagrapi #2852](https://github.com/subzeroid/instagrapi/issues/2852)), and the web session covers the same JSON — so it was removed in v1.3.0, along with `IG_USER`, `IG_PASS` and `ig_session.json`.

## 3. gallery-dl (Firefox session)

When yt-dlp says the post **requires login** and the web API can't resolve it either, the bot tries `gallery-dl` with the same web session, as a last resort.

## Relevant configs

| Key | Default | What it does |
|---|---|---|
| `IG_CAPTION_MAX` | `1000` | Max caption chars before truncating. IG's real limit is 2200. |
| `IG_USER_AGENT` | `Instagram 219.0.0.12.117 Android` | UA used to download the audio. Update if IG blocks. |
| `IG_QUEUE_WARN_THRESHOLD` | `5` | Instagram queue size that triggers a log warning. |

## Caption

Standard format:

```
📄 @username
Post text (from edge_media_to_caption)

🔗 Original Link
```

## Photo + music

Posts where the photo has external music: the IG embed returns the photo, but the music comes in a `progressive_download_url` that only the API (web or app) returns. Flow:

1. Embed detects photo + music → deliberately gives up (so it won't send a silent photo).
2. Falls to the web API → gets the `media_info` + recursively scans the JSON for `progressive_download_url`.
3. Downloads the raw audio via `aiohttp` with an Instagram UA.
4. Mixes via `ffmpeg loop -framerate 1 -i img.jpg -i audio.m4a -shortest`.
5. Result: `.mp4` with the static photo + the music, on the right segment (`audio_asset_start_time_in_ms` and `overlap_duration_in_ms` are honored).

## Common failures

- **"login_required"** → bot tries the web API, then gallery-dl, both with the Firefox session. If both fail, check that Firefox is still logged in to Instagram.
- **"feedback_required"** → IG flagged as suspicious. Use a VPN or change UA. Wait a few hours.
- **Carousel only gets first media** → embed bug with very large carousels; the web API covers it.
