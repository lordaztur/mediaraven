# Changelog

## v1.2.10 — Handler dedicado pro Facebook (carrosséis via gallery-dl) + validação de uploader no yt-dlp + ordem unificada de tentativas + cobertura ampliada do classifier

**Major changes:**

- 📘 **Novo handler dedicado pra Facebook em `downloaders/facebook.py`**. Pra qualquer link FB, o dispatcher agora tenta `gallery-dl` primeiro (com cookies do Firefox) — gallery-dl extrai carrosséis de imagens corretamente via API SSR, sem cair no scraping da timeline. Se gallery-dl achar arquivos → usa direto, status `📘 Facebook Gallery [N arquivos]`. Caso contrário, segue pro fluxo normal (yt-dlp pra vídeo). Confirmado: post de carrossel de 20 imagens que retornava vídeo errado agora vem completo (~250KB cada).
- 🛡️ **Validação `facebook_owner_mismatch` após yt-dlp success pra FB.** O extractor do Facebook no yt-dlp tem bug: quando o post original é só imagens, ele "encontra" qualquer vídeo embedado na página (sponsored/recomendação/comentário) e retorna como "sucesso". Resultado prático: user mandava link de carrossel e recebia vídeo aleatório de outro user. Agora: comparamos o `uploader_id` retornado pelo yt-dlp com o user_id numérico da URL (`facebook.com/<UID>/posts/...`). Se não baterem, descartamos o resultado e seguimos pros fallbacks.
- 🍪 **`_gallery_dl_run` agora injeta cookies do Firefox** (via `gdl_config.set(('extractor',), 'cookies', ('firefox', profile))`). Necessário pro FB; sem efeito colateral em outras plataformas (Pinterest/Imgur já funcionavam sem auth).
- 🖼️ **Carrosséis de imagens do Facebook agora baixam mesmo sem login.** A heurística `_drop_facebook_image_only` (introduzida no v1.0.x pra evitar 50+ thumbnails de UI quando user mandava link de vídeo) era agressiva demais: descartava QUALQUER post FB sem `.mp4` como "lixo de UI", o que incluía posts legítimos de fotos/carrosséis. **Função removida.** No lugar, expandi `is_junk_url` com hosts/paths conhecidos de UI do FB/Reddit (`static.xx.fbcdn.net`, `static.cdninstagram.com`, `styles.redditmedia.com`, `alb.reddit.com`, `id.rlcdn.com`, `/rsrc.php/`, `/safe_image.php`, `headshot`, `snoovatar`, `_profile`, `communityicon`, `profileicon`, `awardicon`) — agora UI é filtrada na fonte (antes do download) e imagens reais de posts passam.
- 🔁 **`_expand_attempts_with_impersonate` agora aplica o padrão "no_imp primeiro, imp como fallback" pra Facebook/Instagram também** (antes era só Reddit). Resultado pra FB/IG/Reddit: 4 tentativas `[no_cookie+no_imp, with_cookie+no_imp, no_cookie+imp, with_cookie+imp]`. Pra YouTube/outros (que não usam impersonate): 2 tentativas como antes. Motivo: testes manuais com Facebook mostraram que `impersonate=chrome` faz o FB devolver SPA pesada que yt-dlp não consegue parsear (`"Cannot parse data"`), enquanto sem impersonate retorna erro semântico (`"No video formats found"`) que o classifier pode reconhecer e responder corretamente.
- 🛑 **Facebook com "This video is only available for registered users" não estava sendo classificado pelo v1.2.9** — caía pro scraper e a heurística descartava tudo. Adicionados padrões: `only available for registered users`, `only available for registered`, `only available to registered`, `use --cookies`, `requires login`, `please log in`. Outros patterns novos: `this account is private` → `private`, `restricted to subscribers` → `members_only`, `this content isn't available`/`this tweet is unavailable`/`no video formats found`/`no media found`/`cannot parse data` → `unavailable`, `this video is no longer available` → `removed`, `too many requests` → `rate_limited`.

**Removido:**

- Função `_drop_facebook_image_only` em `downloaders/fallback.py` (e 4 call sites)
- Chave de log `fallback.facebook_image_only_dropped` (PT/EN)

**Adicionado:**

