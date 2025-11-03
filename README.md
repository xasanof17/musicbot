# MusicBot (aiogram 3 • Railway-ready)

A Telegram bot to:
- 🎬 Download media via URL or uploads (yt-dlp)
- 🎧 Extract audio (ffmpeg)
- 🔎 Identify songs (Chromaprint + AcoustID)

## Features
- aiogram 3.x, async-safe
- Beautiful inline keyboards with progress states
- Clean logging for Railway
- Hobby plan friendly (single dyno)

## Env Vars
- `TELEGRAM_BOT_TOKEN` (required)
- `ACOUSTID_API_KEY` (optional but recommended)
- `LOG_LEVEL` (default: INFO)

## Local Run
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# make sure ffmpeg is installed on your OS
export TELEGRAM_BOT_TOKEN=xxx
export ACOUSTID_API_KEY=xxx
python -m musicbot.bot
