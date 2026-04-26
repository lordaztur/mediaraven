# MediaRaven

**Bot do Telegram que baixa qualquer mídia da internet e envia direto no seu chat.**

Cole um link, recebe a mídia. O MediaRaven roda local, usa Bot API próprio (até 4 GB por arquivo se a conta dona for Telegram Premium), reaproveita cookies do Firefox, faz bypass de paywall soft e tem scraper genérico em cascata pra sites obscuros.

## Por que existe

Bots públicos de download têm limites apertados (50 MB), filas, propaganda, e quando funcionam expõem o conteúdo da galeria pra um terceiro. O MediaRaven é o oposto: roda no seu servidor, com sua conta, com regras suas. 1 GB de vídeo? Sem problema. Galeria do Pinterest com 30 imagens? Vai. Tweet só com texto? Vira mensagem formatada. Notícia atrás de paywall? Tenta Googlebot UA + archive.ph.

## Plataformas suportadas

| Plataforma | Estratégia | Texto-only? |
|---|---|---|
| YouTube | yt-dlp (com bypass JS via Deno) | — |
| Instagram | Embed → Instagrapi (login) | — |
| Reddit | API JSON → Playwright (NSFW) | — |
| Threads | JSON SSR via Playwright | ✅ |
| X (Twitter) | `__INITIAL_STATE__` + GraphQL | ✅ |
| Facebook | yt-dlp generic | — |
| Qualquer outro | Scraper genérico (HTTP + Playwright + yt-dlp + gallery-dl) | — |

## Highlights da v1.1.0

- 🌍 Bot API local — uploads até 2 GB (4 GB com Premium)
- 🦊 Cookies do Firefox automáticos pra burlar bloqueios
- 🔒 Bypass de paywall soft (Googlebot UA + archive.ph)
- 📰 Extração de corpo de artigo via trafilatura como caption
- 📝 Posts só de texto (Threads, X) viram mensagem formatada
- 🎚️ **42 configs customizáveis por chat e por usuário** ([entenda](customization/index.md))
- 🌐 Mensagens 100% customizáveis (UI + logs)
- 📊 ~250 testes, observabilidade detalhada nos logs

## Por onde começar

- **Quero rodar o bot** → [Instalação](getting-started/install.md)
- **Quero entender o que cada plataforma faz** → [Plataformas](platforms/index.md)
- **Quero mudar timeouts/qualidade pra um chat específico** → [Customização](customization/index.md)
- **Quero entender a arquitetura do scraper** → [Como funciona](architecture/index.md)
- **Algo deu errado** → [Solução de problemas](troubleshooting.md)
