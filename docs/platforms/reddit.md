# Reddit

Reddit tem **dois caminhos** dedicados:

## 1. Reddit JSON (`reddit_json.py`)

Adiciona `.json?raw_json=1` no fim da URL e parseia. Cobre:

- ✅ Posts de imagem única
- ✅ Galerias (`media_metadata` + `gallery_data`)
- ✅ Reposts de outras subs
- ❌ Vídeos (delega pro yt-dlp porque DASH precisa de merge)
- ❌ Posts NSFW sem login → cai no Playwright
- ❌ Spoilers blurred → cai no Playwright

Cookies do Firefox são injetados na sessão `aiohttp` automaticamente quando disponíveis.

## 2. Reddit Playwright (`reddit_playwright.py`)

Quando o JSON falha (NSFW gate, spoilers, "no preview"), abre `old.reddit.com` no Playwright:

- ✅ Clica no botão NSFW automaticamente
- ✅ Remove blur de spoilers (incluindo Shadow DOM)
- ✅ Extrai mídia da Shadow Tree
- ❌ Vídeos (mesmo motivo: DASH)

## Configurações relevantes

| Chave | Default | O que faz |
|---|---|---|
| `REDDIT_JSON_UA` | UA do Firefox 123 | UA usado na API JSON. Reddit detecta UAs de bot — use um realista. |

## Caption

Vem de `title` + `selftext`:

```
📄 Título do post
Self-text aqui (se houver)...

🔗 Link Original
```

Username/subreddit não estão na caption hoje (poderia adicionar — abrir issue se quiser).

## Vídeos do Reddit

URL como `v.redd.it/xxx` ou post com `is_video=true` → o `reddit_json` detecta e **retorna vazio de propósito**, fazendo o dispatcher cair no `yt-dlp`. O yt-dlp baixa o stream DASH (vídeo + áudio separados) e mixa.

Caption do vídeo vem do `info_dict` do yt-dlp (title + description).

## NSFW

Bot consegue baixar NSFW se você tem cookies do Firefox de uma sessão logada com NSFW habilitado nas preferências do Reddit. Sem cookies, o `reddit_playwright` clica no botão NSFW automaticamente como fallback.

## Falhas comuns

- **403 / "blocked"** → você precisa cookies; Reddit fechou acesso anônimo a muita coisa em 2023+.
- **Galeria com algumas imagens faltando** → API às vezes retorna `media_metadata` parcial. Bot usa o que veio.
- **`v.redd.it` retorna sem áudio** → yt-dlp + ffmpeg deveriam mixar. Se não, ffmpeg não tá no PATH ou DASH falhou. Ative `LOG_LEVEL=DEBUG`.
