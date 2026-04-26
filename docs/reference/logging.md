# Logging

## Setup

`config.setup_logging()` é chamado uma vez no boot:

- **Format**: `%(asctime)s - %(levelname)s - %(name)s:%(lineno)d - %(message)s`
- **Handlers**: `RotatingFileHandler(bot.log)` + `StreamHandler(stderr)`
- **Rotation**: 20 MB por arquivo, 5 arquivos rotativos (`bot.log`, `bot.log.1`, ..., `bot.log.5`)
- **Captura warnings**: `logging.captureWarnings(True)` redireciona o módulo `warnings` pro logger

## Níveis

```ini
LOG_LEVEL=INFO    # default
LOG_LEVEL=DEBUG   # debug pontual, gera muito volume
LOG_LEVEL=WARNING # produção apertada
```

Os níveis seguem hierarquia padrão: `DEBUG < INFO < WARNING < ERROR < CRITICAL`. Setar pra `WARNING` esconde os INFOs do scraper, etc.

## Libs silenciadas

Quando `LOG_LEVEL > DEBUG`, esses loggers são forçados pra `WARNING`:

```python
_NOISY_LIBS = (
    'httpx', 'httpcore', 'urllib3', 'asyncio', 'PIL',
    'gallery_dl', 'telegram._utils', 'telegram.ext._updater',
    'apscheduler', 'instagrapi.mixins', 'public_request',
    'private_request', 'curl_cffi', 'playwright',
    'trafilatura', 'htmldate', 'courlan', 'charset_normalizer',
)
```

Sem isso, `httpx` sozinho gera ~3 linhas por request HTTP do PTB pro Telegram. Com `LOG_LEVEL=DEBUG`, todas voltam (útil pra investigar).

## Stack traces

Catches de exceções "fatais" (não esperados, não rede) usam `exc_info=True` pra incluir stack trace completo:

```python
try:
    ...
except Exception as e:
    logger.error(lmsg("module.fatal_error", e=e), exc_info=True)
```

Catches de erros esperados (timeout de rede, 404, paywall) **não** usam `exc_info=True` — stack trace só polui sem agregar info. Pega só a mensagem.

Lugares com `exc_info=True`:

- `telegram_io.send_downloaded_media` — falhas no upload
- `cookies.extract_firefox_cookies` — falha lendo SQLite
- `utils.safe_cleanup`, `async_ffmpeg_remux`, `async_merge_audio_image` — operações de filesystem/ffmpeg
- `lifecycle/instagram_login.py`, `lifecycle/playwright_refresh.py`, `lifecycle/startup.py`
- `downloaders/instagram.py` — erros do Instagrapi
- `downloaders/reddit_json.py` — erros parseando JSON
- `downloaders/fallback.py` — `❌ Erro Scraper Playwright`
- `handlers.process_media_request` — top-level exception handler

## Customização das mensagens

Toda mensagem de log (180+) é customizável via `log_messages.json`. Veja [Mensagens de log](../customization/logs.md).

Stack traces NÃO são customizáveis — vêm direto do Python.

## Onde ler os logs

Local: `bot.log` (no diretório do projeto). Rotativos: `bot.log.1`, ..., `bot.log.5`.

```bash
# Tail em tempo real
tail -f bot.log

# Buscar erros recentes
grep -E "ERROR|WARNING" bot.log | tail -50

# Stats por nível
grep -oE "INFO|WARNING|ERROR|DEBUG|CRITICAL" bot.log | sort | uniq -c
```

## Métricas agregadas

A cada `METRICS_LOG_INTERVAL_MIN` (default 30 min), o bot loga um resumo:

```
📊 metrics | youtube: 12 ok / 1 fail (avg 8.3s) | instagram: 5 ok / 0 fail | ...
```

Útil pra ver taxa de sucesso por plataforma sem precisar parsear logs detalhados.
