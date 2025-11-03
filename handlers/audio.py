import os
import logging
import tempfile
from aiogram import Router
from aiogram.types import Message, FSInputFile
from utils.recognizer import search_spotify
from utils.downloader import _run

router = Router(name="audio")
logger = logging.getLogger("audio")


@router.message(lambda m: not any(x in (m.text or "").lower() for x in ["instagram.com", "tiktok.com", "youtu"]))
async def handle_text_music_search(message: Message):
    """
    Handles plain text messages like "21 Savage Redrum".
    - Searches Spotify for matches.
    - Downloads best result as MP3 via YouTube.
    """
    query = message.text.strip()
    if not query or len(query.split()) < 2:
        await message.answer(
            "🎵 Please type both artist and song name (e.g. <b>21 Savage redrum</b>)",
            parse_mode="HTML"
        )
        return

    await message.answer(f"🎧 Searching for <b>{query}</b> on Spotify...", parse_mode="HTML")

    try:
        # 1️⃣ Spotify Search
        result_msg = await search_spotify(query)
        await message.answer(result_msg, parse_mode="HTML")

        # 2️⃣ Try Download MP3 from YouTube
        tmpdir = tempfile.mkdtemp(prefix="music_")
        out_path = os.path.join(tmpdir, "song.%(ext)s")

        cmd = [
            "yt-dlp",
            "-x", "--audio-format", "mp3",
            "--default-search", "ytsearch1",
            "--no-warnings",
            "--quiet",
            "-o", out_path,
            query,
        ]

        logger.info(f"🎶 Searching & downloading '{query}' via yt-dlp...")
        await _run(cmd)

        # Find actual MP3
        mp3_path = ""
        for name in os.listdir(tmpdir):
            if name.endswith(".mp3"):
                mp3_path = os.path.join(tmpdir, name)
                break

        if mp3_path and os.path.exists(mp3_path):
            await message.answer_audio(
                audio=FSInputFile(mp3_path),
                caption=f"🎶 {query}\n✅ Downloaded from YouTube",
            )
            logger.info(f"✅ Sent MP3 for query: {query}")
        else:
            await message.answer("⚠️ Couldn’t download MP3, but you can listen on Spotify 👆")

    except Exception as e:
        logger.exception(f"❌ Music text search failed for: {query}")
        await message.answer(
            f"⚠️ Something went wrong while searching for '{query}'. Try again later."
        )
