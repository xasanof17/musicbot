"""
Enhanced media downloader with production-ready yt-dlp configuration,
Instagram instagrapi integration, and comprehensive error handling
"""
import asyncio
import os
import re
import sys
import logging
import random
from typing import Dict, Optional, List
from aiogram.types import Message

logger = logging.getLogger("downloader")

# ───────────────────────────────────────────────
# ⚙️ Constants
# ───────────────────────────────────────────────
YTDLP_BIN = sys.executable
YTDLP_ARGS = ["-m", "yt_dlp"]
FFMPEG_BIN = "ffmpeg"
MAX_FILE_BYTES = 50 * 1024 * 1024  # 50 MB Telegram limit (not 200)


# ───────────────────────────────────────────────
# 🔍 URL detection and platform identification
# ───────────────────────────────────────────────
def _is_url(text: str) -> bool:
    """Check if text is a valid URL"""
    return bool(re.match(r"https?://", text or ""))


def detect_platform(url: str) -> str:
    """Detect which platform the URL is from"""
    url_lower = url.lower()
    
    if "instagram.com" in url_lower or "instagr.am" in url_lower:
        return "instagram"
    elif "tiktok.com" in url_lower or "vm.tiktok.com" in url_lower:
        return "tiktok"
    elif "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "youtube"
    elif "twitter.com" in url_lower or "x.com" in url_lower:
        return "twitter"
    elif "facebook.com" in url_lower or "fb.watch" in url_lower:
        return "facebook"
    else:
        return "other"


# ───────────────────────────────────────────────
# ⚙️ Async subprocess runner
# ───────────────────────────────────────────────
async def _run(cmd: List[str]) -> tuple[str, str]:
    """Executes an async subprocess and captures output."""
    if cmd[0] == "yt-dlp":
        cmd = [sys.executable, "-m", "yt_dlp"] + cmd[1:]

    proc = await asyncio.create_subprocess_exec(
        *cmd, 
        stdout=asyncio.subprocess.PIPE, 
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        error_msg = stderr.decode(errors='ignore')
        logger.error(f"Command failed: {' '.join(cmd)}\n{error_msg}")
        raise RuntimeError(f"Command failed: {error_msg}")

    return stdout.decode(errors="ignore"), stderr.decode(errors="ignore")


# ───────────────────────────────────────────────
# 📊 Pre-download size checking
# ───────────────────────────────────────────────
async def check_video_size(url: str, max_size_mb: int = 50) -> Dict:
    """
    Check video size before downloading to avoid wasting bandwidth
    
    Returns:
        Dict with 'can_download', 'size_mb', 'resolution', 'format_id'
    """
    platform = detect_platform(url)
    
    # Instagram uses instagrapi - can't check size beforehand easily
    if platform == "instagram":
        return {
            'can_download': True,
            'platform': 'instagram',
            'note': 'Size check unavailable for Instagram'
        }
    
    cmd = [
        YTDLP_BIN, *YTDLP_ARGS,
        "--dump-json",
        "--no-warnings",
        "--no-playlist",
        url
    ]
    
    try:
        stdout, _ = await _run(cmd)
        import json
        info = json.loads(stdout)
        
        formats = info.get('formats', [])
        # Find best format under size limit
        for fmt in sorted(formats, key=lambda x: x.get('filesize', 0) or 0, reverse=True):
            size = fmt.get('filesize') or fmt.get('filesize_approx') or 0
            if 0 < size < max_size_mb * 1024 * 1024:
                return {
                    'can_download': True,
                    'format_id': fmt.get('format_id'),
                    'size_mb': round(size / (1024 * 1024), 2),
                    'resolution': fmt.get('resolution', 'unknown'),
                    'ext': fmt.get('ext', 'mp4')
                }
        
        return {
            'can_download': False,
            'reason': f'No format found under {max_size_mb}MB'
        }
        
    except Exception as e:
        logger.warning(f"Size check failed: {e}")
        # Allow download to proceed if size check fails
        return {
            'can_download': True,
            'note': 'Size check failed, attempting download anyway'
        }


# ───────────────────────────────────────────────
# 🎬 Instagram downloader (using instagrapi)
# ───────────────────────────────────────────────
async def download_instagram(url: str, tmpdir: str) -> Dict:
    """
    Download Instagram content using instagrapi for 90%+ reliability
    
    Returns:
        Dict with 'success', 'paths', 'caption', 'type'
    """
    try:
        from utils.instagram_downloader import get_instagram_downloader
        
        ig = get_instagram_downloader()
        
        # Run in executor since instagrapi is blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: ig.download_content(url, tmpdir)
        )
        
        return result
        
    except ImportError:
        logger.error("❌ instagrapi not installed - falling back to yt-dlp")
        # Fallback to yt-dlp if instagrapi unavailable
        return await run_yt_dlp(url, tmpdir, audio_only=False)
    except Exception as e:
        logger.error(f"❌ Instagram download failed: {e}")
        raise RuntimeError(f"Instagram download failed: {e}")


