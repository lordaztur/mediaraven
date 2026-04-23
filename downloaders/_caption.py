import html
from typing import Any

from messages import msg


CAPTION_MAX = 1024
TEXT_MAX = 4096
FRAGMENT_RESERVE = 200


def _build_caption(info_dict: dict[str, Any], url: str) -> tuple[str, str]:
    raw_title = str(info_dict.get('title', '') or '')
    raw_desc = str(
        info_dict.get('description', '')
        or info_dict.get('comment', '')
        or info_dict.get('caption', '')
        or ''
    )
    link_label = msg("caption.link_original_label")
    title_prefix = msg("caption.title_prefix")
    link_prefix = msg("caption.link_prefix")

    def _build(title_budget: int, desc_budget: int, total_limit: int) -> str:
        title = raw_title[:title_budget]
        if len(raw_title) > title_budget:
            title = title.rstrip() + "..."
        desc = raw_desc[:desc_budget]
        if len(raw_desc) > desc_budget:
            desc = desc.rstrip() + "..."
        title_esc = html.escape(title)
        desc_esc = html.escape(desc)

        parts = []
        if title_esc:
            parts.append(f"{title_prefix}<b>{title_esc}</b>\n\n")
        if desc_esc:
            parts.append(f"{desc_esc}\n\n")
        parts.append(f"{link_prefix}<a href='{html.escape(url, quote=True)}'>{link_label}</a>")
        out = "".join(parts)
        if len(out) > total_limit:
            out = out[:total_limit]
        return out

    caption_budget = max(200, CAPTION_MAX - FRAGMENT_RESERVE - len(url))
    caption = ""
    if raw_title or raw_desc:
        title_b = int(caption_budget * 0.3)
        desc_b = caption_budget - title_b
        caption = _build(title_b, desc_b, CAPTION_MAX)

    text_budget = max(1000, TEXT_MAX - FRAGMENT_RESERVE - len(url))
    text_title_b = min(200, text_budget // 10)
    text_desc_b = text_budget - text_title_b
    text_content = _build(text_title_b, text_desc_b, TEXT_MAX)

    return caption, text_content
