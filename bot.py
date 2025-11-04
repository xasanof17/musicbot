import asyncio
import logging
import os
import shutil
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

from utils.logger import configure_logging
from handlers.start import router as start_router
from handlers.buttons import router as buttons_router
from handlers.download import router as download_router
from handlers.identify import router as identify_router
from handlers.audio import router as audio_router


# ───────────────────────────────────────────────
# ENV + SETUP
# ───────────────────────────────────────────────
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")
ACOUSTID_API_KEY = os.getenv("ACOUSTID_API_KEY")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

# ───────────────────────────────────────────────
# LOGGING
# ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("MusicBot")

# ───────────────────────────────────────────────
# BOT FACTORY
# ───────────────────────────────────────────────
def make_bot() -> Bot:
    return Bot(
        token=TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

def make_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(start_router)
    dp.include_router(buttons_router)
    dp.include_router(download_router)
    dp.include_router(identify_router)
    dp.include_router(audio_router)
    return dp


# ───────────────────────────────────────────────
# HEALTH CHECK
# ───────────────────────────────────────────────
def health_check():
    print("\n═════════════ 🎵 MusicBot Startup Check ═════════════")
    print(f"💬 Telegram Token: {'✅ Loaded' if TELEGRAM_BOT_TOKEN else '❌ Missing'}")
    print(f"📸 Instagram Username: {'✅ Loaded' if INSTAGRAM_USERNAME else '⚠️ Missing (Instagram downloads will fail)'}")
    print(f"🔐 Instagram Password: {'✅ Loaded' if INSTAGRAM_PASSWORD else '⚠️ Missing (Instagram downloads will fail)'}")
    print(f"🔍 AcoustID Key: {'✅ Loaded' if ACOUSTID_API_KEY else '⚠️ Missing (Song ID disabled)'}")
    print(f"🎧 Spotify ID: {'✅ Loaded' if SPOTIFY_CLIENT_ID else '⚠️ Missing (Spotify search disabled)'}")
    print(f"🎧 Spotify Secret: {'✅ Loaded' if SPOTIFY_CLIENT_SECRET else '⚠️ Missing (Spotify search disabled)'}")
    print(f"🎼 ffmpeg binary: {'✅ Found' if shutil.which('ffmpeg') else '❌ Not Found'}")
    print(f"🎥 yt-dlp: {'✅ Installed' if shutil.which('yt-dlp') else '⚠️ Not Found (will use python module)'}")
    print("═════════════════════════════════════════════════════\n")
    
    # Critical checks
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("❌ TELEGRAM_BOT_TOKEN is required!")
    
    if not INSTAGRAM_USERNAME or not INSTAGRAM_PASSWORD:
        logger.warning("⚠️ Instagram credentials missing - Instagram downloads will fail!")
        logger.warning("⚠️ Add INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD to .env file")
    
    if not shutil.which('ffmpeg'):
        logger.warning("⚠️ ffmpeg not found - video/audio processing will fail!")


# ───────────────────────────────────────────────
# MAIN
# ───────────────────────────────────────────────
async def main():
    configure_logging()
    health_check()

    bot = make_bot()
    dp = make_dispatcher()

    logger.info("🚀 Starting Enhanced MusicBot (Instagram + TikTok + YouTube)")
    logger.info("📥 Supported platforms: Instagram, TikTok, YouTube, Twitter, Facebook")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())