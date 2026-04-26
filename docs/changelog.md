# Changelog

## v1.1.0 — Customização granular + extração de artigo + bypass de paywall

**Maiores mudanças:**

- 🎚️ **42 configs customizáveis por chat e por usuário** via `customization.json`. Precedência `user > chat > default > .env`. Inclui timeouts, defaults de prompt, qualidade, scraper, caption, plataformas. Helper `cfg(key)` + ContextVar `request_context` permitem lookup transparente sem propagar IDs.
- 🌐 **180+ strings de log customizáveis** via `log_messages.json` (separado das mensagens UI). Helper `lmsg(key, **kw)` com fallback graceful pra keys ausentes.
- 🔒 **Bypass de paywall soft** (Googlebot UA + archive.ph) ativável via `SCRAPE_PAYWALL_BYPASS=yes`. Cobre NYT, Folha, FT, Estadão, etc.
- 📰 **Extração de artigo via trafilatura** como caption. Detecta automaticamente em qualquer URL com >= 300 chars de texto. Prompt opt-in dedicado (`ASK_ARTICLE_*`).
- 📝 **Posts só de texto** (Threads, X) viram mensagem de texto formatada (`📄 @user` + corpo + link), em vez de "falha".
- 🌍 **Documentação bilíngue PT/EN** + site de docs com MkDocs Material.
- 🛡️ **`ALLOW_ALL`** env pra rodar como bot público (whitelist ignorada).

**Refatorações:**

- `_build_caption` redesenhado pra ter `uploader` + `title` separados. YT Shorts detectados (não duplicam título no body). Threads/X agora usam `@username` no header.
- Scraper genérico paraleliza HTTP fast path + Playwright deep scrape (`asyncio.gather`).
- Logs com line numbers (`%(name)s:%(lineno)d`) + libs barulhentas silenciadas (httpx, urllib3, playwright, etc.).
- `exc_info=True` em ~10 catches de exceções fatais — stack traces preservados no log.
- Removido `MIN_CONTENT_LENGTH_BYTES` (filtro de 20KB nukava avatares legítimos).

**Adicionado:**

- `version.py` (`__version__ = "1.1.0"`)
- `customization.example.json` + `.example.en.json` (PT/EN, com `_doc_KEY` inline)
- `log_messages.example.json` + `.example.en.json`
- `messages.example.en.json`
- `.env_example.en`
- `README.en.md`
- `gallery-dl` como tier 3 do scraper
- `trafilatura` como dependência (extração de artigo)
- 5 badges adicionais no README (gallery-dl, trafilatura, instagrapi, curl-cffi, ffmpeg)

**Removido:**

- Envs `PROMPT_*_OFF_CHATS / ON_USERS / OFF_USERS` (substituídas por `PROMPT_*_ENABLED` no `customization.json`)
- 25+ envs movidas pro `customization.json` (todas as ASK_*, SCRAPE_*, MEDIA_GROUP_*, etc.)

## v1.0.0 — Lançamento inicial

- Bot do Telegram com Bot API local
- Plataformas: YouTube, Instagram, Reddit, Threads, X, Facebook
- Scraper genérico em cascata (HTTP + yt-dlp generic + gallery-dl + Playwright)
- Mensagens 100% customizáveis via `messages.json`
- Whitelist por chat e por usuário
- ~80 envs de tuning
