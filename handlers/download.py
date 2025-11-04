"""
Enhanced download handler with comprehensive error handling,
rate limiting, and support for Instagram, TikTok, YouTube, and more
"""
import os
import shutil
import tempfile
import asyncio
import logging
from collections import defaultdict
import time
from aiogram import Router
from aiogram.types import Message, FSInputFile
from utils.downloader import download_from_url, check_video_size, detect_platform

router = Router(name="download")
logger = logging.getLogger("download")

MAX_TG_FILE_SIZE = 50 * 1024 * 1024  # Telegram limit

# ───────────────────────────────────────────────
# Rate Limiting
# ───────────────────────────────────────────────
class RateLimiter:
    def __init__(self, max_requests=10, time_window=60):
        self.requests = defaultdict(list)
        self.max_requests = max_requests
        self.time_window = time_window
    
    def is_allowed(self, user_id: int) -> bool:
        now = time.time()
        # Clean old requests
        self.requests[user_id] = [
            req_time for req_time in self.requests[user_id]
            if now - req_time < self.time_window
        ]
        
        if len(self.requests[user_id]) >= self.max_requests:
            return False
        
        self.requests[user_id].append(now)
        return True
    
    def time_until_allowed(self, user_id: int) -> int:
        """Returns seconds until user can make another request"""
        if not self.requests[user_id]:
            return 0
        
        oldest = self.requests[user_id][0]
        elapsed = time.time() - oldest
        remaining = self.time_window - elapsed
        return max(0, int(remaining))


rate_limiter = RateLimiter(max_requests=10, time_window=60)


