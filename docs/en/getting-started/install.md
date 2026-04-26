# Installation

## 1. System prerequisites

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

**Useful optionals:**

- **Deno** — bypasses YouTube JS challenges. Without it, some protected videos fail.
- **Firefox** — source of cookies the bot injects into yt-dlp and Playwright to access logged-in sites.

## 2. Clone + venv

```bash
git clone https://github.com/LordAztur/mediaraven.git
cd mediaraven
python3.11 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

`playwright install chromium` downloads a dedicated Chromium (~150 MB) used by Playwright for advanced scraping. Doesn't replace your browser.

## 3. Validate install

```bash
pytest        # ~250 tests, all should pass in <3s
python -c "from version import __version__; print(__version__)"
```

If you saw the version and tests passed, deps are OK. Next: [Configuration](config.md).
