# templates/messages.py

START_TEXT = (
    "🎵 <b>Welcome to MusicBot!</b>\n\n"
    "Send me any video or music link — YouTube, TikTok, Instagram, you name it — "
    "and I’ll handle the rest for you automatically.\n\n"
    "✨ What I can do:\n"
    "• 🎬 Download videos\n"
    "• 🎧 Extract music\n"
    "• 🧠 Identify songs\n\n"
    "Ready? Choose an option below 👇"
)

HOME_TEXT = (
    "🏠 <b>Main Menu</b>\n\n"
    "You’re back at the start.\n"
    "Send me a link, a video, or a voice message — "
    "I’ll download it or tell you what song it is 🎶"
)


HELP_TEXT = (
    "❓ <b>How to use MusicBot</b>\n\n"
    "1️⃣ Send any video or audio link (YouTube, TikTok, Instagram, etc.)\n"
    "2️⃣ Or upload a video / voice clip to identify its song 🎧\n"
    "3️⃣ Tap buttons to download, extract, or analyze.\n\n"
    "💡 Tips:\n"
    "• Use /start to return to main menu\n"
    "• Use /settings to change preferences\n"
    "• Works with most major platforms 🌍"
)

ABOUT_TEXT = (
    "ℹ️ <b>About MusicBot</b>\n\n"
    "MusicBot is powered by open-source tools:\n"
    "• <b>yt-dlp</b> for downloads\n"
    "• <b>ffmpeg</b> for conversions\n"
    "• <b>AcoustID + MusicBrainz</b> for song recognition\n\n"
    "Made with ❤️ using <b>Aiogram 3.x</b> and deployed on <b>Railway</b>."
)

MENU_DOWNLOAD_TEXT = (
    "🎬 <b>Video Downloader</b>\n\n"
    "Send any video link — YouTube, TikTok, Instagram, etc. — "
    "and I’ll download it for you automatically."
)

MENU_IDENTIFY_TEXT = (
    "🧠 <b>Identify a Song</b>\n\n"
    "Send me a short audio or voice clip (5–15 seconds) "
    "and I’ll tell you the song name and artist 🎶"
)

SETTINGS_TEXT = (
    "⚙️ <b>Bot Settings</b>\n\n"
    "Customize your experience:\n"
    "• Audio quality (MP3 bitrate)\n"
    "• Default mode (Video / Music)\n"
    "• Language preferences 🌍"
)
