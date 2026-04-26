# Instalação

## 1. Pré-requisitos do sistema

=== "Linux (Debian/Ubuntu)"

    ```bash
    sudo apt install -y python3.11 python3.11-venv ffmpeg git
    ```

=== "macOS"

    ```bash
    brew install python@3.11 ffmpeg git
    ```

=== "Windows (Chocolatey)"

    ```powershell
    choco install python311 ffmpeg git -y
    ```

**Opcionais úteis:**

- **Deno** — bypass de JS challenges do YouTube. Sem ele, alguns vídeos protegidos falham.
- **Firefox** — fonte dos cookies que o bot injeta no yt-dlp e no Playwright pra acessar sites logados.

## 2. Clone + venv

```bash
git clone https://github.com/LordAztur/mediaraven.git
cd mediaraven
python3.11 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

O `playwright install chromium` baixa um Chromium dedicado (~150 MB) que o Playwright usa pra scraper avançado. Não substitui seu navegador.

## 3. Validar instalação

```bash
pytest        # ~250 testes, deve passar tudo em <3s
python -c "from version import __version__; print(__version__)"
```

Se viu a versão e os testes verdes, deps tão ok. Próximo passo: [Configuração](config.md).
