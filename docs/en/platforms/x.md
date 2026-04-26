# X (Twitter)

Two-step extraction:

## 1. Guest path (anonymous)

curl_cffi (Chrome impersonation) fetches HTML, regex extracts `window.__INITIAL_STATE__={...}`, parser walks the JSON looking for the tweet by ID.

URL is normalized to `x.com` regardless of incoming domain (`twitter.com`, `fxtwitter.com`, `vxtwitter.com`, `fixupx.com`, `mobile.twitter.com`).

## 2. Authenticated path (Playwright)

If guest returns empty (protected tweet, or X blocking), opens in Playwright **with Firefox cookies** + intercepts requests to `/i/api/graphql/` to capture the full payload.

## What works

- ✅ Tweets with 1 image
- ✅ Tweets with up to 4 images (carousel)
- ✅ Tweets with video
- ✅ Tweets with GIF (extracted as MP4 video)
- ✅ **Text-only tweets** → become formatted text messages
- ✅ Resolves trailing `t.co` automatically (strips the shortened link from the end of text)
- ❌ Multi-tweet threads (only gets the pointed tweet)
- ❌ Spaces

## Caption

Bot extracts `screen_name` from multiple sources (in order):

1. `tweet["user"]["screen_name"]` (when `user` is an object)
2. `tweet["core"]["user_results"]["result"]["legacy"]["screen_name"]`
3. `data.entities.users.entities[<user_id>].screen_name` (lookup when `user` is just a string ID)
4. Username extracted from the URL (`/<username>/status/`) — except for `/i/status/` which is anonymous

Final caption:

```
📄 @username
Tweet text (without t.co trailing)

🔗 Original Link
```

## Text-only posts

Identical to Threads — `(files=[], non_empty_caption)` becomes a text message. Details in [Text-only posts](../architecture/text-only-posts.md).

## Text truncation

X tweets can have up to 4096 chars (premium) or 280 (free). `_build_caption` truncates to 1024 (Telegram caption limit) with "..." when exceeding.

When the tweet is text-only, it goes as `sendMessage` (4096 limit) — no need to truncate so much.

## Common failures

- **"No media found in tweet"** → text-only tweet falls into the "text-only" flow. If it still vanished, it's a quote/repost tweet.
- **"403 Forbidden"** → protected tweet (private account). Cookies from a logged-in Firefox session that follows the account solve it.
- **`/i/status/` without `@user` in caption** → bot tries lookup via `_resolve_user_dict()`. If still no user, it's because the JSON didn't bring user data.