# ───────────────────────────────────────────────
# 🎬 Universal yt-dlp runner with platform-specific configs
# ───────────────────────────────────────────────
async def run_yt_dlp(url: str, tmpdir: str, audio_only: bool = False) -> Dict:
    """
    Downloads media using yt-dlp with optimized platform-specific settings
    
    Returns:
        Dict with 'success', 'paths', 'title', 'ext'
    """
    logger.info(f"⬇️ Running yt-dlp for: {url}")
    
    platform = detect_platform(url)
    cookies = os.path.join(os.getcwd(), "cookies.txt")
    has_cookies = os.path.exists(cookies)
    
    out_path = os.path.join(tmpdir, "output.%(ext)s")
    
    # Format selection with Telegram 50MB limit
    if audio_only:
        fmt = "bestaudio/best"
    else:
        # Try formats under 50MB, fallback to lower quality
        fmt = (
            f"best[filesize<50M]/"
            f"bv*[height<=720][filesize<50M]+ba/"
            f"bv*[height<=480]+ba/"
            "worst"
        )
    
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
        "--no-color",
    ]
    
    # Platform-specific configurations
    if platform == "tiktok":
        cmd += [
            "--extractor-args", 
            "tiktok:api_hostname=api22-normal-c-alisg.tiktokv.com"
        ]
    elif platform == "instagram":
        cmd += [
            "--extractor-args", 
            "instagram:storyitem_webpage=True"
        ]
    elif platform == "youtube":
        # YouTube requires cookies for age-restricted content
        if not has_cookies:
            logger.warning("⚠️ No cookies found - age-restricted YouTube videos may fail")
    
    # Add cookies if available
    if has_cookies:
        cmd += ["--cookies", cookies]
        logger.info("🍪 Using cookies for authentication")
    
    cmd.append(url)
    
    try:
        stdout, stderr = await _run(cmd)
        
        # Find downloaded files
        files = [
            os.path.join(tmpdir, f) 
            for f in os.listdir(tmpdir) 
            if not f.startswith('.')
        ]
        
        if not files:
            raise RuntimeError("No files downloaded")
        
        logger.info(f"✅ Downloaded {len(files)} file(s)")
        
        return {
            'success': True,
            'paths': files,
            'platform': platform
        }
        
    except Exception as e:
        logger.error(f"❌ yt-dlp failed: {e}")
        
        # Provide helpful error messages
        error_str = str(e).lower()
        if 'sign in' in error_str or 'bot' in error_str:
            raise RuntimeError(
                "Bot detection triggered. "
                "Try: 1) Add cookies.txt file, 2) Update yt-dlp, 3) Use VPN"
            )
        elif '403' in error_str or 'forbidden' in error_str:
            raise RuntimeError(
                "Access forbidden. The content may be private or geo-blocked. "
                "Try adding valid cookies or using a VPN."
            )
        elif 'private' in error_str:
            raise RuntimeError(
                "Private content - authentication required"
            )
        else:
            raise RuntimeError(f"Download failed: {e}")


# ───────────────────────────────────────────────
# 🎧 Audio Extractor (MP3)
# ───────────────────────────────────────────────
async def extract_audio_mp3(in_path: str, out_path: str, quality: str = "192") -> str:
    """
    Converts any video to MP3 using ffmpeg
    
    Args:
        in_path: Input video file
        out_path: Output MP3 file
        quality: Bitrate (0=best VBR, 128, 192, 256, 320)
    """
    cmd = [
        FFMPEG_BIN,
        "-y",
        "-i", in_path,
        "-vn",
        "-acodec", "libmp3lame",
        "-q:a", "2" if quality == "0" else "4",  # VBR quality
        "-b:a", f"{quality}k" if quality != "0" else None,
        out_path,
    ]
    
    # Remove None values
    cmd = [c for c in cmd if c is not None]
    
    try:
        await _run(cmd)
        logger.info(f"✅ Extracted audio to {out_path}")
        return out_path
    except Exception as e:
        raise RuntimeError(f"❌ ffmpeg audio extraction failed: {e}")


