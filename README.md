<div align="center">

<img src="assets/banner.svg" alt="MediaRaven" width="720"/>

**Bot do Telegram que baixa qualquer mídia da internet e envia direto no seu chat.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-22.7-26A5E4?style=flat&logo=telegram&logoColor=white)](https://python-telegram-bot.org/)
[![yt-dlp](https://img.shields.io/badge/powered%20by-yt--dlp-red?style=flat)](https://github.com/yt-dlp/yt-dlp)
[![Playwright](https://img.shields.io/badge/playwright-1.58-2EAD33?style=flat&logo=playwright&logoColor=white)](https://playwright.dev/)
[![gallery-dl](https://img.shields.io/badge/gallery--dl-1.32-9333EA?style=flat)](https://github.com/mikf/gallery-dl)
[![trafilatura](https://img.shields.io/badge/trafilatura-2.0-1B6B93?style=flat)](https://github.com/adbar/trafilatura)
[![instagrapi](https://img.shields.io/badge/instagrapi-2.3-E4405F?style=flat&logo=instagram&logoColor=white)](https://github.com/subzeroid/instagrapi)
[![curl-cffi](https://img.shields.io/badge/curl--cffi-0.14-073551?style=flat&logo=curl&logoColor=white)](https://github.com/lexiforest/curl_cffi)
[![ffmpeg](https://img.shields.io/badge/ffmpeg-required-007808?style=flat&logo=ffmpeg&logoColor=white)](https://ffmpeg.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat)](LICENSE)

🇺🇸 [English](README.en.md)

</div>

---

## ✨ O que ele faz

Cole um link, recebe a mídia. Suporta **YouTube** (com seleção de idioma quando há dublagem), **Instagram**, **Reddit** (incluindo NSFW), **Threads**, **X/Twitter**, **Facebook** e **qualquer outro site** via scraper genérico (HTTP + Playwright em paralelo, com yt-dlp generic e gallery-dl como fallbacks).

- Envia arquivos até **2 GB** via Bot API local (**4 GB** se a conta dona do bot for Telegram Premium)
- Reaproveita cookies do **Firefox** pra burlar bloqueios
- **Bypass de paywall soft** (Googlebot UA + archive.ph) e extração do corpo do artigo como caption
- **Posts só de texto** (Threads, X) viram mensagem de texto formatada com `📄 @user` + corpo + link
- Mensagens user-facing 100% customizáveis via `messages.json`
- Whitelist por chat e por usuário
- 80+ envs de tuning (timeouts, concorrência, qualidade, etc.)
- Botão **"Tentar novamente"** em falha + prompt opcional de **screenshot da página** quando o scraper não acha mídia

---

## 🚀 Instalação rápida

**Pré-requisitos:** Python 3.11+, ffmpeg, git. Opcional: Deno (bypass JS do YouTube), Firefox (cookies).

```bash
# Linux
sudo apt install -y python3.11 python3.11-venv ffmpeg git

# macOS
brew install python@3.11 ffmpeg git

# Windows (Chocolatey)
choco install python311 ffmpeg git -y
```

```bash
git clone https://github.com/SEU_USUARIO/mediaraven.git
cd mediaraven
python3.11 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

---

## 🔧 Setup

### 1. Bot API local (obrigatório — sem ele, Telegram limita a 50MB)

```bash
docker run -d --name telegram-bot-api -p 8081:8081 \
  -e TELEGRAM_API_ID=SEU_API_ID -e TELEGRAM_API_HASH=SEU_API_HASH \
  -e TELEGRAM_LOCAL=1 \
  -v telegram-bot-api-data:/var/lib/telegram-bot-api \
  aiogram/telegram-bot-api:latest
```

Pegue `TELEGRAM_API_ID` e `TELEGRAM_API_HASH` em https://my.telegram.org → **API development tools**.

### 2. Bot no Telegram

Fale com [@BotFather](https://t.me/BotFather) → `/newbot` → guarde o token.
Depois: **Bot Settings → Group Privacy → OFF** (senão o bot só responde a comandos diretos).

### 3. `.env` mínimo

```bash
cp .env_example .env
```

```ini
TELEGRAM_BOT_TOKEN="123456789:ABC-DEF..."
ALLOWED_CHAT_ID=-1001234567890       # de https://api.telegram.org/bot<TOKEN>/getUpdates
ALLOWED_USER_IDS=123456789           # de @userinfobot
LOCAL_API_HOST=127.0.0.1:8081
BASE_DOWNLOAD_DIR=/caminho/absoluto/downloads
```

> ⚠️ `BASE_DOWNLOAD_DIR` precisa ser **absoluto**.

Opcionais úteis:
- `IG_USER` / `IG_PASS` — conta descartável do Instagram (fallback)
- `FIREFOX_PROFILE_PATH` — caminho do perfil pra reaproveitar cookies

### 4. Rodar

```bash
python mediaraven.py
```

---

## ⚙️ Customização

**Mensagens:** copie `messages.example.json` pra `messages.json` (interface do bot) ou `log_messages.example.json` pra `log_messages.json` (logs internos) e edite. Recarrega no restart. Keys faltando viram `<<missing log key: X>>` (não crasha).

**Customização por chat/usuário:** copie `customization.example.json` pra `customization.json` e adicione overrides em `chats` (por chat_id) ou `users` (por user_id). Precedência: **user > chat > default > .env**. Exemplo: forçar 720p e desativar prompt de download para um chat específico:
```json
{
  "default": { "YTDLP_MAX_HEIGHT": 1920 },
  "chats": { "-100123": { "YTDLP_MAX_HEIGHT": 720, "PROMPT_DOWNLOAD_ENABLED": false } },
  "users": { "555": { "ASK_CAPTION_DEFAULT": "yes" } }
}
```

**Envs (system-level):** `.env_example` documenta auth, paths, pools e sessões. Destaques:

```ini
ALLOW_ALL=no                   # "yes" libera o bot pra qualquer chat/usuário
YTDLP_WORKERS=5                # downloads simultâneos
PW_CONCURRENCY=3               # páginas Playwright simultâneas
LOG_LEVEL=DEBUG                # debug pontual
```

Tudo que afeta UX (timeouts, prompts, qualidade, scraper, etc. — 42 chaves) vive em `customization.example.json`.


> 🔒 **Privacidade técnica:** o que o usuário vê no Telegram não expõe `yt-dlp`/`Playwright`/`gallery-dl`. Só "baixando…" → "enviando N arquivos" → mensagem some, ou uma mensagem genérica de falha + retry. Os logs (`bot.log`) preservam tudo pra debug.

<details>
<summary><b>🦊 Firefox dockerizado pra cookies (recomendado em servidor)</b></summary>

Em vez de usar seu Firefox pessoal, suba um isolado com VNC web:

```bash
docker run -d --name firefox-bot --restart unless-stopped \
  -p 5800:5800 -v /caminho/firefox-bot:/config --shm-size 2g \
  jlesage/firefox
```

Acesse `http://localhost:5800`, faça login nos sites, depois aponte:

```bash
docker exec firefox-bot ls /config/.mozilla/firefox/ | grep default-release
# → xxxxxxxx.default-release
```

```ini
FIREFOX_PROFILE_PATH=/caminho/firefox-bot/.mozilla/firefox/xxxxxxxx.default-release
```

Use o caminho do **host** (não o do container — o bot lê o `cookies.sqlite` direto). Pode parar o container quando não precisar; o bot continua lendo o arquivo.
</details>

---

## 🧪 Testes

```bash
pip install -r requirements-dev.txt
pytest
```

---

## 📂 Estrutura

```
mediaraven.py            ponto de entrada
version.py               __version__
config.py                .env + 80+ envs + setup_logging
handlers.py              orquestração Telegram
telegram_io.py           upload de mídias
utils.py                 download/ffmpeg/imagens
messages.json            strings user-facing
log_messages.json        strings de log (~180 chaves)
customization.json       overrides por chat/user (~36 envs)
downloaders/
  dispatcher.py          orquestrador
  _platform.py _ytdlp.py _languages.py _caption.py
  instagram_embed.py     IG via /embed/ (sem login)
  instagram.py           IG via Instagrapi (com login)
  reddit_json.py         Reddit API pública
  reddit_playwright.py   Reddit headless (NSFW/spoilers)
  threads.py             Threads via JSON SSR
  x.py                   X via __INITIAL_STATE__ + GraphQL
  fallback.py            scraper genérico em cascata
  _scrape_helpers.py     URL rewrite, dedupe, parsers
lifecycle/               init, shutdown, refresh, métricas
```

---

## ❓ Problemas comuns

- **`BASE_DOWNLOAD_DIR deve ser absoluto`** → use caminho com `/` ou `C:/`.
- **Bot não responde em grupo** → desligue Group Privacy no BotFather.
- **`ffmpeg não encontrado`** → instale; sem ele, posts do IG com música avulsa não funcionam.
- **`Invalid file http url specified`** → Bot API local não tá acessível; confira o Docker e `LOCAL_API_HOST`.
- **Instagram pede login/challenge** → use conta descartável; delete `ig_session.json` e reinicie se travar.

---

## 📜 Licença

[MIT](LICENSE). Respeite os ToS de cada plataforma de onde baixa conteúdo.
