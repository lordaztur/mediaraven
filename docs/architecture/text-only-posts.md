# Posts só com texto

Tweets / threads que **não têm mídia** mas têm texto não somem — o bot envia o texto como **mensagem de texto formatada**.

## Como funciona

Quando `download_x` ou `download_threads` detecta que o post não tem mídia mas tem texto:

```python
if not media_items:
    if caption:
        return [], "x_text_only", caption  # ou "threads_text_only"
```

O dispatcher propaga `(files=[], status, caption)` (não chama o `_finalize_success` porque não tem files pra enriquecer). O handler detecta `not files and caption`:

```python
if not files and desc_text:
    await context.bot.send_message(
        chat_id=chat_id,
        text=desc_text,
        parse_mode='HTML',
        reply_to_message_id=message_id,
    )
```

Pula o screenshot offer e o retry prompt — texto vai direto.

## Formato

Mesmo padrão dos outros captions:

```
📄 @username
Texto do tweet/thread aqui...

🔗 Link Original
```

A diferença é que vai como `sendMessage` (limite 4096 chars) em vez de `caption` (limite 1024 chars).

## Plataformas suportadas

- ✅ **X (Twitter)** — `x_text_only`
- ✅ **Threads** — `threads_text_only`
- ❌ Instagram — Instagram não tem post de texto puro
- ❌ Reddit — `reddit_json` retorna `selftext` mas como caption de outra coisa
- ❌ Facebook — yt-dlp não diferencia
- ❌ YouTube — n/a

Pra adicionar suporte em outras plataformas, basta o downloader retornar `(files=[], status, caption)` quando tem texto sem mídia. Handler já trata.

## Logs

```
🐦 X (Texto)
🧵 Threads (Texto)
```

## Falhas comuns

- **Tweet só texto não veio** → tweet é de quote/repost com mídia em outro tweet. O bot pega o tweet apontado pela URL.
- **Mensagem cortada** → texto excedeu 4096 chars do `sendMessage`. Tweets premium podem ter até 4096 mas o bot trunca. Solução: aumentar truncação no `_build_caption`.
- **HTML não renderizou** → caracteres especiais sem escape. Bot escapa via `html.escape()`. Se ainda quebra, é caractere zero-width ou similar.