# ───────────────────────────────────────────────
# 📥 Main download function with platform routing
# ───────────────────────────────────────────────
async def download_from_url(url: str, tmpdir: str, audio_only: bool = False) -> Dict:
    """
    Universal download function that routes to the best downloader
    
    Args:
        url: Media URL from any supported platform
        tmpdir: Temporary directory for downloads
        audio_only: Extract audio only (MP3)
        
    Returns:
        Dict with 'success', 'paths', and platform-specific metadata
    """
    platform = detect_platform(url)
    logger.info(f"🌐 Detected platform: {platform}")
    
    # Route to appropriate downloader
    if platform == "instagram":
        result = await download_instagram(url, tmpdir)
        
        # Convert to audio if requested
        if audio_only and result.get('success'):
            audio_paths = []
            for path in result['paths']:
                if path.endswith(('.mp4', '.mov', '.mkv')):
                    audio_path = path.rsplit('.', 1)[0] + '.mp3'
                    await extract_audio_mp3(path, audio_path)
                    audio_paths.append(audio_path)
            result['paths'] = audio_paths
        
        return result
    else:
        # Use yt-dlp for all other platforms
        return await run_yt_dlp(url, tmpdir, audio_only)


# ───────────────────────────────────────────────
# 📥 Download from Telegram message or URL
# ───────────────────────────────────────────────
async def download_from_text_or_url(
    message: Message, tmpdir: str, audio_only: bool = False
) -> str:
    """
    Downloads either a Telegram file or a media URL.
    Returns local path to saved file.
    """
    # Check if message contains URL
    if message.text and _is_url(message.text.strip()):
        result = await download_from_url(message.text.strip(), tmpdir, audio_only)
        
        if not result.get('success'):
            raise RuntimeError(result.get('error', 'Download failed'))
        
        # Return first file path
        paths = result.get('paths', [])
        if not paths:
            raise RuntimeError("No files downloaded")
        
        return paths[0]

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

async def run_yt_dlp_tiktok_enhanced(url: str, tmpdir: str, audio_only: bool = False) -> Dict:
    """
    Enhanced TikTok downloader with multiple retry strategies
    """
    logger.info(f"⬇️ Running enhanced TikTok downloader for: {url}")
    
    cookies = os.path.join(os.getcwd(), "cookies.txt")
    has_cookies = os.path.exists(cookies)
    
    # TikTok-specific strategies
    strategies = [
        {
            'name': 'API v1 (US East)',
            'api_hostname': 'api16-normal-c-useast1a.tiktokv.com',
            'timeout': 30,
            'retries': 5
        },
        {
            'name': 'API v2 (Singapore)',
            'api_hostname': 'api22-normal-c-alisg.tiktokv.com',
            'timeout': 45,
            'retries': 8
        },
        {
            'name': 'API v3 (US East 2)',
            'api_hostname': 'api19-normal-c-useast2a.tiktokv.com',
            'timeout': 60,
            'retries': 10
        },
        {
            'name': 'Mobile API',
            'api_hostname': 'api16-normal-c-useast1a.tiktokv.com',
            'timeout': 90,
            'retries': 15,
            'mobile': True
        }
    ]
    
    last_error = None
    
    for i, strategy in enumerate(strategies, 1):
        try:
            logger.info(f"🔄 TikTok Strategy {i}/{len(strategies)}: {strategy['name']}")
            
            out_path = os.path.join(tmpdir, "output.%(ext)s")
            fmt = "bestaudio/best" if audio_only else "best"
            
            cmd = [
                YTDLP_BIN, *YTDLP_ARGS,
                "-f", fmt,
                "-o", out_path,
                "--no-playlist",
                "--no-warnings",
                "--socket-timeout", str(strategy['timeout']),
                "--retries", str(strategy['retries']),
                "--fragment-retries", str(strategy['retries']),
                "--geo-bypass",
                "--merge-output-format", "mp4",
                "--no-color",
                "--extractor-args", f"tiktok:api_hostname={strategy['api_hostname']}",
            ]
            
            # Add user agent
            if strategy.get('mobile'):
                user_agent = "com.zhiliaoapp.musically/2023600050 (Linux; U; Android 13)"
            else:
                user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
            
            cmd += ["--user-agent", user_agent]
            
            # Add cookies if available
            if has_cookies:
                cmd += ["--cookies", cookies]
                logger.info("🍪 Using cookies")
            
            cmd.append(url)
            
            # Run with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    _run(cmd),
                    timeout=strategy['timeout'] + 30  # Extra time for processing
                )
                
                # Check for downloaded files
                files = [
                    os.path.join(tmpdir, f) 
                    for f in os.listdir(tmpdir) 
                    if not f.startswith('.')
                ]
                
                if files:
                    logger.info(f"✅ TikTok download succeeded with {strategy['name']}")
                    return {
                        'success': True,
                        'paths': files,
                        'platform': 'tiktok',
                        'method': strategy['name']
                    }
                    
            except asyncio.TimeoutError:
                last_error = f"Timeout after {strategy['timeout']}s"
                logger.warning(f"⏱️ Strategy {i} timed out")
                
        except Exception as e:
            last_error = str(e)
            logger.warning(f"⚠️ Strategy {i} failed: {str(e)[:100]}")
        
        # Wait between strategies with exponential backoff
        if i < len(strategies):
            wait_time = i * 3  # 3s, 6s, 9s
            logger.info(f"⏳ Waiting {wait_time}s before next attempt...")
            await asyncio.sleep(wait_time)
            
            # Clear cache before retry
            if i == 2:  # Clear cache on 2nd retry
                try:
                    cache_cmd = [YTDLP_BIN, *YTDLP_ARGS, "--rm-cache-dir"]
                    await _run(cache_cmd)
                    logger.info("🗑️ Cleared yt-dlp cache")
                except:
                    pass
    
    # All strategies failed
    raise RuntimeError(
        f"TikTok download failed after {len(strategies)} attempts. "
        f"TikTok may be blocking requests. Try: 1) Update yt-dlp, "
        f"2) Add fresh cookies, 3) Use VPN. Last error: {last_error}"
    )


