# YouTube

## O que funciona

- ✅ Vídeos públicos em qualquer resolução até `YTDLP_MAX_HEIGHT` (default 1080p; sobe pra 4K/8K se quiser)
- ✅ Shorts (URL automaticamente normalizada de `/shorts/X` → `/watch?v=X`)
- ✅ Vídeos com **múltiplas dublagens** — bot pergunta qual idioma você quer
- ✅ Bypass de JS challenges via **Deno** (se instalado)
- ✅ Cookies do Firefox usados como fallback pra vídeos com idade-restrita / privados

## Configurações relevantes

Todas customizáveis por chat/user via [`customization.json`](../customization/keys.md):

| Chave | Default | O que faz |
|---|---|---|
| `YTDLP_MAX_HEIGHT` | `1920` | Altura máxima do vídeo. 480/720/1080/1920/2160/4320. |
| `YTDLP_SOCKET_TIMEOUT` | `90` | Timeout socket do yt-dlp (segundos). |
| `YTDLP_YT_CLIENTS` | `"ios,mweb,web"` | CSV de clients do extractor (ordem importa). |
| `ASK_LANG_TIMEOUT` | `10.0` | Tempo (s) pra escolher dublagem. |
| `PROMPT_LANG_ENABLED` | `true` | Se `false`, pula prompt e baixa idioma original. |

## Caption

Vem de `info_dict["title"]` + `info_dict["description"]` + `info_dict["uploader"]`/`uploader_id`.

Renderiza como:

```
📄 @channel_name
Título do vídeo (em bold)

Descrição do vídeo aqui...

🔗 Link Original
```

**YouTube Shorts** são detectados via `original_url`/`webpage_url` — o título é colapsado na descrição (não duplica) e só `@channel + corpo` aparecem.

## Multi-idioma

Quando o vídeo tem dublagem (audio tracks em vários idiomas), o bot:

1. Lista os idiomas disponíveis em botões inline
2. Espera `ASK_LANG_TIMEOUT` segundos pela escolha
3. Default no timeout: `"original"` (faixa primária)

Quem clicou no link pode escolher; outros recebem callback alert. Se desabilitar (`PROMPT_LANG_ENABLED=false`), baixa direto a faixa original.

## Bypass JS via Deno

Alguns vídeos (especialmente em mobile, ou idade-restrita) trazem JS challenge que o yt-dlp precisa executar. Se você tem **Deno** no PATH, o bot detecta automaticamente e usa pra rodar o challenge.

```bash
# Linux
curl -fsSL https://deno.land/install.sh | sh
```

Sem Deno o bot ainda tenta — só falha em alguns casos específicos.

## Falhas comuns

- **"Sign in to confirm you're not a bot"** → cookies do Firefox de uma sessão logada resolvem (`FIREFOX_PROFILE_PATH`).
- **Vídeo idade-restrita** → mesma coisa, precisa cookies de sessão logada.
- **Live stream** → não suportado (yt-dlp poderia, mas bot não trata).