- Novo módulo `downloaders/facebook.py` com `download_facebook_gallery` e `facebook_owner_mismatch`
- Mensagem UI `downloader_status.facebook_gallery` (PT/EN) e 2 chaves de log `facebook.tentando_gallery_dl`, `facebook.gallery_dl_ok`, `dispatcher.facebook_owner_mismatch`
- 5 testes em `tests/test_facebook.py` (mismatch detection: no info / match / mismatch / share URL / sem uploader_id)
- 4 testes em `tests/test_ytdlp_format_selection.py` (registered users / use --cookies / 429 / private account)
- Teste `test_expand_attempts_facebook_and_instagram_also_try_no_imp_first` em `tests/test_ytdlp_format_selection.py`
- 3 testes em `tests/test_scrape_helpers.py` cobrindo os novos junk patterns (FB static, Reddit UI, real FB post image)

## v1.2.9 — Detecta erros não recuperáveis do yt-dlp (privado/removido/geo/etc.) e pula fallbacks

**Major changes:**

- 🛑 **Vídeo privado/removido/geo-bloqueado/etc. agora retorna mensagem clara** em vez de cair pro scraper genérico (que pegava o logo do YouTube/Google da página de erro como se fosse a mídia). Antes: link de vídeo privado → yt-dlp falha → scraper raspa página → manda logo do Google pro chat. Agora: yt-dlp captura o erro, classifica como `private`/`removed`/`geo_blocked`/`members_only`/`age_restricted`/`sign_in_required`/`live_not_started`/`unavailable`/`rate_limited`, e o dispatcher para na hora com mensagem específica.
- 🪵 **Captura de erros do yt-dlp via `logger=` no opts** em vez de mexer com `ignoreerrors`. Cada chamada de extração agora retorna `(info, error_messages)` quando `capture_errors=True`. O classifier compara contra 21 padrões conhecidos (case-insensitive) e retorna a categoria.

**Refatorações:**

- `_yt_dlp_extract` aceita `capture_errors: bool = False`; quando True retorna tupla `(info, errors)` em vez de só `info`
- Novo helper `_classify_ytdlp_errors(error_messages) -> Optional[str]` em `downloaders/_ytdlp.py` com padrões pra: `private`, `members_only`, `age_restricted`, `geo_blocked`, `removed`, `live_not_started`, `unavailable`, `sign_in_required`, `rate_limited`
- `_run_ytdlp_with_cookie_fallback` agora retorna `(files, info, unrecoverable_reason)`. Em vez de só listar arquivos, acumula erros de todas as tentativas e classifica no final
- `dispatcher.download_media` checa `unrecoverable_reason` antes de chamar fallbacks; se setado, retorna `msg("downloader_status.ytdlp_{reason}")` direto

**Adicionado:**

- 9 mensagens UI (PT/EN) em `downloader_status.ytdlp_{private,unavailable,removed,geo_blocked,members_only,age_restricted,sign_in_required,live_not_started,rate_limited}`
- 2 chaves de log: `_ytdlp.unrecoverable_reason`, `dispatcher.unrecoverable_skip_fallbacks`
- 9 testes em `tests/test_ytdlp_format_selection.py` (classifier por categoria + fallback None) + 1 teste de integração em `tests/test_dispatcher_integration.py`

## v1.2.8 — Threads: extrai mídia de `linked_inline_media` (posts media_type=19)

**Major changes:**

- 🧵 **Posts Threads com `media_type=19` (audio-augmented / format novo) tinham a mídia em `text_post_app_info.linked_inline_media`**, campo que `_extract_media` não cobria. O post tem `video_versions` no nível raiz como falsy/empty e `image_versions2.candidates: []`, daí o bot caía no branch "sem mídia, só caption" e respondia com texto. Agora `_extract_media` chama-se recursivamente em `linked_inline_media` (mesma estrutura: `carousel_media`/`video_versions`/`image_versions2`) antes do fallback de `share_info.quoted_post`. Mídia direta continua tendo precedência.

**Adicionado:**

- 3 testes em `tests/test_threads.py` (`linked_inline_media` com vídeo, com imagem, precedência da mídia direta)

## v1.2.7 — AIORateLimiter agora retenta de verdade (max_retries=3)

**Major changes:**

