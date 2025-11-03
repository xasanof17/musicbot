from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu_kb():
    """Main menu with essential options only."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎬 Download Video", callback_data="menu_download"),
                InlineKeyboardButton(text="🎧 Identify Song", callback_data="menu_identify"),
            ],
            [
                InlineKeyboardButton(text="⚙️ Settings", callback_data="settings"),
            ],
        ]
    )


def settings_kb():
    """Settings menu."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔙 Back", callback_data="home"),
            ]
        ]
    )


def progress_kb(stage="idle"):
    """
    Minimal placeholder for backwards compatibility.
    You can safely remove old retry/cancel buttons.
    """
    if stage == "downloading":
        text = "⏳ Downloading..."
    elif stage == "done":
        text = "✅ Done!"
    else:
        text = "🕹 Ready"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, callback_data="noop")]
        ]
    )
