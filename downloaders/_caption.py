import html
from typing import Any

from messages import msg


CAPTION_MAX = 1024
TEXT_MAX = 4096
FRAGMENT_RESERVE = 200


def _pick_uploader(info_dict: dict[str, Any]) -> str:
    uid = str(info_dict.get('uploader_id') or '').strip()
    if uid.startswith('@'):
        return uid
    return str(
        info_dict.get('uploader')
        or info_dict.get('channel')
        or uid
        or ''
    ).strip()


def _title_is_redundant(title: str, desc: str) -> bool:
    if not title or not desc:
        return False
    t = title.strip().lower()
    d = desc.strip().lower()
    return t == d or d.startswith(t)


def _looks_like_shorts(info_dict: dict[str, Any], url: str) -> bool:
    for key in ('original_url', 'webpage_url'):
        v = info_dict.get(key)
        if isinstance(v, str) and '/shorts/' in v:
            return True
    return '/shorts/' in url


def _build_caption(info_dict: dict[str, Any], url: str) -> tuple[str, str]:
    raw_uploader = _pick_uploader(info_dict)
    raw_title = str(info_dict.get('alt_title') or info_dict.get('title') or '').strip()
    raw_desc = str(
        info_dict.get('description', '')
        or info_dict.get('comment', '')
        or info_dict.get('caption', '')
        or ''
    ).strip()

    if _looks_like_shorts(info_dict, url):
        if not raw_desc:
            raw_desc = raw_title
        raw_title = ''
    elif _title_is_redundant(raw_title, raw_desc):
        raw_title = ''

    if not raw_uploader and raw_title:
        raw_uploader, raw_title = raw_title, ''

    link_label = msg("caption.link_original_label")
    title_prefix = msg("caption.title_prefix")
    link_prefix = msg("caption.link_prefix")
    link_html = f"{link_prefix}<a href='{html.escape(url, quote=True)}'>{link_label}</a>"

    def _build(uploader_budget: int, title_budget: int, desc_budget: int, total_limit: int) -> str:
        up = raw_uploader[:uploader_budget]
        if len(raw_uploader) > uploader_budget:
            up = up.rstrip() + "..."
        ttl = raw_title[:title_budget]
        if len(raw_title) > title_budget:
            ttl = ttl.rstrip() + "..."
        ds = raw_desc[:desc_budget]
        if len(raw_desc) > desc_budget:
            ds = ds.rstrip() + "..."

        up_esc = html.escape(up)
        ttl_esc = html.escape(ttl)
        ds_esc = html.escape(ds)

        header_lines = []
        if up_esc:
            header_lines.append(f"{title_prefix}<b>{up_esc}</b>")
        if ttl_esc:
            header_lines.append(f"<b>{ttl_esc}</b>")

        parts = []
        if header_lines:
            parts.append("\n".join(header_lines) + "\n\n")
        if ds_esc:
            parts.append(f"{ds_esc}\n\n")
        parts.append(link_html)

        out = "".join(parts)
        if len(out) > total_limit:
            out = out[:total_limit]
        return out

    caption_budget = max(200, CAPTION_MAX - FRAGMENT_RESERVE - len(url))
    caption = ""
    if raw_uploader or raw_title or raw_desc:
        up_b = min(80, caption_budget // 5)
        ttl_b = min(120, caption_budget // 4)
        ds_b = caption_budget - up_b - ttl_b
        caption = _build(up_b, ttl_b, ds_b, CAPTION_MAX)

    text_budget = max(1000, TEXT_MAX - FRAGMENT_RESERVE - len(url))
    text_up_b = min(80, text_budget // 20)
    text_ttl_b = min(200, text_budget // 10)
    text_desc_b = text_budget - text_up_b - text_ttl_b
    text_content = _build(text_up_b, text_ttl_b, text_desc_b, TEXT_MAX)

    return caption, text_content
