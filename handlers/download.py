import os
import shutil
import tempfile
import asyncio
import logging
from aiogram import Router
from aiogram.types import Message, FSInputFile
from utils.downloader import run_yt_dlp

router = Router(name="download")
logger = logging.getLogger("download")

MAX_TG_FILE_SIZE = 50 * 1024 * 1024  # Telegram limit ≈ 50MB

# ───────────────────────────────────────────────
# Compress large videos using ffmpeg
# ───────────────────────────────────────────────
async def compress_video(input_path: str, output_path: str):
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", "scale=-1:720",
        "-b:v", "2M", "-b:a", "128k",
        output_path,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    await proc.communicate()
    return proc.returncode == 0 and os.path.exists(output_path)


# ───────────────────────────────────────────────
# 🎬 Download Handler (Instagram / TikTok / YouTube / Photos)
# ───────────────────────────────────────────────
@router.message(lambda m: any(x in (m.text or "").lower() for x in ["instagram.com", "tiktok.com", "youtu"]))
async def handle_link_download(message: Message):
    """Handles all supported social links."""
    url = message.text.strip()
    await message.answer("🎬 Downloading your media... Please wait ⏳")

    tmpdir = tempfile.mkdtemp(prefix="media_")
    output_template = os.path.join(tmpdir, "media.%(ext)s")
    cookies_path = os.path.join(os.getcwd(), "cookies.txt")

    try:
        cookies_exist = os.path.exists(cookies_path)
        logger.info(f"🍪 Cookies loaded: {cookies_exist}")

        ydl_opts = {
            "outtmpl": output_template,
            "quiet": True,
            "cookiefile": cookies_path if cookies_exist else None,
            "socket_timeout": 60,
            "retries": 3,
            "ignoreerrors": True,
            "format": "best/bestvideo+bestaudio/best",
            "geo_bypass": True,
            "nocheckcertificate": True,
            "writethumbnail": True,
            "merge_output_format": "mp4",
            "no_color": True,
        }

        logger.info(f"⬇️ Running yt-dlp for: {url}")
        result = await run_yt_dlp(url, tmpdir)

        # Detect all files downloaded
        files = [os.path.join(tmpdir, f) for f in os.listdir(tmpdir)]
        if not files:
            raise RuntimeError("yt-dlp did not produce any output files.")

        sent_any = False

        for file_path in files:
            size = os.path.getsize(file_path)
            ext = os.path.splitext(file_path)[1].lower()

            if ext in [".jpg", ".jpeg", ".png", ".webp"]:
                await message.answer_photo(FSInputFile(file_path), caption=f"📸 {url}")
                sent_any = True

            elif ext in [".mp4", ".mov", ".mkv"]:
                if size > MAX_TG_FILE_SIZE:
                    compressed_path = os.path.join(tmpdir, "compressed.mp4")
                    await message.answer("⚙️ Compressing large video for Telegram...")
                    ok = await compress_video(file_path, compressed_path)
                    if ok:
                        file_path = compressed_path
                    else:
                        await message.answer(f"⚠️ File too large to send. You can view it here:\n{url}")
                        continue

                await message.answer_video(FSInputFile(file_path), caption=f"🎥 {url}")
                sent_any = True

        if not sent_any:
            await message.answer("⚠️ No downloadable media found in this post (might be private).")

    except Exception as e:
        logger.exception("❌ Failed to download media")
        await message.answer(f"❌ Couldn't download this post. It may be private or unsupported.\nError: {e}")

    finally:
        await asyncio.sleep(3)
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception as e:
            logger.warning(f"⚠️ Temp cleanup skipped: {e}")
