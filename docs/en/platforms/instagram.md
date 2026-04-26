# Instagram

Instagram has **two dedicated paths**, in order:

## 1. IG Embed (no login)

URL `instagram.com/p/<shortcode>/embed/captioned/` returns HTML with embedded `contextJSON`. Works for:

- ✅ Single photo posts
- ✅ Carousels (multiple items)
- ✅ Reels
- ❌ Posts with **external music** (needs to download audio + mix with ffmpeg → delegates to Instagrapi)
- ❌ Stories (different URL)

No login needed. Silent fallback if the post is private/removed.

## 2. Instagrapi (with login)

When the embed can't handle it, tries with the logged-in account via `IG_USER`/`IG_PASS` (set in `.env`).

- ✅ Everything embed does
- ✅ Posts with external music (downloads audio + mixes with photo to generate video)
- ✅ Stories
- ✅ Reels the embed didn't catch

!!! warning "Use a throwaway account"
    Instagram bans accounts that appear doing mass downloads. Use a secondary account created just for this. Session is persisted in `ig_session.json` (auto perms 600).

## Relevant configs

| Key | Default | What it does |
|---|---|---|
| `IG_CAPTION_MAX` | `1000` | Max chars of caption before truncating. IG's actual limit is 2200. |
| `IG_USER_AGENT` | `Instagram 219.0.0.12.117 Android` | UA used to download audio (outside instagrapi). Update if IG blocks. |
| `IG_QUEUE_WARN_THRESHOLD` | `5` | Instagrapi queue size that fires a warning log. |

## Caption

Standard format:

```
📄 @username
Post text (from edge_media_to_caption)

🔗 Original Link
```

## Photo + music

Posts where the photo has external music: the IG embed returns the photo, but the music comes in a `progressive_download_url` only Instagrapi knows. Flow:

1. Embed thinks it's a pure photo → doesn't catch music → fails (expected semantic).
2. Falls into Instagrapi → fetches `media_info` + recursively scans the JSON to find `progressive_download_url`.
3. Downloads pure audio via `aiohttp` with Instagram UA.
4. Mixes via `ffmpeg loop -framerate 1 -i img.jpg -i audio.m4a -shortest`.
5. Result: `.mp4` with the static photo + music, at the right time (`audio_asset_start_time_in_ms` and `overlap_duration_in_ms` are respected).

## Common failures

- **"login_required"** → bot tries Instagrapi. If it fails too, the account was probably blocked — delete `ig_session.json` and force re-login.
- **"feedback_required"** → IG flagged as suspicious. Use VPN or change UA. Wait a few hours.
- **Carousel only gets first media** → embed bug with very large carousels; Instagrapi covers it.
