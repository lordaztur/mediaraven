"""Testes dos helpers puros de utils: safe_url, normalize_image e chunk_html_text."""
import os

from PIL import Image

from config import cfg
from utils import chunk_html_text, normalize_image, safe_url


def test_chunk_html_text_returns_single_when_below_limit():
    assert chunk_html_text("oi", 100) == ["oi"]


def test_chunk_html_text_empty():
    assert chunk_html_text("", 100) == []


def test_chunk_html_text_prefers_paragraph_break():
    text = "primeiro\n\nsegundo\n\nterceiro"
    out = chunk_html_text(text, 12)
    assert out[0] == "primeiro"
    assert "segundo" in out[1] or out[1].startswith("segundo")


def test_chunk_html_text_chunks_under_limit():
    text = "abc\n\n" + "x" * 50 + "\n\n" + "y" * 50
    out = chunk_html_text(text, 60)
    for chunk in out:
        assert len(chunk) <= 60


def test_chunk_html_text_preserves_full_content():
    text = ("palavra " * 200).strip()
    out = chunk_html_text(text, 80)
    rejoined = " ".join(out)
    assert "palavra" * 1 in rejoined
    assert rejoined.count("palavra") == 200


def test_chunk_html_text_preserves_html_tags_when_in_separate_lines():
    """tag <b> no header e <a> no rodapé separados por \\n\\n: chunks ficam balanceados."""
    text = "<b>Header</b>\n\n" + "x" * 1000 + "\n\n<a href='u'>link</a>"
    out = chunk_html_text(text, 400)
    for chunk in out:
        assert chunk.count("<b>") == chunk.count("</b>")
        assert chunk.count("<a ") == chunk.count("</a>")


def test_safe_url_strips_query():
    assert safe_url("https://example.com/path?token=secret") == "https://example.com/path"


def test_safe_url_strips_fragment():
    assert safe_url("https://example.com/page#section") == "https://example.com/page"


def test_safe_url_truncates_long_url():
    long_url = "https://example.com/" + "a" * 500
    out = safe_url(long_url)
    assert len(out) <= cfg("SAFE_URL_MAX_LENGTH") + len("...(truncated)")
    assert out.endswith("...(truncated)")


def test_safe_url_invalid_input():
    assert safe_url(None) == "<invalid-url>"  # type: ignore[arg-type]


def test_safe_url_respects_custom_max_length():
    out = safe_url("https://x.com/" + "a" * 100, max_length=30)
    assert "...(truncated)" in out


def _make_png(path, size=(100, 100), mode="RGB", color=(255, 0, 0)):
    img = Image.new(mode, size, color)
    img.save(path, "PNG")


def test_normalize_image_passes_through_rgb(tmp_path):
    p = str(tmp_path / "ok.jpg")
    Image.new("RGB", (800, 600), (0, 255, 0)).save(p, "JPEG")
    out = normalize_image(p, min_size=100)
    assert out == p
    assert os.path.exists(p)


def test_normalize_image_converts_rgba_to_jpg(tmp_path):
    p = str(tmp_path / "alpha.png")
    Image.new("RGBA", (400, 400), (0, 0, 0, 128)).save(p, "PNG")
    out = normalize_image(p, min_size=100)
    assert out is not None
    assert out.endswith(".jpg")
    assert os.path.exists(out)
    # Original com extensão diferente é apagado.
    assert not os.path.exists(p)


def test_normalize_image_rejects_tiny(tmp_path):
    p = str(tmp_path / "tiny.jpg")
    Image.new("RGB", (10, 10), (0, 0, 0)).save(p, "JPEG")
    assert normalize_image(p, min_size=50) is None
    assert not os.path.exists(p)


def test_normalize_image_rejects_garbage(tmp_path):
    p = str(tmp_path / "not_image.jpg")
    with open(p, "wb") as f:
        f.write(b"definitely not a PNG")
    assert normalize_image(p) is None
    assert not os.path.exists(p)
