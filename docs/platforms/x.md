# X (Twitter)

Extração em duas etapas:

## 1. Guest path (anônimo)

curl_cffi (Chrome impersonation) busca o HTML, regex extrai `window.__INITIAL_STATE__={...}`, parser percorre o JSON procurando o tweet pelo ID.

URL é normalizada pra `x.com` independente do domínio recebido (`twitter.com`, `fxtwitter.com`, `vxtwitter.com`, `fixupx.com`, `mobile.twitter.com`).

## 2. Authenticated path (Playwright)

Se guest retorna vazio (tweet protegido, ou X bloqueando), abre no Playwright **com cookies do Firefox** + intercepta requests pra `/i/api/graphql/` pra capturar o payload completo.

## O que funciona

- ✅ Tweets com 1 imagem
- ✅ Tweets com até 4 imagens (carrossel)
- ✅ Tweets com vídeo
- ✅ Tweets com GIF (extraído como vídeo MP4)
- ✅ **Tweets só com texto** → vira mensagem de texto formatada
- ✅ Resolve `t.co` trailing automaticamente (remove o link encurtado do final do texto)
- ❌ Threads de múltiplos tweets (só pega o tweet apontado)
- ❌ Spaces

## Caption

Bot extrai `screen_name` de várias fontes (em ordem):

1. `tweet["user"]["screen_name"]` (quando `user` é objeto)
2. `tweet["core"]["user_results"]["result"]["legacy"]["screen_name"]`
3. `data.entities.users.entities[<user_id>].screen_name` (lookup quando `user` é só string ID)
4. Username extraído da URL (`/<username>/status/`) — exceto pra `/i/status/` que é anônima

Caption final:

```
📄 @username
Texto do tweet (sem t.co trailing)

🔗 Link Original
```

## Posts só com texto

Idêntico ao Threads — `(files=[], caption_não_vazia)` vira mensagem de texto. Detalhes em [Posts de texto](../architecture/text-only-posts.md).

## Truncação de texto

X tweets podem ter até 4096 chars (premium) ou 280 (free). O `_build_caption` trunca pra 1024 (limite do Telegram caption) com "..." quando excede.

Quando o tweet é só texto, vai como `sendMessage` (limite 4096) — sem necessidade de truncar tanto.

## Falhas comuns

- **"Nenhuma mídia encontrada no tweet"** → tweet só de texto cai pro fluxo "text-only". Se ainda assim sumiu, é tweet de quote / repost.
- **"403 Forbidden"** → tweet protegido (conta privada). Cookies de Firefox de uma sessão logada que segue a conta resolvem.
- **`/i/status/` sem `@user` no caption** → o bot tenta lookup via `_resolve_user_dict()`. Se ainda assim ficar sem, é porque o JSON não trouxe o user data.
