import asyncio
import os
import re
import sys
import logging
from aiogram.types import Message

# ───────────────────────────────────────────────
# ⚙️ Constants
# ───────────────────────────────────────────────
YTDLP_BIN = sys.executable
YTDLP_ARGS = ["-m", "yt_dlp"]
FFMPEG_BIN = "ffmpeg"
MAX_FILE_BYTES = 200 * 1024 * 1024  # 200 MB Telegram-safe limit

logger = logging.getLogger("downloader")


# ───────────────────────────────────────────────
# 🔍 URL detection helper
# ───────────────────────────────────────────────
def _is_url(text: str) -> bool:
    return bool(re.match(r"https?://", text or ""))


# ───────────────────────────────────────────────
# ⚙️ Async subprocess runner
# ───────────────────────────────────────────────
async def _run(cmd: list[str]) -> tuple[str, str]:
    """Executes an async subprocess and captures output."""
    if cmd[0] == "yt-dlp":
        cmd = [sys.executable, "-m", "yt_dlp"] + cmd[1:]

    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(
            f"❌ Command failed: {' '.join(cmd)}\n{stderr.decode(errors='ignore')}"
        )

    return stdout.decode(errors="ignore"), stderr.decode(errors="ignore")


# ───────────────────────────────────────────────
# 🎬 yt-dlp universal runner
# ───────────────────────────────────────────────
async def run_yt_dlp(url: str, tmpdir: str, audio_only: bool = False) -> str:
    """
    Downloads Instagram / TikTok / YouTube media using yt-dlp.
    Uses cookies, supports Reels, Posts, and Videos.
    """
    logger.info(f"⬇️ Running yt-dlp for: {url}")

    cookies = os.path.join(os.getcwd(), "cookies.txt")
    has_cookies = os.path.exists(cookies)
    logger.info(f"🍪 Cookies loaded: {has_cookies}")

    out_path = os.path.join(tmpdir, "output.%(ext)s")
    fmt = "bestaudio/best" if audio_only else "b"

    cmd = [
        YTDLP_BIN, *YTDLP_ARGS,
        "-f", fmt,
        "-o", out_path,
        "--no-playlist",
        "--no-warnings",
        "--socket-timeout", "60",
        "--retries", "3",
        "--geo-bypass",
        "--merge-output-format", "mp4",
        "--extractor-args", "instagram:storyitem_webpage=True",
        "--no-color",
    ]

    if has_cookies:
        cmd += ["--cookies", cookies]

    cmd.append(url)

    try:
        stdout, stderr = await _run(cmd)
        logger.info(f"✅ yt-dlp finished for {url}")
        return out_path
    except Exception as e:
        logger.error(f"yt-dlp primary attempt failed: {e}")
        raise RuntimeError(f"yt-dlp failed: {e}")


# ───────────────────────────────────────────────
# 📥 Download from Telegram or URL
# ───────────────────────────────────────────────
async def download_from_text_or_url(
    message: Message, tmpdir: str, audio_only: bool = False
) -> str:
    """
    Downloads either a Telegram file or a media URL.
    Returns local path to saved file.
    """
    if message.text and _is_url(message.text.strip()):
        return await run_yt_dlp(message.text.strip(), tmpdir, audio_only)

    # Telegram file fallback
    file = message.video or message.audio or message.document
    if not file:
        raise RuntimeError("⚠️ No URL or file supplied.")

    if file.file_size and file.file_size > MAX_FILE_BYTES:
        raise RuntimeError(
            f"⚠️ File too large (> {MAX_FILE_BYTES / 1024 / 1024:.0f} MB)."
        )

    suffix = ".mp4" if message.video else ".mp3" if message.audio else ".bin"
    out_path = os.path.join(tmpdir, f"upload{suffix}")
    await file.download(destination=out_path)
    return out_path


# ───────────────────────────────────────────────
# 🎧 Audio Extractor (MP3)
# ───────────────────────────────────────────────
async def extract_audio_mp3(in_path: str, out_path: str) -> str:
    """Converts any video to MP3 using ffmpeg."""
    cmd = [
        FFMPEG_BIN,
        "-y",
        "-i", in_path,
        "-vn",
        "-acodec", "libmp3lame",
        "-q:a", "2",
        out_path,
    ]
    try:
        await _run(cmd)
        return out_path
    except Exception as e:
        raise RuntimeError(f"❌ ffmpeg failed: {e}")
