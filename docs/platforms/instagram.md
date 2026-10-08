# Instagram

Instagram tem **três caminhos** dedicados, em ordem:

## 1. IG Embed (sem login)

URL `instagram.com/p/<shortcode>/embed/captioned/` retorna HTML com `contextJSON` embedado. Funciona pra:

- ✅ Posts de foto única
- ✅ Carrosséis (vários itens)
- ✅ Reels
- ❌ Posts com **música externa** (precisa baixar áudio + mixar com ffmpeg → delega pro Instagrapi)
- ❌ Stories (URL diferente)

Não precisa login. Falha silenciosa se o post for privado / removido.

## 2. Instagrapi (com login)

Quando o embed não dá conta, tenta com a conta logada via `IG_USER`/`IG_PASS` (defina no `.env`).

- ✅ Tudo que o embed faz
- ✅ Posts com música externa (baixa áudio + mixa com foto pra gerar vídeo)
- ✅ Stories
- ✅ Reels que o embed não pegou

!!! warning "Use conta descartável"
    O Instagram bane contas que aparecem fazendo download em massa. Use uma conta secundária criada só pra isso. Sessão é persistida em `ig_session.json` (tem perms 600 automáticas).

## 3. gallery-dl (sessão do Firefox)

Quando o yt-dlp diz que o post **exige login** e o Instagrapi também não resolve, o bot tenta o `gallery-dl` com a **sessão web** dos cookies do Firefox (`FIREFOX_PROFILE_PATH`). Não depende da API do app — segue funcionando quando o login do Instagrapi está fora do ar (desde out/2026 o login novo leva 429, [instagrapi #2852](https://github.com/subzeroid/instagrapi/issues/2852)).

!!! danger "Não use o `sessionid` do navegador no Instagrapi"
    `login_by_sessionid` com o cookie do Firefox é rejeitado pela API do app e pode **deslogar a sessão do navegador** — a mesma que o gallery-dl usa.

## Configurações relevantes

| Chave | Default | O que faz |
|---|---|---|
| `IG_CAPTION_MAX` | `1000` | Máximo de chars do caption antes de truncar. Limite real do IG é 2200. |
| `IG_USER_AGENT` | `Instagram 219.0.0.12.117 Android` | UA usado pra baixar áudio (fora do instagrapi). Atualize se IG bloquear. |
| `IG_QUEUE_WARN_THRESHOLD` | `5` | Tamanho da fila do Instagrapi que dispara warning no log. |

## Caption

Formato padrão:

```
📄 @username
Texto do post (do edge_media_to_caption)

🔗 Link Original
```

## Foto + música

Posts onde a foto tem música externa: o IG embed retorna a foto, mas a música vem em um `progressive_download_url` que só o Instagrapi conhece. Fluxo:

1. Embed acha que é foto pura → não pega música → falha (semântica esperada).
2. Cai no Instagrapi → pega `media_info` + scaneia recursivamente o JSON pra achar `progressive_download_url`.
3. Baixa áudio puro via `aiohttp` com UA do Instagram.
4. Mixa via `ffmpeg loop -framerate 1 -i img.jpg -i audio.m4a -shortest`.
5. Resultado: `.mp4` com a foto estática + a música, no tempo certo (`audio_asset_start_time_in_ms` e `overlap_duration_in_ms` são respeitados).

## Falhas comuns

- **"login_required"** → bot tenta Instagrapi e depois gallery-dl com a sessão do Firefox. Se os dois falharem, confira se o Firefox ainda está logado. **Não** fique forçando re-login do Instagrapi: cada tentativa gasta o limite de login da conta (429).
- **"feedback_required"** → IG marcou como suspeito. Use VPN ou troque UA. Aguarde algumas horas.
- **Carrossel pega só primeira mídia** → bug do embed em carrosséis muito grandes; o Instagrapi cobre.
