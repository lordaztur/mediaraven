# MediaRaven

**Telegram bot that downloads any media from the internet and sends it straight to your chat.**

Paste a link, get the media. MediaRaven runs locally, uses its own Bot API (up to 4 GB per file if the owner account is Telegram Premium), reuses Firefox cookies, bypasses soft paywalls, and has a generic cascading scraper for obscure sites.

## Why it exists

Public download bots have tight limits (50 MB), queues, ads, and when they work they expose your gallery content to a third party. MediaRaven is the opposite: runs on your server, with your account, your rules. 1 GB video? No problem. Pinterest gallery with 30 images? Works. Text-only tweet? Becomes formatted message. News article behind paywall? Tries Googlebot UA + archive.ph.

## Supported platforms

| Platform | Strategy | Text-only? |
|---|---|---|
| YouTube | yt-dlp (with Deno JS bypass) | — |
| Instagram | Embed → Instagrapi (login) | — |
| Reddit | JSON API → Playwright (NSFW) | — |
| Threads | Playwright JSON SSR | ✅ |
| X (Twitter) | `__INITIAL_STATE__` + GraphQL | ✅ |
| Facebook | yt-dlp generic | — |
| Anything else | Generic scraper (HTTP + Playwright + yt-dlp + gallery-dl) | — |

## v1.1.0 highlights

- 🌍 Local Bot API — uploads up to 2 GB (4 GB with Premium)
- 🦊 Automatic Firefox cookies to bypass blocks
- 🔒 Soft paywall bypass (Googlebot UA + archive.ph)
- 📰 Article body extraction via trafilatura as caption
- 📝 Text-only posts (Threads, X) become formatted messages
- 🎚️ **42 customizable configs per chat and per user** ([learn more](customization/index.md))
- 🌐 100% customizable messages (UI + logs)
- 📊 ~250 tests, detailed observability in logs

## Where to start

- **I want to run the bot** → [Installation](getting-started/install.md)
- **I want to understand each platform** → [Platforms](platforms/index.md)
- **I want to change timeouts/quality for a specific chat** → [Customization](customization/index.md)
- **I want to understand the scraper architecture** → [How it works](architecture/index.md)
- **Something went wrong** → [Troubleshooting](troubleshooting.md)
