"""
Enhanced TikTok Downloader with Retry Logic and Fallback Mechanisms
Handles connection resets, timeouts, and TikTok's anti-bot measures
"""
import asyncio
import os
import logging
import time
from typing import Dict, Optional

logger = logging.getLogger("tiktok_downloader")


async def download_tiktok_enhanced(url: str, tmpdir: str, cookies_path: Optional[str] = None) -> Dict:
    """
    Enhanced TikTok downloader with multiple strategies and retry logic
    
    Strategies:
    1. Try with API hostname and cookies
    2. Try clearing cache and retry
    3. Try with different user agents
    4. Fall back to mobile API
    """
    
    strategies = [
        _strategy_api_with_cookies,
        _strategy_clear_cache_retry,
        _strategy_mobile_api,
        _strategy_basic_download,
    ]
    
    last_error = None
    
    for i, strategy in enumerate(strategies, 1):
        try:
            logger.info(f"🔄 Trying TikTok strategy {i}/{len(strategies)}: {strategy.__name__}")
            result = await strategy(url, tmpdir, cookies_path)
            
            if result.get('success'):
                logger.info(f"✅ TikTok strategy {i} succeeded!")
                return result
                
        except Exception as e:
            last_error = e
            logger.warning(f"⚠️ Strategy {i} failed: {str(e)[:100]}")
            
            # Wait between retries
            if i < len(strategies):
                wait_time = i * 2  # Exponential backoff: 2s, 4s, 6s
                logger.info(f"⏳ Waiting {wait_time}s before next attempt...")
                await asyncio.sleep(wait_time)
    
    # All strategies failed
    return {
        'success': False,
        'error': f'All TikTok download strategies failed. Last error: {str(last_error)}'
    }


async def _run_ytdlp_command(cmd: list) -> tuple[str, str]:
    """Run yt-dlp command with timeout handling"""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)  # 2 min timeout
        return stdout.decode(errors='ignore'), stderr.decode(errors='ignore')
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError("Download timed out after 120 seconds")


async def _strategy_api_with_cookies(url: str, tmpdir: str, cookies_path: Optional[str]) -> Dict:
    """
    Strategy 1: Use API hostname with cookies and optimized settings
    """
    import sys
    
    out_path = os.path.join(tmpdir, "tiktok.%(ext)s")
    
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "-f", "best",  # Simple format selection
        "-o", out_path,
        "--socket-timeout", "30",
        "--retries", "5",
        "--fragment-retries", "5",
        "--no-playlist",
        "--no-warnings",
        "--geo-bypass",
        "--extractor-args", "tiktok:api_hostname=api16-normal-c-useast1a.tiktokv.com",
        "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]
    
    if cookies_path and os.path.exists(cookies_path):
        cmd += ["--cookies", cookies_path]
    
    cmd.append(url)
    
    stdout, stderr = await _run_ytdlp_command(cmd)
    
    # Check if file was downloaded
    files = [f for f in os.listdir(tmpdir) if not f.startswith('.')]
    if files:
        return {
            'success': True,
            'paths': [os.path.join(tmpdir, f) for f in files],
            'method': 'api_with_cookies'
        }
    
    raise RuntimeError("No files downloaded")


async def _strategy_clear_cache_retry(url: str, tmpdir: str, cookies_path: Optional[str]) -> Dict:
    """
    Strategy 2: Clear yt-dlp cache and retry
    """
    import sys
    
    # Clear cache first
    cache_cmd = [sys.executable, "-m", "yt_dlp", "--rm-cache-dir"]
    try:
        await _run_ytdlp_command(cache_cmd)
        logger.info("🗑️ Cleared yt-dlp cache")
    except:
        pass  # Cache clear not critical
    
    # Wait a moment
    await asyncio.sleep(3)
    
    # Try download with different API hostname
    out_path = os.path.join(tmpdir, "tiktok.%(ext)s")
    
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "-f", "best",
        "-o", out_path,
        "--socket-timeout", "45",
        "--retries", "10",
        "--no-playlist",
        "--extractor-args", "tiktok:api_hostname=api22-normal-c-alisg.tiktokv.com",
    ]
    
    if cookies_path and os.path.exists(cookies_path):
        cmd += ["--cookies", cookies_path]
    
    cmd.append(url)
    
    stdout, stderr = await _run_ytdlp_command(cmd)
    
    files = [f for f in os.listdir(tmpdir) if not f.startswith('.')]
    if files:
        return {
            'success': True,
            'paths': [os.path.join(tmpdir, f) for f in files],
            'method': 'cache_cleared'
        }
    
    raise RuntimeError("No files downloaded after cache clear")


