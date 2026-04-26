# Getting Started

To get MediaRaven running you need **three things**:

1. **Install** the code + Python deps — [Installation](install.md)
2. **Run the local Bot API server** + create the bot in @BotFather — [Configuration](config.md)
3. **Fill the `.env`** with token, IDs and paths — [Configuration](config.md)

Then it's `python mediaraven.py` and send a link in Telegram.

## Prerequisites at a glance

- Python 3.11+
- ffmpeg (for audio/video mixing)
- Docker (for the local Bot API server)
- Optional: Deno (for YouTube JS bypass), Firefox (to reuse cookies)
