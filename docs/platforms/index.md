# Plataformas

O MediaRaven detecta a plataforma pelo domínio da URL e roteia pra um handler dedicado quando existe. Quando não existe (ou o handler dedicado falha), cai no [scraper genérico](scraper.md).

## Roteamento

```mermaid
flowchart TD
    A[URL recebida] --> B{Detect platform}
    B -->|youtube.com| YT[yt-dlp + Deno bypass]
    B -->|instagram.com| IG[IG embed → Instagrapi]
    B -->|reddit.com| RD[reddit_json → reddit_playwright]
    B -->|threads.net| TH[Threads JSON SSR via Playwright]
    B -->|x.com / twitter.com| X[__INITIAL_STATE__ → Playwright auth]
    B -->|facebook.com| FB[yt-dlp generic]
    B -->|outro| SC[Scraper genérico em cascata]
    YT --> S[Sucesso?]
    IG --> S
    RD --> S
    TH --> S
    X --> S
    FB --> S
    SC --> S
    S -->|não| SC
    S -->|sim| OK[Envia mídia]
```

## Quando handler dedicado falha

Cai no scraper genérico, que tenta:

1. **HTTP fast path** (curl_cffi com Chrome impersonation) + Playwright em paralelo
2. **yt-dlp generic** (modo forçado pra qualquer URL)
3. **gallery-dl** (Pinterest, Imgur, Tumblr, ArtStation, etc.)
4. **iframe yt-dlp generic** (YouTube/Vimeo embedados)
5. **Screenshot da página** (último recurso, prompt opt-in)

Detalhes em [Cascata do scraper](../architecture/scraper-cascade.md).

## Páginas por plataforma

- [YouTube](youtube.md) — vídeos, Shorts, dublagens multi-idioma
- [Instagram](instagram.md) — posts, reels, stories, carrosséis, foto+música
- [Reddit](reddit.md) — galerias, vídeos, NSFW, spoilers
- [Threads](threads.md) — posts, carrosséis, texto-only
- [X / Twitter](x.md) — tweets com mídia, texto-only
- [Facebook](facebook.md) — vídeos públicos
- [Scraper genérico](scraper.md) — qualquer outro site
