# handlers/identify.py
import os
import tempfile
from aiogram import Router
from aiogram.types import Message
from utils.recognizer import identify_audio

router = Router(name="identify")

@router.message(lambda m: m.audio or m.voice or m.video)
async def identify_song(message: Message):
    await message.answer("🎧 Listening… analyzing audio…")

    # Build a hint from metadata/caption (helps Spotify fallback)
    hint_parts = []
    if message.caption:
        hint_parts.append(message.caption)
    if message.audio:
        if message.audio.performer:
            hint_parts.append(message.audio.performer)
        if message.audio.title:
            hint_parts.append(message.audio.title)
    hint = " ".join(p for p in hint_parts if p).strip() or None

    # Download to temp
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        file_path = tmp.name

    file_id = (message.audio or message.voice or message.video).file_id
    tg_file = await message.bot.get_file(file_id)
    await message.bot.download_file(tg_file.file_path, destination=file_path)

    try:
        result = await identify_audio(file_path, hint=hint)
        await message.answer(result, parse_mode="HTML")
    finally:
        try:
            os.remove(file_path)
        except Exception:
            pass