- 🐛 **No v1.2.4 o `AIORateLimiter` foi adicionado, mas com `max_retries=0` (default).** Resultado: ao bater em flood control (`Retry in N seconds`), o limiter só logava `Rate limit hit after maximum of 0 retries` e relançava a `RetryAfter`, fazendo a request original falhar e o handler explodir — exatamente o sintoma que o v1.2.4 tentou corrigir. O status_msg ficava travado em "baixando" porque o `_safe_edit` para "internal_error" também caía no mesmo flood. Agora `AIORateLimiter(max_retries=3)`: o limiter espera o `Retry-After` informado pelo Telegram e retenta até 3 vezes automaticamente.

## v1.2.6 — Reddit: tentativa sem impersonate primeiro (corrige IP-block)

**Major changes:**

- 🐛 **Reddit estava retornando `Your IP address is unable to access the Reddit API` quando o yt-dlp era chamado com `impersonate=ImpersonateTarget('chrome')`** (ativado pra Reddit no v1.0.x). Resultado: `bestvideo+bestaudio/best` falhava em qualquer post de vídeo, e o bot caía no scraper genérico que pegava avatares/ícones de comunidade em vez do vídeo. Agora, pra Reddit, as tentativas são expandidas pra `[no_cookie+no_imp, with_cookie+no_imp, no_cookie+imp, with_cookie+imp]` — o impersonate vira fallback em vez de default. Facebook/Instagram não mudam (continuam sempre com impersonate).
- 🧪 Confirmado manualmente: sem impersonate, yt-dlp baixa o vídeo do Reddit normalmente (~5 MB em 2s); com impersonate, retorna IP-block.

**Refatorações:**

- `_apply_format_selection` ganhou parâmetro `use_impersonate: bool = True` em `downloaders/_ytdlp.py` — quando False, faz `opts.pop('impersonate', None)` (gating só de adicionar não basta porque o dispatcher injeta impersonate em `base_opts` antes do loop, e o `current_opts.copy()` herda)
- Novo helper `_expand_attempts_with_impersonate(attempts, platform)` — pra Reddit retorna `[(m, False) for m in attempts] + [(m, True) for m in attempts]`; pra outros mantém `[(m, True) for m in attempts]`
- Loop principal de `_run_ytdlp_with_cookie_fallback` agora itera `(mode, use_imp)`, chama `_apply_format_selection` em toda iteração (não só quando há info do pre-extract — senão o gating é pulado), e pula `_pre_extract` pra Reddit (Reddit usa `format='bestvideo+bestaudio/best'` direto)
- Log da tentativa inclui sufixo `_imp`/`_noimp` no `mode` pra diagnose

**Adicionado:**

- 6 testes em `tests/test_ytdlp_format_selection.py` (impersonate gating + pop quando herdado + expand_attempts)

## v1.2.5 — Conversão automática de vídeo pra MP4 quando necessário

**Major changes:**

- 🎞️ **Vídeos em formato incompatível com player nativo do Telegram são convertidos pra MP4 antes de enviar.** Telegram só garante player de streaming pra MP4 H.264+AAC ([Bot API docs](https://core.telegram.org/bots/api#sendvideo): "other formats may be sent as Document"). Antes, `.webm`/`.mkv`/`.avi`/`.flv` caíam como documento sem player; agora viram MP4 antes do `send_video`.
- 🧠 **Estratégia smart (probe + remux/re-encode mínimo)**: `ffprobe` detecta vcodec/acodec do arquivo. Se já for H.264 → `-c:v copy` (instantâneo, sem perda). Se for AAC → `-c:a copy`. Caso contrário, re-encode só do stream incompatível. Se o remux falhar (codec não cabe em MP4 container), faz fallback automático pra re-encode completo.
- ✅ Extensões compatíveis (`.mp4`/`.m4v`/`.mov`) passam direto sem ffprobe nem ffmpeg.

**Adicionado:**

- `state.FFPROBE_PATH` + `init_ffmpeg` agora descobre tanto `ffmpeg` quanto `ffprobe` no PATH em `lifecycle/startup.py`
- `is_telegram_compatible_video_ext`, `async_ffprobe_codecs`, `async_ensure_telegram_video` em `utils.py`
- Helper `_ensure_video` em `telegram_io.py` (single-file e media_group)
- Config `VIDEO_CONVERT_TIMEOUT` (default 900s) em `config.py` + `customization.example.{json,en.json}`
- 13 chaves de log novas (PT/EN): `startup.ffprobe_*`, `utils.ffprobe_*`, `utils.video_convert_*`
- 11 testes em `tests/test_video_convert.py` + 4 testes em `tests/test_telegram_io_timeouts.py`

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
