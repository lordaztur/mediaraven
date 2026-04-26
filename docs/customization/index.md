# Customização

Tudo que afeta UX (timeouts, prompts, qualidade, scraper, etc.) é customizável **por chat** e **por usuário** via `customization.json`. As configs system-level (token, paths, pools) ficam no `.env` e não são per-chat.

## Precedência

```
user > chat > customization.default > .env (constante module-level)
```

Pra cada lookup, o `cfg(key)` resolve nessa ordem. Se a key existe no override do `user_id`, usa esse. Senão checa `chat_id`. Senão `default`. Senão cai pra constante do `.env`.

## Estrutura do arquivo

```bash
cp customization.example.json customization.json
```

```json
{
  "default": {
    "ASK_DL_TIMEOUT": 5.0,
    "YTDLP_MAX_HEIGHT": 1920
  },
  "chats": {
    "-1001234567890": {
      "YTDLP_MAX_HEIGHT": 720,
      "PROMPT_DOWNLOAD_ENABLED": false
    }
  },
  "users": {
    "555": {
      "ASK_CAPTION_DEFAULT": "yes",
      "YTDLP_MAX_HEIGHT": 4320
    }
  }
}
```

**Nesse exemplo:**

| Cenário | YTDLP_MAX_HEIGHT efetivo |
|---|---|
| User 555 manda link em qualquer chat | 4320 (override do user) |
| Outro user manda link no chat -1001234567890 | 720 (override do chat) |
| Outro user em qualquer outro chat | 1920 (default) |

## Reload

O JSON é carregado no boot. Pra aplicar mudanças, **restarte o bot** (não tem watch automático).

## ContextVar interno

Cada request seta `request_context = (chat_id, user_id)` no início do `handle_message`. Toda chamada `cfg(key)` ao longo do download lê esse contexto. Funciona automaticamente em chains de `await` e `loop.run_in_executor`.

## Páginas

- [Chaves de configuração](keys.md) — todas as 42 keys customizáveis
- [Mensagens da interface](messages.md) — `messages.json` (texto user-facing)
- [Mensagens de log](logs.md) — `log_messages.json` (~180 strings de log)
