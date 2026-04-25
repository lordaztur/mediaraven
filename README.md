<div align="center">

<img src="assets/banner.svg" alt="MediaRaven" width="720"/>

**Bot do Telegram que baixa qualquer mídia da internet e envia direto no seu chat.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-22.7-26A5E4?style=flat&logo=telegram&logoColor=white)](https://python-telegram-bot.org/)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20Windows%20%7C%20macOS-blue?style=flat)](#)
[![yt-dlp](https://img.shields.io/badge/powered%20by-yt--dlp-red?style=flat)](https://github.com/yt-dlp/yt-dlp)
[![Playwright](https://img.shields.io/badge/playwright-1.58-2EAD33?style=flat&logo=playwright&logoColor=white)](https://playwright.dev/)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat)](LICENSE)

</div>

---

## ✨ O que ele faz

Cole qualquer link num chat e o bot devolve a mídia em segundos. Simples assim.

- 🎥 **YouTube** — vídeos, Shorts, múltiplas trilhas de áudio (seleção de idioma quando há dublagem)
- 📸 **Instagram** — posts, reels, carrosséis, stories, com áudio original
- 👽 **Reddit** — galerias, imagens únicas, vídeos, posts NSFW (remove blur)
- 🧵 **Threads** — posts, carrosséis (foto/vídeo/misto), reposts com comentário
- 👍 **Facebook** — vídeos e reels (incluindo links `/share/v/` resolvidos automaticamente)
- 🕸️ **Qualquer outro site** — scraper genérico varre a página à procura de mídias

### 🎁 Extras

- ⚡ Envia arquivos de até **2 GB** (usa Bot API local)
- 🍪 Reaproveita cookies do seu **Firefox** para burlar paywalls e bloqueios
- 🗣️ Todas as mensagens estão em um **arquivo JSON** — personalize o tom do bot sem tocar no código
- 🔒 **Whitelist** de chats e usuários permitidos
- ⚙️ **70+ parâmetros configuráveis via `.env`** — timeouts, concorrência, qualidade de vídeo, prompts por chat/usuário, tudo
- 📊 Métricas de sucesso/falha por plataforma nos logs
- 🔁 Botão **"Tentar novamente"** se um download falhar

---

## 📸 Como funciona (resumo)

```
┌─────────────┐      ┌──────────┐      ┌─────────────┐      ┌──────────┐
│  Você cola  │──►   │  Bot     │──►   │  Escolhe o  │──►   │ Baixa e  │
│  um link    │      │ detecta  │      │   método    │      │  envia   │
└─────────────┘      └──────────┘      └─────────────┘      └──────────┘
                                       yt-dlp / Instagrapi
                                       Reddit JSON / Playwright
                                       Scraper genérico
```

O bot tenta várias estratégias em ordem. Se uma falha, cai na próxima — você quase nunca vai ver um "não consegui".

---

## 🚀 Tutorial de instalação

> **Tempo estimado**: 20–30 minutos na primeira vez.

### 1️⃣ Pré-requisitos

| Requisito | Versão | Obrigatório? |
|-----------|--------|:---:|
| Python | 3.11+ | ✅ |
| ffmpeg | qualquer recente | ✅ (para Instagram com áudio) |
| git | qualquer | ✅ |
| Deno | qualquer | ⚠️ opcional (bypass JS do YouTube) |
| Firefox | qualquer | ⚠️ opcional (cookies) |

<details>
<summary><b>📦 Instalando no Linux (Debian/Ubuntu)</b></summary>

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip ffmpeg git
# Deno (opcional)
curl -fsSL https://deno.land/install.sh | sh
```
</details>

<details>
<summary><b>📦 Instalando no Windows</b></summary>

Use [Chocolatey](https://chocolatey.org/) (PowerShell como admin):
```powershell
choco install python311 ffmpeg git -y
choco install deno -y   # opcional
```

Ou baixe manualmente: [Python](https://www.python.org/downloads/), [ffmpeg](https://www.gyan.dev/ffmpeg/builds/), [git](https://git-scm.com/).
</details>

<details>
<summary><b>📦 Instalando no macOS</b></summary>

```bash
brew install python@3.11 ffmpeg git
brew install deno   # opcional
```
</details>

---

### 2️⃣ Telegram Bot API Local

Esse passo é **obrigatório** — sem o servidor local, o Telegram limita uploads a 50 MB. Com ele, você manda até 2 GB.

#### Opção A: Docker (recomendado — mais simples)

```bash
docker run -d --name telegram-bot-api \
  -p 8081:8081 \
  -e TELEGRAM_API_ID=SEU_API_ID \
  -e TELEGRAM_API_HASH=SEU_API_HASH \
  -e TELEGRAM_LOCAL=1 \
  -v telegram-bot-api-data:/var/lib/telegram-bot-api \
  aiogram/telegram-bot-api:latest
```

Para conseguir `TELEGRAM_API_ID` e `TELEGRAM_API_HASH`:
1. Entre em https://my.telegram.org
2. Faça login com seu número
3. Clique em **API development tools** → **Create application**
4. Preencha qualquer nome/descrição — copie o `api_id` e `api_hash`

#### Opção B: Compilar do zero

Siga o guia oficial: [github.com/tdlib/telegram-bot-api](https://github.com/tdlib/telegram-bot-api#installation).

#### ✅ Teste se tá funcionando

```bash
curl http://localhost:8081/
# deve responder algo — não vai dar "connection refused"
```

---

### 3️⃣ Criar o bot no Telegram

1. Abra o Telegram e fale com **[@BotFather](https://t.me/BotFather)**
2. Mande `/newbot`
3. Escolha um nome e um username (tem que terminar com `bot`)
4. O BotFather te manda um **token**: `123456789:ABC-DEF...` — guarde

#### Permitir que o bot leia todas as mensagens do grupo

```
/mybots → [seu bot] → Bot Settings → Group Privacy → Turn OFF
```

Sem isso, o bot só responde a comandos e menções.

---

### 4️⃣ Pegar seu User ID e do grupo

- **Seu ID**: fale com [@userinfobot](https://t.me/userinfobot)
- **ID do grupo**: adicione o bot ao grupo, mande qualquer mensagem, e acesse:
  ```
  https://api.telegram.org/bot<SEU_TOKEN>/getUpdates
  ```
  Procure `"chat":{"id":-100...` — é o ID (negativo).

---

### 5️⃣ Clonar o projeto e instalar dependências

```bash
git clone https://github.com/SEU_USUARIO/mediaraven.git
cd mediaraven

# Ambiente virtual Python
python3.11 -m venv venv

# Ativar o venv
source venv/bin/activate          # Linux/macOS
# ou
venv\Scripts\activate              # Windows PowerShell

# Instalar deps
pip install -r requirements.txt

# Instalar navegador do Playwright (~300 MB)
playwright install chromium
```

---

### 6️⃣ Configurar o `.env`

```bash
cp .env_example .env
```

Edite o `.env` com seu editor favorito. Campos essenciais:

```ini
TELEGRAM_BOT_TOKEN="123456789:ABC-DEF..."
ALLOWED_CHAT_ID=-1001234567890
ALLOWED_USER_IDS=123456789
LOCAL_API_HOST=127.0.0.1:8081
BASE_DOWNLOAD_DIR=/caminho/absoluto/para/pasta/downloads
```

> ⚠️ `BASE_DOWNLOAD_DIR` precisa ser **absoluto** (começar com `/` no Linux/macOS ou `C:/` no Windows).

Opcionais (deixe em branco se não quiser usar):
- `IG_USER` / `IG_PASS` — conta descartável do Instagram para fallback
- `FIREFOX_PROFILE_PATH` — para reaproveitar cookies de sites logados

<details>
<summary><b>🦊 Dica: Firefox dockerizado dedicado ao bot (recomendado em servidor)</b></summary>

Em vez de apontar o bot para o seu Firefox pessoal, rode um Firefox isolado em Docker com **VNC via web**. Vantagens:

- 🔒 Cookies e sessões isolados do seu navegador pessoal
- 🖥️ Funciona em servidor headless (sem GUI)
- 🔄 Faz login UMA vez pelo navegador web e os cookies ficam persistidos no volume
- 🧼 Se um site bloquear a sessão, é só apagar o volume e relogar sem afetar o navegador principal

#### 1. Subir o container

```bash
docker run -d \
  --name firefox-bot \
  --restart unless-stopped \
  -p 5800:5800 \
  -v /caminho/absoluto/para/firefox-bot:/config \
  --shm-size 2g \
  jlesage/firefox
```

Substitua `/caminho/absoluto/para/firefox-bot` pela pasta que você quer dedicar ao perfil. Exemplos:
- Linux: `/home/seu_user/docker/firefox-bot`
- Windows: `C:/docker/firefox-bot`

#### 2. Fazer login nos sites

Abra no seu navegador pessoal:
```
http://localhost:5800
```
(ou `http://IP-do-servidor:5800` se Docker estiver em outra máquina)

Aparece o Firefox em tela cheia. Entre no YouTube, Instagram, Reddit, e faça login em cada um. O Firefox já salva tudo automaticamente no volume montado.

#### 3. Encontrar o caminho do perfil

Dentro do container, o perfil fica em:
```
/config/.mozilla/firefox/<HASH>.default-release
```

Para descobrir o `<HASH>`:

```bash
docker exec firefox-bot ls /config/.mozilla/firefox/ | grep default-release
```

O output é algo como `xxxxxxxx.default-release`.

#### 4. Apontar o bot para o volume

No seu `.env`:

```ini
FIREFOX_PROFILE_PATH=/caminho/absoluto/para/firefox-bot/.mozilla/firefox/xxxxxxxx.default-release
```

**Importante:** use o caminho do **host**, não o caminho interno do container. O bot precisa acessar o `cookies.sqlite` diretamente — ele não fala com o container.

#### 5. (Opcional) Parar o Firefox quando não estiver usando

O container ocupa memória. Se você só precisa dele para revalidar login esporadicamente:

```bash
docker stop firefox-bot                # para
docker start firefox-bot               # inicia
```

O bot continua lendo os cookies normalmente, mesmo com o container parado — o `cookies.sqlite` no volume é acessível.

</details>

> 💡 O `.env_example` lista ~70 outras variáveis de **customização avançada** (timeouts, tamanhos de pool, qualidade máxima de vídeo, prompts por chat/usuário, User-Agents, etc). Todas têm defaults sensatos — só adicione ao seu `.env` o que quiser mudar.

---

### 7️⃣ Rodar

```bash
python mediaraven.py
```

Se tudo certo, você vê:
```
🦕 Deno encontrado em: ...
🎬 ffmpeg encontrado em: ...
🔌 Conectando ao Servidor Local em: http://127.0.0.1:8081/bot
🌐 Sessão aiohttp global iniciada (timeout default 30s).
🌐 Iniciando Playwright (Navegador Global)...
✅ Todos os serviços globais prontos!
🤖 Bot Iniciado...
```

Manda um link pro bot e se prepara. 🎉

---

## 🎨 Personalizar mensagens

Copie `messages.example.json` para `messages.json` e altere qualquer frase. O bot recarrega ao reiniciar. Você pode trocar emojis, idioma, tom — tudo.

Exemplos do que dá pra customizar:
- Emojis de reação ao receber um link
- Mensagens enquanto baixa ("Aguenta aí, tô terminando...")
- Prefixos de legenda (`📄`, `🔗`)
- Label do botão "ORIGINAL" na escolha de idioma

---

## ⚙️ Customização avançada

Tudo que é hardcoded em outros bots aqui é env var. Alguns destaques:

### 🎚️ Prompts interativos

Cada prompt (baixar/ignorar, legenda, idioma) pode ser ligado ou desligado por **chat** ou por **usuário**. Precedência: `OFF_USERS` > `ON_USERS` > `OFF_CHATS` > default (ligado).

```ini
# No grupo -100123 o bot baixa sem perguntar, mas o usuário 555 sempre vê o prompt:
PROMPT_DOWNLOAD_OFF_CHATS=-100123
PROMPT_DOWNLOAD_ON_USERS=555
```

Mesmo esquema para `PROMPT_CAPTION_*` e `PROMPT_LANG_*`.

### 📐 Qualidade, concorrência e timeouts

```ini
YTDLP_MAX_HEIGHT=1920           # 1080p. Use 720 em conexão limitada ou 4320 em 8K.
YTDLP_WORKERS=5                 # downloads yt-dlp simultâneos
PW_CONCURRENCY=3                # páginas Playwright simultâneas
MAX_URLS_PER_MESSAGE=20         # anti paste-bomb
TELEGRAM_UPLOAD_TIMEOUT=600     # timeout de upload (segundos)
ASK_DL_TIMEOUT=5.0              # tempo para clicar "baixar/ignorar"
```

### 📊 Observabilidade

```ini
LOG_LEVEL=DEBUG                 # mais verboso para debug pontual
LOG_MAX_BYTES=20971520          # tamanho de cada arquivo de log
LOG_BACKUP_COUNT=5              # quantos backups manter
METRICS_LOG_INTERVAL_MIN=30     # log de métricas agregadas
```

Consulte `.env_example` para a lista completa — cada variável tem um comentário explicando para que serve.

---

## 🧪 Rodando os testes

```bash
# com o venv ativo
pip install -r requirements-dev.txt
pytest
```

114 testes cobrem: parsing de config, controle de prompts por chat/usuário, extração de URLs, detecção de plataforma, helpers do dispatcher, fluxo de fallbacks, cookies do Firefox, métricas, validação de mensagens, imagens/URL helpers, lifecycle, extração de mídia do Threads via JSON SSR.

---

## 📂 Estrutura

```
mediaraven/
├── mediaraven.py            ← ponto de entrada
├── config.py                ← leitura do .env + validação + 70+ env vars
├── handlers.py              ← callbacks e orquestração do Telegram
├── telegram_io.py           ← envio de mídias
├── utils.py                 ← helpers (download, ffmpeg, imagens)
├── metrics.py               ← contadores de sucesso/falha por plataforma
├── messages.json            ← TODAS as mensagens user-facing
├── downloaders/
│   ├── dispatcher.py        ← orquestrador
│   ├── _platform.py         ← detecção por domínio
│   ├── _ytdlp.py            ← wrappers do yt-dlp
│   ├── _languages.py        ← multi-idioma do YouTube
│   ├── _caption.py          ← legendas HTML
│   ├── instagram.py         ← fallback Instagrapi
│   ├── reddit_json.py       ← API pública do Reddit
│   ├── reddit_playwright.py ← Playwright no Reddit (NSFW, spoilers)
│   ├── threads.py           ← extração JSON SSR do Threads (Playwright + parse)
│   └── fallback.py          ← scraper genérico
└── lifecycle/
    ├── services.py          ← init/stop globais
    ├── startup.py           ← deno, ffmpeg, limpeza inicial
    ├── chat_lock.py         ← locks por chat (serializa downloads)
    ├── instagram_login.py   ← login IG em background
    ├── playwright_refresh.py← reciclagem do Playwright por RSS (psutil)
    └── metrics_log.py       ← log periódico de métricas
```

---

## ❓ Problemas comuns

<details>
<summary><b>"Config inválida: BASE_DOWNLOAD_DIR deve ser absoluto"</b></summary>

Seu `.env` está com `BASE_DOWNLOAD_DIR=./downloads` ou similar. Troque por um caminho absoluto como `/home/seu_user/downloads` ou `C:/mediaraven/downloads`.
</details>

<details>
<summary><b>Bot não responde em grupos</b></summary>

Desative a **Group Privacy** do bot no BotFather (passo 3 do tutorial).
</details>

<details>
<summary><b>"ffmpeg não encontrado no PATH"</b></summary>

O bot sobe mesmo assim, mas posts do Instagram com áudio+imagem não vão funcionar. Instale o ffmpeg e reinicie.
</details>

<details>
<summary><b>"Invalid file http url specified"</b></summary>

Seu servidor Bot API Local não está acessível. Confira se o Docker tá rodando e se `LOCAL_API_HOST` no `.env` aponta para o host:porta certos.
</details>

<details>
<summary><b>Instagram fica pedindo login/challenge</b></summary>

Use uma **conta descartável** no `.env`, não a principal. O Instagram pode bloquear contas que logam via API com frequência. Delete `ig_session.json` e reinicie se travar.
</details>

---

## 📜 Licença

[MIT](LICENSE) — livre para usar, modificar e distribuir.

Respeite os Termos de Serviço de cada plataforma da qual você baixa conteúdo.
