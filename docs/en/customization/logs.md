# Log messages

~180 internal log strings (INFO, WARNING, DEBUG, ERROR) are customizable via `log_messages.json`. Useful for translating, standardizing emojis, or disabling emojis in environments that don't render Unicode well.

```bash
cp log_messages.example.en.json log_messages.json
# edit
```

Reload: bot restart. Without the file, fallback to `log_messages.example.en.json`.

## Structure

Top-level keys = module name. Sub-keys = semantic identifier of the log.

```json
{
  "fallback": {
    "iniciando_scraping_multi": "🕸️ Starting Multi-Tier Scraping for: {arg0}",
    "fast_path_http": "Fast-path HTTP {arg0} for {arg1}",
    ...
  },
  "x": {
    "iniciando_extra_o_para": "🐦 Starting extraction for X: {arg0}",
    ...
  },
  ...
}
```

## API

In code:

```python
from messages import lmsg

logger.info(lmsg("fallback.iniciando_scraping_multi", arg0=safe_url(url)))
```

`lmsg("module.key", **kwargs)` resolves the template + does `.format()`. **Doesn't crash if the key doesn't exist** — returns `<<missing log key: X>>` (graceful degradation, log keeps showing in fallback format).

## Stack traces

Log customization does NOT affect stack traces. Whoever calls `logger.error("...", exc_info=True)` always prints the stack trace below the text, regardless of what you put in the JSON.

## Hardcoded logs (chicken-and-egg)

Some logs need to stay hardcoded because they run BEFORE `messages.py` can be imported:

- `messages.py` itself (1 log)
- `config.py` `_boot_logger` (3 logs)
- `lifecycle/metrics_log.py` (1 log that calls `metrics.format_summary()`)

These ~5 logs stay in Portuguese hardcoded.

## Example: translating to Portuguese

```bash
cp log_messages.example.json log_messages.json
```

The `.json` (PT) version keeps the **same keys** (`fallback.iniciando_scraping_multi`) but with strings in Portuguese:

```json
{
  "fallback": {
    "iniciando_scraping_multi": "🕸️ Iniciando Scraping Multi-Tier para: {arg0}",
    ...
  }
}
```

## Silencing very verbose logs

If a specific log is polluting, replace with empty string:

```json
{
  "fallback": {
    "fast_path_http": ""
  }
}
```

But this still generates the line in the log (just without text). To truly silence, adjust `LOG_LEVEL` or edit code to remove the log call.