# Update the main run_yt_dlp function to use enhanced TikTok handler:

async def run_yt_dlp(url: str, tmpdir: str, audio_only: bool = False) -> Dict:
    """
    Downloads media using yt-dlp with optimized platform-specific settings
    Enhanced TikTok support with retry logic
    """
    platform = detect_platform(url)
    logger.info(f"⬇️ Running yt-dlp for: {url}")
    
    # Use enhanced TikTok downloader
    if platform == "tiktok":
        return await run_yt_dlp_tiktok_enhanced(url, tmpdir, audio_only)
    
    # Rest of the function remains the same for other platforms...
    cookies = os.path.join(os.getcwd(), "cookies.txt")
    has_cookies = os.path.exists(cookies)
    
    out_path = os.path.join(tmpdir, "output.%(ext)s")
    
    # Format selection with Telegram 50MB limit
    if audio_only:
        fmt = "bestaudio/best"
    else:
        fmt = (
            f"best[filesize<50M]/"
            f"bv*[height<=720][filesize<50M]+ba/"
            f"bv*[height<=480]+ba/"
            "worst"
        )
    
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
        "--no-color",
    ]
    
    # Platform-specific configurations
    if platform == "instagram":
        cmd += ["--extractor-args", "instagram:storyitem_webpage=True"]
    elif platform == "youtube":
        if not has_cookies:
            logger.warning("⚠️ No cookies - age-restricted YouTube may fail")
    
    # Add cookies if available
    if has_cookies:
        cmd += ["--cookies", cookies]
        logger.info("🍪 Using cookies")
    
    cmd.append(url)
    
    try:
        stdout, stderr = await _run(cmd)
        
        files = [
            os.path.join(tmpdir, f) 
            for f in os.listdir(tmpdir) 
            if not f.startswith('.')
        ]
        
        if not files:
            raise RuntimeError("No files downloaded")
        
        logger.info(f"✅ Downloaded {len(files)} file(s)")
        
        return {
            'success': True,
            'paths': files,
            'platform': platform
        }
        
    except Exception as e:
        logger.error(f"❌ yt-dlp failed: {e}")
        
        # Provide helpful error messages
        error_str = str(e).lower()
        if 'sign in' in error_str or 'bot' in error_str:
            raise RuntimeError(
                "Bot detection. Try: 1) Add cookies.txt, 2) Update yt-dlp, 3) Use VPN"
            )
        elif '403' in error_str or 'forbidden' in error_str:
            raise RuntimeError(
                "Access forbidden. Content may be private/geo-blocked. Try cookies or VPN."
            )
        elif 'timeout' in error_str or 'timed out' in error_str:
            raise RuntimeError(
                "Connection timeout. Check your internet or try again."
            )
        else:
            raise RuntimeError(f"Download failed: {e}")
