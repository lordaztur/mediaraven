# Changelog

## v1.2.4 — Rate limiter pra evitar Flood control exceeded

**Major changes:**

- 🚦 **`AIORateLimiter` ativado** no `ApplicationBuilder`. Antes, quando Telegram retornava `RetryAfter: Flood control exceeded. Retry in N seconds` (em `edit_text`/`send_*`), a exception subia sem retry, e a request do user falhava. Agora o PTB respeita `Retry-After` em todos os requests automaticamente — espera N+ε e tenta de novo, sem propagar erro pro handler.

**Adicionado:**

- `builder.rate_limiter(AIORateLimiter())` em `mediaraven.py`
- `python-telegram-bot[rate-limiter]==22.7` em `requirements.txt` (puxa `aiolimiter` como dependência transitiva)

## v1.2.3 — GIFs vão como animação (não vídeo bugado)

**Major changes:**

- 🎞️ **GIFs agora vão via `send_animation`** em vez de `send_video`. Telegram tratava GIF como vídeo (sem autoplay, sem loop, com player feio). Com `send_animation`, vira animação nativa.
- 🎞️ **GIF é convertido pra MP4 (H.264) com ffmpeg antes de enviar**. Telegram converte GIF cru com perda de qualidade e renderiza pequeno; MP4 silencioso é o formato nativo de "GIF animado" do Telegram (mesmo que o cliente oficial usa) — qualidade muito melhor e tamanho cheio.
- 📐 Dimensões (`width`/`height`) extraídas do GIF original via PIL e passadas pro `send_animation` — garante renderização no tamanho correto mesmo quando ffmpeg não está disponível.

**Adicionado:**

- `_ANIMATION_EXTS_DEFAULT = ('.gif',)` em `config.py` (extensível via env `ANIMATION_EXTS_EXTRA`); `.gif` removido de `VIDEO_EXTS_DEFAULT`
- `async_gif_to_mp4(input_path, output_path, timeout=60)` em `utils.py` (ffmpeg `-c:v libx264 -pix_fmt yuv420p -an -movflags +faststart`)
- Helper `_get_image_dims` + branch `send_animation` em `telegram_io.py` (com fallback pro `.gif` original se ffmpeg falhar)
- 6 chaves de log `utils.gif_to_mp4_*` em PT/EN
- 3 testes em `tests/test_telegram_io_timeouts.py` (rota gif→animation, conversão bem-sucedida, fallback quando ffmpeg falha)

## v1.2.2 — Cap dinâmico pra HLS / lives finalizados do YouTube

**Major changes:**

- 📺 **Live finalizado do YouTube agora cabe**: lives que terminaram (`live_status: post_live`) só expõem formats HLS sem `filesize_approx` declarado. Antes o seletor caía no `best` e pegava 1094p (~3.8 GB pra 1h53min) → `File_parts_invalid` no upload. Agora, **pre-extract** descobre `duration` + formats e:
    - Aplica **cap dinâmico de bitrate** `[tbr<=N]` calculado por `(TELEGRAM_MAX_UPLOAD_MB × 8 × 1024) ÷ duration_s × 0.95`. Pra um live de 1h53min com cap 2 GB → `tbr<=2289 kbps`.
    - Detecta **HLS-only** (todos formats com vídeo são `m3u8_native`/`http_dash_segments`) e aplica cap conservador de altura via novo config `YTDLP_HLS_MAX_HEIGHT` (default 720).
- 🎯 **Format selector ordenado em tiers**: 1) DASH com filesize cap → 2) progressive com filesize cap → 3) progressive com tbr cap → 4) fallback puro. Garante que VOD normal continua escolhendo melhor qualidade dentro do limite.

**Refatorações:**

- Helpers extraídos em `downloaders/_ytdlp.py`: `_calc_max_tbr_kbps`, `_is_hls_only`, `_build_format_selector`, `_pre_extract`.
- `_apply_format_selection` aceita `info: Optional[dict]` e ajusta seletor dinamicamente.
- `_run_ytdlp_with_cookie_fallback` aceita `platform` opcional; quando passado, faz pre-extract por attempt (cookie/no-cookie) e re-aplica format selection com info real.

**Adicionado:**

- Config `YTDLP_HLS_MAX_HEIGHT` (default 720) em `customization.example.{json,en.json}`
- 3 chaves de log novas: `_ytdlp.hls_only_height_cap`, `_ytdlp.tbr_cap`, `_ytdlp.pre_extract_falhou`
- 15 testes em `tests/test_ytdlp_format_selection.py`

## v1.2.1 — Cap de upload pra evitar File_parts_invalid

**Major changes:**

- 📤 **Cap de tamanho no yt-dlp**: novo config `TELEGRAM_MAX_UPLOAD_MB` (default 2000) aplicado como `[filesize_approx<...M]` no seletor de formato. Antes, vídeos longos do YouTube em 1440p60 podiam dar > 2 GB e falhar com `BadRequest: File_parts_invalid` no upload (limite hard do Telegram pra bots; **Premium não afeta bots** — [tdlib/telegram-bot-api#583](https://github.com/tdlib/telegram-bot-api/issues/583)). Agora o seletor reserva ~100 MB pro stream de áudio + container e cai pra 1080p quando 1440p ultrapassaria o cap.
- 📤 **PTB local_mode**: `telegram_io.send_downloaded_media` agora passa o **path como string** em vez de file handle. Com servidor `telegram-bot-api --local`, PTB envia `file:///path` URI e o servidor lê do filesystem direto, sem multipart upload — evita timeouts em arquivos grandes mas dentro do limite. Documentação do `parse_file_input` confirma esse caminho (telegram/_utils/files.py:145-149).
- 📚 **Doc corrigida**: README/site/`.env_example` mencionavam "4 GB com Premium" — falso. Bots não podem ser Premium; o limite é 2 GB sempre.

**Refatorações:**

- `telegram_io.py` aplica `TELEGRAM_UPLOAD_TIMEOUT` em `read_timeout`/`write_timeout`/`connect_timeout` no path single-file (antes só o media_group aplicava).
- `_apply_format_selection` em `downloaders/_ytdlp.py` e `download_with_ytdlp_generic` em `downloaders/fallback.py` montam seletor com cap de filesize.

**Adicionado:**

- Config `TELEGRAM_MAX_UPLOAD_MB` em `customization.example.json` + `.example.en.json` (default 2000, min 50, max 2000)
- 5 testes em `tests/test_telegram_io_timeouts.py`

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