async def _strategy_mobile_api(url: str, tmpdir: str, cookies_path: Optional[str]) -> Dict:
    """
    Strategy 3: Try mobile API endpoint
    """
    import sys
    
    out_path = os.path.join(tmpdir, "tiktok.%(ext)s")
    
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "-f", "best",
        "-o", out_path,
        "--socket-timeout", "60",
        "--retries", "8",
        "--extractor-args", "tiktok:api_hostname=api19-normal-c-useast2a.tiktokv.com",
        "--user-agent", "com.zhiliaoapp.musically/2023600050 (Linux; U; Android 13; en_US; Pixel 6; Build/TP1A.220624.014; Cronet/TTNetVersion:6c7b701a 2021-11-22 QuicVersion:47ac2f7f 2021-07-29)",
    ]
    
    if cookies_path and os.path.exists(cookies_path):
        cmd += ["--cookies", cookies_path]
    
    cmd.append(url)
    
    stdout, stderr = await _run_ytdlp_command(cmd)
    
    files = [f for f in os.listdir(tmpdir) if not f.startswith('.')]
    if files:
        return {
            'success': True,
            'paths': [os.path.join(tmpdir, f) for f in files],
            'method': 'mobile_api'
        }
    
    raise RuntimeError("Mobile API download failed")


async def _strategy_basic_download(url: str, tmpdir: str, cookies_path: Optional[str]) -> Dict:
    """
    Strategy 4: Basic download without special parameters (fallback)
    """
    import sys
    
    out_path = os.path.join(tmpdir, "tiktok.%(ext)s")
    
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "-f", "best",
        "-o", out_path,
        "--socket-timeout", "90",
        "--retries", "15",
        "--fragment-retries", "10",
    ]
    
    if cookies_path and os.path.exists(cookies_path):
        cmd += ["--cookies", cookies_path]
    
    cmd.append(url)
    
    stdout, stderr = await _run_ytdlp_command(cmd)
    
    files = [f for f in os.listdir(tmpdir) if not f.startswith('.')]
    if files:
        return {
            'success': True,
            'paths': [os.path.join(tmpdir, f) for f in files],
            'method': 'basic'
        }
    
    raise RuntimeError("Basic download failed")


# Alternative: Use third-party API as last resort
async def download_tiktok_api_fallback(url: str, tmpdir: str) -> Dict:
    """
    Fallback: Use third-party TikTok download API
    WARNING: This requires internet access and may have rate limits
    """
    import aiohttp
    import re
    
    # Extract video ID from URL
    video_id_match = re.search(r'/video/(\d+)', url)
    if not video_id_match:
        return {'success': False, 'error': 'Could not extract video ID'}
    
    video_id = video_id_match.group(1)
    
    # Try TikTok download API (example - may need API key)
    api_url = f"https://api.tiklydown.eu.org/api/download?url={url}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=30) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Download video from provided URL
                    video_url = data.get('video', {}).get('noWatermark')
                    if video_url:
                        async with session.get(video_url) as video_response:
                            if video_response.status == 200:
                                file_path = os.path.join(tmpdir, f"{video_id}.mp4")
                                with open(file_path, 'wb') as f:
                                    f.write(await video_response.read())
                                
                                return {
                                    'success': True,
                                    'paths': [file_path],
                                    'method': 'api_fallback'
                                }
        
        return {'success': False, 'error': 'API fallback failed'}
        
    except Exception as e:
        return {'success': False, 'error': f'API fallback error: {str(e)}'}