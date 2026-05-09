# Changelog

## v1.2.0 — Pinterest, Kwai e captions em chunks

**Maiores mudanças:**

- 📌 **Pinterest**: links de pin (`pin.it/XXX`, `pinterest.com/pin/<id>`, regionais como `br.pinterest.com`) agora baixam só a mídia do pin via filtro `og:image`/`og:video`/JSON-LD com cap=1. Antes vinham 60+ imagens recomendadas da página.
- 🎬 **Kwai / SnackVideo**: shortlinks (`kwai-video.com/p/XXX`, `s.kw.ai`, `snackvideo.com/in`) resolvidos antes do yt-dlp; query string de tracking removida pra evitar erro `File name too long` no ID gerado pelo generic extractor. Hosts cobertos: `kwai-video.com`, `kwai.com`, `m.kwai.com`, `kw.ai`, `s.kw.ai`, `snackvideo.com`, `snackvideo.in`.
- ✂️ **Captions longas em chunks**: caption acima de 1024 chars não é mais truncada. A mídia vai sem caption e o texto completo é enviado em chunks de até 4096 chars (separadores preferidos: `\n\n` > `\n` > `". "` > `" "`). Caption que cabe em 1024 segue sendo colada na mídia normalmente. Sem duplicação de texto.
- 📰 **Filtro de mídia em artigos**: quando um artigo é detectado por trafilatura, só `og:image`/`og:video`/JSON-LD são considerados (cap=1), em vez de todas as imagens scrapadas. Antes vinham banners, ads, related articles.

**Refatorações:**

- `_build_caption` agora retorna tupla `(short, full)` propagada por todos os downloaders (Threads, X, Reddit, Instagram, Instagram Embed, fallback). `short` ≤ 1024, `full` sem truncamento.
- Novo helper `chunk_html_text(text, limit)` em `utils.py` quebra texto preservando limites semânticos (parágrafo > linha > frase > palavra).
- `_send_text_in_chunks` em `handlers.py` envia chunks em sequência com delay configurável.

**Adicionado:**

- `_is_pinterest()` em `downloaders/fallback.py`
- `_is_kwai_host()` + `_resolve_kwai_url()` em `downloaders/_platform.py`
- 4 chaves de log novas: `fallback.pinterest_media_filtered`, `_platform.resolvendo_kwai`, `_platform.kwai_resolvido`, `_platform.falha_ao_resolver_kwai`
- 16 testes novos: `tests/test_fallback_pinterest.py` (7), `tests/test_kwai_resolver.py` (9)
- 6 testes novos pra `chunk_html_text` em `tests/test_utils_helpers.py`

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
