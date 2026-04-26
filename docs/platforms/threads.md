# Threads

Extração via **JSON SSR** servido no HTML inicial. Como Threads é uma SPA pesada, curl_cffi não dá conta — o bot abre no Playwright e parseia os scripts JSON embedados.

## O que funciona

- ✅ Posts de foto única
- ✅ Posts de vídeo
- ✅ Carrosséis (foto+vídeo misturados)
- ✅ Reposts (delega pro post original via `quoted_attachment_post`)
- ✅ **Posts só com texto** → vira mensagem de texto formatada (sem mídia)
- ❌ Stories
- ❌ Posts deletados

## Configurações relevantes

| Chave | Default | O que faz |
|---|---|---|
| `THREADS_MIN_IMAGE_SIZE` | `500` | Mínimo (px) da menor dimensão pra manter — filtra thumbnails de UI. |
| `PW_GOTO_TIMEOUT_MS` | `25000` | Timeout do `page.goto()` no Playwright. |

## Caption

Pega `post["caption"]["text"]` + `post["user"]["username"]`:

```
📄 @username
Texto do post...

🔗 Link Original
```

## Posts só com texto

Quando o post não tem mídia mas tem texto, o bot:

1. Constrói a caption normalmente (`@user + texto + link`)
2. Retorna `(files=[], status="threads_text_only", caption=texto)`
3. O handler detecta `not files and caption` → envia caption como **mensagem de texto** (não como caption de mídia)
4. Status logado: `🧵 Threads (Texto)`

Detalhes em [Posts de texto](../architecture/text-only-posts.md).

## Carrosséis grandes

Threads carrossel tem até **10 itens** (mesmo limite do Telegram `sendMediaGroup`). Bot baixa todos em paralelo e envia em album único com a caption no primeiro item.

Se o carrossel tem foto+vídeo misturados, o Telegram aceita ambos no mesmo grupo — sem problema.

## Falhas comuns

- **"Post X não encontrado em scripts JSON do HTML"** → Threads mudou o formato do SSR. Abrir issue.
- **Imagens de UI sendo enviadas** → ajuste `THREADS_MIN_IMAGE_SIZE` pra cima (default 500px filtra a maioria).
- **Página não carrega** → aumente `PW_GOTO_TIMEOUT_MS`.
