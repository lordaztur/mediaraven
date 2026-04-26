# Configuração

## 1. Bot API local (obrigatório)

Sem ele, Telegram limita uploads a **50 MB**. Com ele, **2 GB** (4 GB se a conta dona do bot for Premium).

```bash
docker run -d --name telegram-bot-api -p 8081:8081 \
  -e TELEGRAM_API_ID=SEU_API_ID -e TELEGRAM_API_HASH=SEU_API_HASH \
  -e TELEGRAM_LOCAL=1 \
  -v telegram-bot-api-data:/var/lib/telegram-bot-api \
  aiogram/telegram-bot-api:latest
```

Pegue `TELEGRAM_API_ID` e `TELEGRAM_API_HASH` em **[my.telegram.org](https://my.telegram.org)** → API development tools.

## 2. Bot no Telegram

1. Fale com **[@BotFather](https://t.me/BotFather)** → `/newbot` → guarde o token.
2. **Bot Settings → Group Privacy → OFF** (senão o bot só responde a comandos diretos `/`).

## 3. `.env`

```bash
cp .env_example .env
```

Mínimo necessário:

```ini
TELEGRAM_BOT_TOKEN="123456789:ABC-DEF..."
ALLOWED_CHAT_ID=-1001234567890       # de https://api.telegram.org/bot<TOKEN>/getUpdates
ALLOWED_USER_IDS=123456789           # de @userinfobot
LOCAL_API_HOST=127.0.0.1:8081
BASE_DOWNLOAD_DIR=/caminho/absoluto/downloads
```

!!! warning "BASE_DOWNLOAD_DIR precisa ser absoluto"
    O bot rejeita paths relativos no boot. Linux: `/mnt/...`. Windows: `C:/...`.

### Bot público

Se quer expor o bot pra qualquer pessoa (público), adicione:

```ini
ALLOW_ALL=yes
```

Aí `ALLOWED_CHAT_ID` e `ALLOWED_USER_IDS` ficam ignorados — qualquer um que descobrir o handle do bot pode usar.

### Opcionais úteis

- `IG_USER` / `IG_PASS` — conta descartável do Instagram pro Instagrapi (fallback quando o yt-dlp falha).
- `FIREFOX_PROFILE_PATH` — caminho do perfil pra reaproveitar cookies. Veja [Cookies do Firefox](#cookies-do-firefox-recomendado-em-servidor) abaixo.

## 4. Customização (opcional)

Tudo que afeta UX (timeouts, qualidade, scraper, prompts) vive em `customization.json`, **não** no `.env`. Veja [Customização](../customization/index.md).

```bash
cp customization.example.json customization.json
# edita pra mudar defaults globais ou adicionar overrides por chat/user
```

## 5. Rodar

```bash
python mediaraven.py
```

Você verá no terminal:
```
🔌 MediaRaven v1.1.0 — Conectando ao Servidor Local em: http://127.0.0.1:8081/bot
🤖 Bot iniciado...
```

Pronto. Mande um link YouTube/Instagram/Reddit/X/Threads/Facebook ou qualquer site no chat — bot baixa e devolve.

## Cookies do Firefox (recomendado em servidor)

Se você tá rodando em servidor sem display, suba um Firefox dockerizado com VNC web:

```bash
docker run -d --name firefox-bot --restart unless-stopped \
  -p 5800:5800 -v /caminho/firefox-bot:/config --shm-size 2g \
  jlesage/firefox
```

Acesse `http://localhost:5800`, faça login nos sites que você quer (Instagram, Twitter, Reddit, sites com paywall), depois aponte:

```bash
docker exec firefox-bot ls /config/.mozilla/firefox/ | grep default-release
# → xxxxxxxx.default-release
```

```ini
FIREFOX_PROFILE_PATH=/caminho/firefox-bot/.mozilla/firefox/xxxxxxxx.default-release
```

!!! tip "Use o caminho do host"
    Não o do container — o bot lê o `cookies.sqlite` direto do disco. Pode parar o container quando não precisar; o bot continua lendo.
