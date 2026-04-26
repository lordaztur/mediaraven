# Helpers internos

Três funções fazem 90% do trabalho de configuração e mensagens:

## `cfg(key, chat_id=None, user_id=None)`

Resolve uma config customizável. Precedência:

```
user > chat > customization.default > globals() (constante .env)
```

```python
from config import cfg

timeout = cfg("ASK_DL_TIMEOUT")  # usa request_context se chamado dentro de uma request
height = cfg("YTDLP_MAX_HEIGHT", chat_id=-1001234, user_id=555)  # explícito
```

Se nenhum dos IDs é passado, lê da `request_context` ContextVar (setada no `handle_message`).

Se a key não existe em lugar nenhum: retorna `None`. Não crasha.

## `request_context`

ContextVar que carrega `(chat_id, user_id)` durante o ciclo de vida de uma request.

```python
from config import request_context

request_context.set((chat_id, user_id))
# ... toda chamada a cfg() daqui em diante (em qualquer profundidade do call stack)
# usa esse contexto, INCLUSIVE em coroutines spawned via asyncio.gather ou loop.run_in_executor.
```

ContextVars são copiadas automaticamente quando você cria um Task ou roda algo no executor (Python 3.7+ asyncio).

Setada em:

- `handlers.handle_message` (mensagem nova chega)
- `handlers.retry_callback` (botão "Tentar novamente")
- `handlers.process_media_request` (defensivo)

## `msg(key, **kwargs)`

Lê string de `messages.json` (UI user-facing). Crasha com `KeyError` se a key não existe — proposital, queremos saber se o `messages.example.json` tá desatualizado.

```python
from messages import msg

await status_msg.edit_text(msg("status.downloading", suffix=" [2/5]"))
```

Validação automática no boot: se `messages.json` tem keys faltando vs `messages.example.json`, loga warning.

## `lmsg(key, **kwargs)`

Lê string de `log_messages.json` (logs internos). **Não crasha** se a key não existe — retorna `<<missing log key: X>>` (graceful degradation, log continua aparecendo).

```python
from messages import lmsg

logger.info(lmsg("fallback.iniciando_scraping_multi", arg0=safe_url(url)))
```

Diferença vs `msg()`: logs são pra desenvolvedores, melhor degradar do que crashar o request inteiro por uma key faltando.

## `_build_caption(info_dict, url)` — em `_caption.py`

Builder universal de caption. Recebe dict com:

- `uploader` (ou `uploader_id`, ou `channel`) — primeiro header
- `title` (ou `alt_title`) — segundo header (em bold)
- `description` (ou `comment`, ou `caption`) — corpo

Retorna `(caption_string, text_string)`. Caption tem 1024 chars max (limite Telegram). Text tem 4096 chars max (pra `sendMessage` quando sem mídia).

Heurísticas:

- **YouTube Shorts**: detecta via `original_url`/`webpage_url` contendo `/shorts/` → colapsa title na desc
- **Title redundante**: se `title` é prefixo de `description`, dropa title (Shorts case)
- **Title sem uploader**: promove title pro slot primário (artigos sem autor)

## `should_show_prompt(kind, chat_id=None, user_id=None)`

Wrapper sobre `cfg()`:

```python
should_show_prompt("download")  # = cfg("PROMPT_DOWNLOAD_ENABLED")
should_show_prompt("caption")   # = cfg("PROMPT_CAPTION_ENABLED")
should_show_prompt("lang")      # = cfg("PROMPT_LANG_ENABLED")
```

Default `True` quando key desconhecida (vs `bool(None) = False`).

## `safe_url(url, max_length=None)` — em `utils.py`

Sanitiza URL pra logging:

- Remove query string e fragment (esconde tokens, secrets em URL)
- Trunca pra `cfg("SAFE_URL_MAX_LENGTH")` chars com `"...(truncated)"` no fim
- Retorna `"<invalid-url>"` pra input não-string

```python
safe_url("https://example.com/path?token=secret")  # → "https://example.com/path"
```

Sempre use `safe_url()` em logs em vez da URL crua.
