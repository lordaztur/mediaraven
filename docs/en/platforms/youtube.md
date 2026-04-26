# YouTube

## What works

- ✅ Public videos in any resolution up to `YTDLP_MAX_HEIGHT` (default 1080p; goes up to 4K/8K if you want)
- ✅ Shorts (URL automatically normalized from `/shorts/X` → `/watch?v=X`)
- ✅ Videos with **multiple dubbings** — bot asks which language you want
- ✅ JS challenge bypass via **Deno** (if installed)
- ✅ Firefox cookies used as fallback for age-restricted / private videos

## Relevant configs

All customizable per chat/user via [`customization.json`](../customization/keys.md):

| Key | Default | What it does |
|---|---|---|
| `YTDLP_MAX_HEIGHT` | `1920` | Max video height. 480/720/1080/1920/2160/4320. |
| `YTDLP_SOCKET_TIMEOUT` | `90` | yt-dlp socket timeout (seconds). |
| `YTDLP_YT_CLIENTS` | `"ios,mweb,web"` | CSV of extractor clients (order matters). |
| `ASK_LANG_TIMEOUT` | `10.0` | Time (s) to pick dubbing language. |
| `PROMPT_LANG_ENABLED` | `true` | If `false`, skips prompt and downloads original language. |

## Caption

Comes from `info_dict["title"]` + `info_dict["description"]` + `info_dict["uploader"]`/`uploader_id`.

Renders as:

```
📄 @channel_name
Video title (in bold)

Video description here...

🔗 Original Link
```

**YouTube Shorts** are detected via `original_url`/`webpage_url` — the title is collapsed into the description (no duplication) and only `@channel + body` appear.

## Multi-language

When the video has dubbing (audio tracks in multiple languages), the bot:

1. Lists available languages as inline buttons
2. Waits `ASK_LANG_TIMEOUT` seconds for choice
3. Default on timeout: `"original"` (primary track)

Whoever clicked the link can choose; others get a callback alert. If you disable (`PROMPT_LANG_ENABLED=false`), it directly downloads the original track.

## JS bypass via Deno

Some videos (especially mobile, or age-restricted) carry a JS challenge that yt-dlp needs to execute. If you have **Deno** in PATH, the bot detects it automatically and uses it to run the challenge.

```bash
# Linux
curl -fsSL https://deno.land/install.sh | sh
```

Without Deno the bot still tries — only fails in some specific cases.

## Common failures

- **"Sign in to confirm you're not a bot"** → cookies from a logged-in Firefox session solve it (`FIREFOX_PROFILE_PATH`).
- **Age-restricted video** → same thing, needs cookies from a logged-in adult session.
- **Live stream** → not supported (yt-dlp could, but bot doesn't handle it).
