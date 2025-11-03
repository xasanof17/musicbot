import os
import tempfile
import asyncio
import logging
from aiogram import Router
from aiogram.types import CallbackQuery, FSInputFile
from aiogram.exceptions import TelegramBadRequest

from templates.buttons import main_menu_kb, settings_kb, progress_kb
from templates.messages import (
    MENU_DOWNLOAD_TEXT,
    MENU_IDENTIFY_TEXT,
    SETTINGS_TEXT,
    HOME_TEXT,
)
from utils.downloader import download_from_text_or_url
from utils.recognizer import identify_audio

router = Router(name="buttons")
logger = logging.getLogger("buttons")

# ───────────────────────────────────────────────
# Safe edit helper
# ───────────────────────────────────────────────
async def safe_edit(c: CallbackQuery, text: str, reply_markup=None):
    """Safely edits a message, avoids 'no text to edit' errors."""
    try:
        await c.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as e:
        if "no text" in str(e).lower():
            await c.message.answer(text, reply_markup=reply_markup)
        else:
            logger.exception("❌ Edit text failed.")
            await c.message.answer(text, reply_markup=reply_markup)
    finally:
        await c.answer()


# ───────────────────────────────────────────────
# Main menu navigation
# ───────────────────────────────────────────────
@router.callback_query(lambda c: c.data == "home")
async def cb_home(c: CallbackQuery):
    await safe_edit(c, HOME_TEXT, main_menu_kb())


@router.callback_query(lambda c: c.data == "menu_download")
async def cb_menu_download(c: CallbackQuery):
    await safe_edit(c, MENU_DOWNLOAD_TEXT, progress_kb(stage="idle"))


@router.callback_query(lambda c: c.data == "menu_identify")
async def cb_menu_identify(c: CallbackQuery):
    await safe_edit(c, MENU_IDENTIFY_TEXT, progress_kb(stage="idle"))


@router.callback_query(lambda c: c.data == "settings")
async def cb_settings(c: CallbackQuery):
    await safe_edit(c, SETTINGS_TEXT, settings_kb())


@router.callback_query(lambda c: c.data == "cancel")
async def cb_cancel(c: CallbackQuery):
    await safe_edit(c, HOME_TEXT, main_menu_kb())
    await c.answer("❌ Cancelled")


# ───────────────────────────────────────────────
# 🎵 Get Music button
# ───────────────────────────────────────────────
@router.callback_query(lambda c: c.data == "get_music")
async def cb_get_music(c: CallbackQuery):
    """Extracts MP3 from a video URL and identifies its original track."""
    user = c.from_user
    msg_text = c.message.text or c.message.caption

    logger.info(f"🎵 [GET MUSIC] User: {user.username or user.id}, Text: {msg_text}")

    if not msg_text:
        await c.answer("⚠️ No media link found.", show_alert=True)
        return

    await safe_edit(c, "🎧 Extracting audio... Please wait ⏳")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # ── Step 1: download video/audio
            mp3_path = await download_from_text_or_url(msg_text, tmpdir, audio_only=True)
            logger.info(f"✅ MP3 extracted: {mp3_path}")

            # ── Step 2: create a smart hint for recognizer
            hint = (c.message.caption or c.message.text or "").strip() or None

            # ── Step 3: identify via AcoustID / Spotify fallback
            identify_result = await identify_audio(mp3_path, hint=hint)
            logger.info(f"🎶 Identification result: {identify_result}")

            # ── Step 4: send result + file
            caption = (
                f"✅ <b>Audio extracted successfully!</b>\n\n{identify_result}"
                if identify_result else "✅ <b>Here’s your audio file.</b>"
            )

            await c.message.answer_audio(
                audio=FSInputFile(mp3_path),
                caption=caption,
                parse_mode="HTML",
            )

        # ── cleanup + log
        await c.message.delete()
        logger.info(f"✅ Audio sent successfully to user {user.id}")

    except Exception as e:
        logger.exception("❌ Failed to process 'Get Music' action.")
        await c.message.answer(f"❌ Download or recognition failed: {e}")
