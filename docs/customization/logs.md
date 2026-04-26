# Mensagens de log

~180 strings de log internas (INFO, WARNING, DEBUG, ERROR) são customizáveis via `log_messages.json`. Útil pra traduzir, padronizar emojis, ou desativar emojis em ambientes que não renderizam Unicode bem.

```bash
cp log_messages.example.json log_messages.json
# edite
```

Reload: restart do bot. Sem o arquivo, fallback pro `log_messages.example.json`.

## Estrutura

Top-level keys = nome do módulo. Sub-keys = identificador semântico do log.

```json
{
  "fallback": {
    "iniciando_scraping_multi": "🕸️ Iniciando Scraping Multi-Tier para: {arg0}",
    "fast_path_http": "Fast-path HTTP {arg0} pra {arg1}",
    ...
  },
  "x": {
    "iniciando_extra_o_para": "🐦 Iniciando extração para X: {arg0}",
    ...
  },
  ...
}
```

## API

No código:

```python
from messages import lmsg

logger.info(lmsg("fallback.iniciando_scraping_multi", arg0=safe_url(url)))
```

`lmsg("module.key", **kwargs)` resolve o template + faz `.format()`. **Não crasha se a key não existe** — retorna `<<missing log key: X>>` (graceful degradation, log continua aparecendo no formato fallback).

## Stack traces

Customização do log NÃO afeta stack traces. Quem chama o `logger.error("...", exc_info=True)` vai sempre printar a stack trace abaixo do texto, independente do que você bote no JSON.

## Logs hardcoded (chicken-and-egg)

Alguns logs precisam ficar hardcoded porque rodam ANTES do `messages.py` poder ser importado:

- `messages.py` mesmo (1 log)
- `config.py` `_boot_logger` (3 logs)
- `lifecycle/metrics_log.py` (1 log que chama `metrics.format_summary()`)

Esses ~5 logs continuam em português hardcoded.

## Exemplo: traduzindo pra inglês

```bash
cp log_messages.example.en.json log_messages.json
```

A versão `.en.json` mantém as **mesmas keys** (`fallback.iniciando_scraping_multi`) mas com strings em inglês:

```json
{
  "fallback": {
    "iniciando_scraping_multi": "🕸️ Starting Multi-Tier Scraping for: {arg0}",
    ...
  }
}
```

## Silenciar logs muito verbosos

Se um log específico tá poluindo, troque por string vazia:

```json
{
  "fallback": {
    "fast_path_http": ""
  }
}
```

Mas isso ainda gera a linha no log (só sem texto). Pra silenciar de verdade, ajuste o `LOG_LEVEL` ou edite o código pra remover o log call.
