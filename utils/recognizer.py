# utils/recognizer.py
import os
import re
import asyncio
import logging
import tempfile
import subprocess
import aiohttp
import acoustid
import musicbrainzngs
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv

os.environ["PATH"] += os.pathsep + os.path.abspath("bin")
load_dotenv()

logger = logging.getLogger("recognizer")

ACOUSTID_API_KEY = os.getenv("ACOUSTID_API_KEY")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
AUDD_API_KEY = os.getenv("AUDD_API_KEY")

musicbrainzngs.set_useragent("MusicBot", "1.0", "https://musicbrainz.org")

spotify = None
if SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET:
    spotify = spotipy.Spotify(
        auth_manager=SpotifyClientCredentials(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET
        )
    )
    logger.info("🎧 Spotify client initialized.")
else:
    logger.warning("⚠️ Spotify credentials missing — Spotify search disabled.")


# ───────────────────────────────────────────────
def _clean_query(text: str) -> str:
    if not text:
        return ""
    base = os.path.splitext(text)[0]
    base = re.sub(r"(tmp|record|voice|audio|video|mix|file|music|song)", "", base, flags=re.I)
    base = re.sub(r"[\[\]\(\)\{\}_-]+", " ", base)
    base = re.sub(r"\s{2,}", " ", base).strip()
    return base


async def _convert_to_wav(src_path: str) -> str:
    out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    cmd = ["ffmpeg", "-y", "-i", src_path, "-t", "25", "-ac", "1", "-ar", "32000", "-vn", "-f", "wav", out]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await proc.communicate()
    if proc.returncode != 0:
        return src_path
    return out


# ───────────────────────────────────────────────
async def search_spotify(query: str) -> str:
    if not spotify:
        return "⚠️ Spotify not configured."
    query = _clean_query(query)
    if not query:
        return "😕 No Spotify query available."
    try:
        results = spotify.search(q=query, type="track", limit=5)
        items = results.get("tracks", {}).get("items", [])
        if not items:
            return "😕 No Spotify matches found."
        msg = "🎧 <b>Closest matches on Spotify:</b>\n\n"
        for t in items:
            name = t["name"]
            artist = t["artists"][0]["name"]
            url = t["external_urls"]["spotify"]
            msg += f"• <b>{artist}</b> — {name}\n🔗 <a href='{url}'>Listen on Spotify</a>\n\n"
        return msg
    except Exception as e:
        logger.exception("Spotify search failed.")
        return f"⚠️ Spotify search error: {e}"


# ───────────────────────────────────────────────
async def identify_with_audd(file_path: str) -> str:
    """Secondary fallback using Audd.io (Shazam-like)."""
    if not AUDD_API_KEY:
        return "⚠️ Audd.io not configured."
    url = "https://api.audd.io/"
    data = {"api_token": AUDD_API_KEY, "return": "timecode,spotify"}
    try:
        async with aiohttp.ClientSession() as session:
            with open(file_path, "rb") as f:
                form = aiohttp.FormData()
                form.add_field("file", f, filename=os.path.basename(file_path), content_type="audio/mpeg")
                form.add_field("api_token", AUDD_API_KEY)
                form.add_field("return", "spotify")
                async with session.post(url, data=form) as resp:
                    result = await resp.json()
        if "result" not in result or not result["result"]:
            logger.warning("Audd.io returned no match.")
            return "😕 No match found via Audd.io."
        r = result["result"]
        artist = r.get("artist")
        title = r.get("title")
        if r.get("spotify"):
            link = r["spotify"].get("external_urls", {}).get("spotify")
            return f"🎶 <b>{artist}</b> — {title}\n🔗 <a href='{link}'>Listen on Spotify</a>"
        return f"🎶 <b>{artist}</b> — {title}"
    except Exception as e:
        logger.exception("Audd.io request failed.")
        return f"⚠️ Audd.io error: {e}"


# ───────────────────────────────────────────────
async def identify_audio(file_path: str, hint: str | None = None) -> str:
    """Full chain: AcoustID → Audd.io → Spotify."""
    try:
        logger.info(f"🎵 Starting fingerprint scan: {file_path}")
        prepared = await _convert_to_wav(file_path)

        loop = asyncio.get_event_loop()
        try:
            results = await loop.run_in_executor(
                None, lambda: list(acoustid.match(ACOUSTID_API_KEY, prepared, force_fpcalc=True))
            )
        except Exception as e:
            logger.error(f"AcoustID failed: {e}")
            results = []

        if not results:
            logger.warning("❌ No AcoustID results. Trying Audd.io...")
            audd_result = await identify_with_audd(file_path)
            if "No match" not in audd_result and "error" not in audd_result:
                return audd_result
            logger.info("Falling back to Spotify.")
            return await search_spotify(hint or os.path.basename(file_path))

        score, rid, title, artist = results[0]
        logger.info(f"✅ AcoustID match — {artist} — {title} (score {score:.2f})")

        if score < 0.3:
            logger.warning("Low confidence; trying Audd.io.")
            audd_result = await identify_with_audd(file_path)
            if "No match" not in audd_result and "error" not in audd_result:
                return audd_result
            return await search_spotify(f"{artist} {title}")

        mb = musicbrainzngs.get_recording_by_id(rid, includes=["artists", "releases"])
        rec = mb.get("recording", {})
        artist_name = rec.get("artist-credit", [{}])[0].get("artist", {}).get("name", artist)
        track_title = rec.get("title", title)
        link = f"https://musicbrainz.org/recording/{rid}"
        return f"🎶 <b>{artist_name}</b> — {track_title}\n🔗 <a href='{link}'>View on MusicBrainz</a>"
    except Exception as e:
        logger.exception("Critical identification crash.")
        fb = await search_spotify(hint or os.path.basename(file_path))
        return f"⚠️ Identification failed, but here are Spotify suggestions:\n\n{fb}"
