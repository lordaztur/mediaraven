"""Regressão: foto única do IG deve baixar via photo_download_by_url (private media_info),
não via photo_download(media_pk), que re-busca pelo GraphQL público (bloqueado, 401)."""
import os

import pytest

import state
from downloaders.instagram import download_instagram_instagrapi


class _FakeMedia:
    media_type = 1
    resources = []
    thumbnail_url = "https://scontent.cdninstagram.com/v/photo_full.jpg"
    caption_text = "legenda de teste"


class _FakeClient:
    def __init__(self):
        self.by_url_calls = []

    def media_pk_from_url(self, url):
        return "3929658045372854557"

    def media_info(self, pk):
        return _FakeMedia()

    def private_request(self, path):
        return {}

    def photo_download(self, media_pk, folder=""):
        raise AssertionError("photo_download(media_pk) usa o GraphQL público quebrado; não deve ser chamado")

    def photo_download_by_url(self, url, folder=""):
        self.by_url_calls.append(url)
        path = os.path.join(folder, "ig_photo.jpg")
        with open(path, "wb") as f:
            f.write(b"\xff\xd8\xff\xe0jpegbytes")
        return path


@pytest.mark.asyncio
async def test_single_photo_uses_download_by_url(tmp_path, monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr(state, "IG_CLIENT", fake)

    paths, status, short, full = await download_instagram_instagrapi(
        "https://www.instagram.com/p/DaI8ywLNHEd/", str(tmp_path)
    )

    assert fake.by_url_calls == ["https://scontent.cdninstagram.com/v/photo_full.jpg"]
    assert len(paths) == 1 and paths[0].endswith("ig_photo.jpg")
    assert os.path.exists(paths[0])
    assert "legenda de teste" in full
