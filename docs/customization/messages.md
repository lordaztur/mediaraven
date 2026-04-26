# Mensagens da interface

Toda string que o bot manda pro Telegram (botões, prompts, status, callback alerts) vive em `messages.json`. Você customiza traduzindo, mudando emoji, ou trocando o tom.

```bash
cp messages.example.json messages.json
# edite à vontade
```

Reload: restart do bot. Sem `messages.json`, o bot usa `messages.example.json` como fallback.

## Estrutura

Top-level groups:

```json
{
  "startup":           { "token_missing": "...", "connecting": "...", "ready": "..." },
  "buttons":           { "download_yes": "...", "caption_yes": "...", ... },
  "prompts":           { "link_detected": "...", "caption_found": "...", ... },
  "callback_alerts":   { "dl_expired": "...", "dl_wrong_user": "...", ... },
  "status":            { "downloading": "...", "sending": "...", ... },
  "status_cycle":      [ "...", "...", "..." ],
  "downloader_status": { "ytdlp_success": "...", "scraper": "...", ... },
  "media_type_labels": { "ig_video": "...", "scraper_images": "...", ... },
  "caption":           { "link_original_label": "...", "title_prefix": "📄 ", ... },
  "reactions":         [ "🔥", "⚡", ... ]
}
```

## Placeholders

Strings podem ter `{var}` que são substituídas em runtime via `.format(**kwargs)`. Exemplos:

- `prompts.link_detected: "🔗 Link detectado{suffix}"` — `{suffix}` vira `" [2/5]"` quando há múltiplas URLs
- `downloader_status.scraper: "🕸️ Scraper Deep Search ({media_type}) [{count} arquivos]"` — `{media_type}` e `{count}` vêm do código

Se você remover um placeholder que o código espera, o `msg()` vai dar erro de format. **Mantenha os `{vars}` no seu override.**

## Idiomas

Há um arquivo `messages.example.en.json` em inglês. Pra usar:

```bash
cp messages.example.en.json messages.json
```

Você pode misturar — copiar o EN, traduzir alguns campos pra outro idioma, deixar outros em inglês.

## Reactions

A array `reactions` define os emojis que o bot reage à mensagem original ao começar a processar. Bot escolhe um aleatório a cada request:

```json
"reactions": ["🔥", "⚡", "👀", "🗿", "👨‍💻"]
```

Lista vazia (`[]`) desabilita reações.

## Dica: cycle de status

Durante o download, o bot edita a mensagem de status ciclicamente entre os textos em `status_cycle`. Default tem 5 mensagens. Adicione/remova quantas quiser:

```json
"status_cycle": [
  "📥 Baixando mídia...{suffix}",
  "📥 Processando o conteúdo...{suffix}",
  "📥 Tô quase lá...{suffix}",
  "📥 Aguenta aí, vai chegar...{suffix}"
]
```

Intervalo entre rotações = `STATUS_CYCLE_INTERVAL` (em [Customização](keys.md)).