# ───────────────────────────────────────────────
# Compress large videos using ffmpeg
# ───────────────────────────────────────────────
async def compress_video(input_path: str, output_path: str, target_size_mb: int = 45):
    """
    Compress video to fit Telegram's 50MB limit with 5MB buffer
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", "scale='min(1280,iw)':min'(720,ih)':force_original_aspect_ratio=decrease",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "28",
        "-b:v", "1500k",
        "-maxrate", "2000k",
        "-bufsize", "3000k",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        output_path,
    ]
    
    proc = await asyncio.create_subprocess_exec(
        *cmd, 
        stdout=asyncio.subprocess.PIPE, 
        stderr=asyncio.subprocess.PIPE
    )
    await proc.communicate()
    
    if proc.returncode == 0 and os.path.exists(output_path):
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        logger.info(f"✅ Compressed video to {size_mb:.2f}MB")
        return True
    
    return False


# ───────────────────────────────────────────────
# 🎬 Universal Download Handler (All Platforms)
# ───────────────────────────────────────────────
@router.message(lambda m: m.text and any(
    domain in (m.text or "").lower() 
    for domain in ["instagram.com", "tiktok.com", "youtu", "twitter.com", "x.com", "facebook.com", "fb.watch"]
))
async def handle_link_download(message: Message):
    """
    Handles all supported social media links with intelligent routing
    """
    url = message.text.strip()
    user_id = message.from_user.id
    
    # Rate limiting check
    if not rate_limiter.is_allowed(user_id):
        wait_time = rate_limiter.time_until_allowed(user_id)
        await message.answer(
            f"⏱ Rate limit exceeded. Please wait {wait_time} seconds.\n"
            f"Limit: 10 downloads per minute"
        )
        return
    
    platform = detect_platform(url)
    logger.info(f"📥 Download request from user {user_id} ({message.from_user.username or 'no username'})")
    logger.info(f"🌐 Platform: {platform}, URL: {url}")
    
    status_msg = await message.answer(
        f"🎬 Processing your {platform.title()} media...\n"
        "⏳ This may take a moment..."
    )
    
    tmpdir = tempfile.mkdtemp(prefix="media_")
    
    try:
        # Step 1: Check size for non-Instagram platforms
        if platform != "instagram":
            await status_msg.edit_text(
                f"📊 Checking video size...\n"
                f"Platform: {platform.title()}"
            )
            
            size_info = await check_video_size(url, max_size_mb=50)
            
            if not size_info.get('can_download') and 'reason' in size_info:
                await status_msg.edit_text(
                    f"❌ {size_info['reason']}\n\n"
                    "💡 Try:\n"
                    "• Requesting a shorter clip\n"
                    "• Audio extraction instead (coming soon)"
                )
                return
            
            if size_info.get('size_mb'):
                await status_msg.edit_text(
                    f"⬇️ Downloading {platform.title()} media...\n"
                    f"📦 Size: ~{size_info['size_mb']}MB\n"
                    f"🎬 Resolution: {size_info.get('resolution', 'unknown')}"
                )
        else:
            await status_msg.edit_text(
                f"⬇️ Downloading from Instagram...\n"
                "🔐 Using authenticated API"
            )
        
        # Step 2: Download
        result = await download_from_url(url, tmpdir, audio_only=False)
        
        if not result.get('success'):
            error_msg = result.get('error', 'Unknown error')
            await status_msg.edit_text(f"❌ Download failed: {error_msg}")
            return
        
        paths = result.get('paths', [])
        if not paths:
            await status_msg.edit_text("❌ No files downloaded")
            return
        
        logger.info(f"✅ Downloaded {len(paths)} file(s)")
        
        # Step 3: Send files to user
        await status_msg.edit_text(
            f"⬆️ Uploading {len(paths)} file(s) to Telegram..."
        )
        
        sent_count = 0
        for file_path in paths:
            size = os.path.getsize(file_path)
            ext = os.path.splitext(file_path)[1].lower()
            
            # Handle images
            if ext in [".jpg", ".jpeg", ".png", ".webp"]:
                try:
                    await message.answer_photo(
                        FSInputFile(file_path),
                        caption=f"📸 Downloaded from {platform.title()}\n{url}"
                    )
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Failed to send photo: {e}")
            
            # Handle videos
            elif ext in [".mp4", ".mov", ".mkv", ".avi", ".webm"]:
                # Compress if too large
                if size > MAX_TG_FILE_SIZE:
                    compressed_path = os.path.join(tmpdir, "compressed.mp4")
                    await status_msg.edit_text(
                        f"⚙️ Compressing video ({size / (1024*1024):.1f}MB → ~45MB)..."
                    )
                    
                    success = await compress_video(file_path, compressed_path)
                    if success and os.path.getsize(compressed_path) < MAX_TG_FILE_SIZE:
                        file_path = compressed_path
                    else:
                        await message.answer(
                            f"⚠️ Video too large to send ({size / (1024*1024):.1f}MB)\n"
                            f"Telegram limit: 50MB\n\n"
                            f"View here: {url}"
                        )
                        continue
                
                try:
                    caption = f"🎥 Downloaded from {platform.title()}"
                    
                    # Add metadata for Instagram
                    if platform == "instagram" and result.get('caption'):
                        caption += f"\n\n{result['caption'][:200]}"
                    
                    await message.answer_video(
                        FSInputFile(file_path),
                        caption=caption,
                        supports_streaming=True
                    )
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Failed to send video: {e}")
                    await message.answer(f"⚠️ Failed to upload video: {str(e)}")
        
        # Delete status message
        await status_msg.delete()
        
        if sent_count == 0:
            await message.answer(
                "⚠️ No media could be extracted from this post.\n"
                "It may be private, deleted, or contain unsupported content."
            )
        else:
            logger.info(f"✅ Successfully sent {sent_count} file(s) to user {user_id}")
    
    except Exception as e:
        logger.exception(f"❌ Download handler error for {url}")
        
        # User-friendly error messages
        error_msg = str(e)
        
        if "Private" in error_msg or "private" in error_msg:
            await status_msg.edit_text(
                "🔒 This content is private.\n\n"
                "For Instagram: The bot account must follow this user first.\n"
                "For other platforms: Content may require authentication."
            )
        elif "Bot detection" in error_msg or "sign in" in error_msg.lower():
            await status_msg.edit_text(
                "🤖 Bot detection triggered.\n\n"
                "Platform detected automated access. Try again in a few minutes."
            )
        elif "403" in error_msg or "Forbidden" in error_msg:
            await status_msg.edit_text(
                "🚫 Access forbidden.\n\n"
                "This content may be:\n"
                "• Geo-blocked in your region\n"
                "• Requiring authentication\n"
                "• Deleted or unavailable"
            )
        elif "not found" in error_msg.lower() or "404" in error_msg:
            await status_msg.edit_text(
                "❌ Content not found.\n\n"
                "The post may have been deleted or the link is incorrect."
            )
        else:
            await status_msg.edit_text(
                f"❌ Download failed: {error_msg[:200]}\n\n"
                "💡 Try:\n"
                "• Checking if the link is correct\n"
                "• Waiting a few minutes\n"
                "• Using a different platform link"
            )
    
    finally:
        # Cleanup
        await asyncio.sleep(2)
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception as e:
            logger.warning(f"⚠️ Temp cleanup failed: {e}")


# ───────────────────────────────────────────────
# 🎵 Audio extraction command
# ───────────────────────────────────────────────
@router.message(lambda m: m.text and m.text.startswith('/mp3 ') or m.text.startswith('/audio '))
async def handle_audio_extraction(message: Message):
    """
    Extract audio from video URL
    Usage: /mp3 <URL> or /audio <URL>
    """
    user_id = message.from_user.id
    
    if not rate_limiter.is_allowed(user_id):
        wait_time = rate_limiter.time_until_allowed(user_id)
        await message.answer(f"⏱ Rate limit: wait {wait_time}s")
        return
    
    url = message.text.split(maxsplit=1)[1].strip()
    platform = detect_platform(url)
    
    status_msg = await message.answer("🎵 Extracting audio...")
    tmpdir = tempfile.mkdtemp(prefix="audio_")
    
    try:
        result = await download_from_url(url, tmpdir, audio_only=True)
        
        if not result.get('success'):
            await status_msg.edit_text(f"❌ {result.get('error')}")
            return
        
        paths = result.get('paths', [])
        audio_file = None
        
        # Find MP3 file
        for path in paths:
            if path.endswith('.mp3'):
                audio_file = path
                break
        
        if not audio_file:
            await status_msg.edit_text("❌ No audio extracted")
            return
        
        await message.answer_audio(
            FSInputFile(audio_file),
            caption=f"🎵 Audio extracted from {platform.title()}"
        )
        
        await status_msg.delete()
        
    except Exception as e:
        logger.exception("Audio extraction failed")
        await status_msg.edit_text(f"❌ Audio extraction failed: {str(e)[:100]}")
    
    finally:
        await asyncio.sleep(2)
        shutil.rmtree(tmpdir, ignore_errors=True)