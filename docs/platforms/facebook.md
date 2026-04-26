# Facebook

Facebook **não tem downloader dedicado** — passa direto pelo `yt-dlp` genérico. O bot só faz uma coisa específica antes: resolver share URLs (`fb.watch/X`, `m.facebook.com/share/X`) pra URL canônica.

## O que funciona bem

- ✅ Vídeo único (FB Watch, Reels, post de vídeo público)
- ✅ Vídeo + texto longo da legenda
- ✅ URL encurtada `fb.watch` (resolvida automaticamente)

## O que NÃO funciona bem

- ❌ **Carrossel de fotos** — yt-dlp historicamente é fraco com carrosséis no FB. Tipicamente pega só uma foto (a primeira ou a `og:image`).
- ❌ Posts privados / com login
- ❌ Stories

## Quando yt-dlp falha

Cai no scraper genérico. Mas **`_drop_facebook_image_only`** descarta resultados image-only do FB (heurística pra evitar enviar UI chrome do FB como se fosse a foto do post). Resultado prático: pra FB image-only, o bot frequentemente devolve "nenhuma mídia encontrada".

## Caption

Vem do `info_dict["description"]` que o yt-dlp extrai. Mesmo formato dos outros:

```
📄 Title
Description here...

🔗 Link Original
```

## Falhas comuns

- **Post pede login** → FB bloqueou anônimos pra muita coisa em 2024+. Cookies do Firefox de uma sessão logada ajudam, mas não 100%.
- **Carrossel virou foto única** → limitação real do yt-dlp. Não tem fix simples.
- **Vídeo trava no download** → ajuste `YTDLP_SOCKET_TIMEOUT` pra cima ou troque `YTDLP_YT_CLIENTS` (FB compartilha alguns clients com YouTube).
