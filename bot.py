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
    print(f"🔍 AcoustID Key: {'✅ Loaded' if ACOUSTID_API_KEY else '❌ Missing'}")
    print(f"🎧 Spotify ID: {'✅ Loaded' if SPOTIFY_CLIENT_ID else '❌ Missing'}")
    print(f"🎧 Spotify Secret: {'✅ Loaded' if SPOTIFY_CLIENT_SECRET else '❌ Missing'}")
    print(f"🎼 fpcalc binary: {'✅ Found' if shutil.which('fpcalc') else '❌ Not Found'}")
    print("═════════════════════════════════════════════════════\n")


# ───────────────────────────────────────────────
# MAIN
# ───────────────────────────────────────────────
async def main():
    configure_logging()
    health_check()

    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("❌ TELEGRAM_BOT_TOKEN is missing!")

    bot = make_bot()
    dp = make_dispatcher()

    logger.info("🚀 Starting MusicBot (Spotify + AcoustID enabled)")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
