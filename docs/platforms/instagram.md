# Instagram

Instagram tem **três caminhos** dedicados, em ordem:

## 1. IG Embed (sem login)

URL `instagram.com/p/<shortcode>/embed/captioned/` retorna HTML com `contextJSON` embedado. Funciona pra:

- ✅ Posts de foto única
- ✅ Carrosséis (vários itens)
- ✅ Reels
- ❌ Posts com **música externa** (precisa baixar áudio + mixar com ffmpeg → delega pra API web)
- ❌ Stories (URL diferente)

Não precisa login. Falha silenciosa se o post for privado / removido.

## 2. API web (sessão do Firefox)

Quando o embed não dá conta, o bot busca o post em `/api/v1/media/{pk}/info/` com a **sessão web** dos cookies do Firefox (`FIREFOX_PROFILE_PATH`) — a mesma que o yt-dlp e o gallery-dl usam. O JSON é o mesmo que a API do app devolve.

- ✅ Tudo que o embed faz
- ✅ Posts com música externa (baixa áudio + mixa com foto pra gerar vídeo)
- ✅ Stories (`/stories/<usuario>/<id>/`)
- ✅ Posts e reels que exigem login

O status aparece como `📸 Instagram Web (...)`. Sem sessão do Instagram no Firefox, esse caminho não roda — logue no Instagram pelo Firefox do perfil configurado.

!!! warning "Use conta descartável"
    O Instagram bane contas que aparecem fazendo download em massa. Use uma conta secundária, logada só no Firefox do bot.

!!! note "Por que não o instagrapi"
    Até a v1.2.35 este caminho era o instagrapi (API do app, login por senha). Desde out/2026 o login novo por senha leva **429** para todo mundo ([instagrapi #2852](https://github.com/subzeroid/instagrapi/issues/2852)), e a sessão web cobre o mesmo JSON — então ele saiu na v1.3.0, junto com `IG_USER`, `IG_PASS` e `ig_session.json`.

## 3. gallery-dl (sessão do Firefox)

Quando o yt-dlp diz que o post **exige login** e a API web também não resolve, o bot tenta o `gallery-dl` com a mesma sessão web, como último recurso.

## Configurações relevantes

| Chave | Default | O que faz |
|---|---|---|
| `IG_CAPTION_MAX` | `1000` | Máximo de chars do caption antes de truncar. Limite real do IG é 2200. |
| `IG_USER_AGENT` | `Instagram 219.0.0.12.117 Android` | UA usado pra baixar o áudio. Atualize se IG bloquear. |
| `IG_QUEUE_WARN_THRESHOLD` | `5` | Tamanho da fila do Instagram que dispara warning no log. |

## Caption

Formato padrão:

```
📄 @username
Texto do post (do edge_media_to_caption)

🔗 Link Original
```

## Foto + música

Posts onde a foto tem música externa: o IG embed retorna a foto, mas a música vem em um `progressive_download_url` que só a API (web ou do app) traz. Fluxo:

1. Embed detecta foto + música → desiste de propósito (pra não mandar foto sem som).
2. Cai na API web → pega o `media_info` + scaneia recursivamente o JSON pra achar `progressive_download_url`.
3. Baixa áudio puro via `aiohttp` com UA do Instagram.
4. Mixa via `ffmpeg loop -framerate 1 -i img.jpg -i audio.m4a -shortest`.
5. Resultado: `.mp4` com a foto estática + a música, no tempo certo (`audio_asset_start_time_in_ms` e `overlap_duration_in_ms` são respeitados).

## Falhas comuns

- **"login_required"** → bot tenta a API web e depois o gallery-dl, ambos com a sessão do Firefox. Se os dois falharem, confira se o Firefox ainda está logado no Instagram.
- **"feedback_required"** → IG marcou como suspeito. Use VPN ou troque UA. Aguarde algumas horas.
- **Carrossel pega só primeira mídia** → bug do embed em carrosséis muito grandes; a API web cobre.
