"""
skills/music.py — Music Playback Skill

Plays audio from YouTube via yt-dlp (search + download) and pygame
(playback).  Downloads audio to a temporary file for reliable Windows
playback, then streams it through ``pygame.mixer.music``.

Dependencies:
    pip install yt-dlp pygame

Commands:
    "play Shape of You"       → search YouTube, download audio, play
    "stop music"              → stop playback
    "pause music"             → pause
    "resume music"            → resume
    "next song"               → stop current, prompt for next
"""

import os
import re
import tempfile
import threading
from pathlib import Path

from skills.base_skill import BaseSkill


# ──────────────────────────────────────────────
#  Module-level state (singleton playback)
# ──────────────────────────────────────────────

_mixer_initialised: bool = False
_current_temp_file: str | None = None
_current_track_info: dict | None = None       # {"title": ..., "artist": ...}
_download_lock = threading.Lock()
_is_downloading: bool = False


def _ensure_mixer() -> None:
    """Lazy-initialise pygame.mixer exactly once."""
    global _mixer_initialised
    if _mixer_initialised:
        return
    try:
        import pygame
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)
        _mixer_initialised = True
        print("   [+] pygame.mixer initialised (44100 Hz, stereo)")
    except Exception as e:
        print(f"   [!] pygame.mixer init failed: {e}")
        raise


def _cleanup_temp_file() -> None:
    """Remove the previous temp audio file, if any."""
    global _current_temp_file
    if _current_temp_file and os.path.exists(_current_temp_file):
        try:
            os.remove(_current_temp_file)
        except OSError:
            pass  # file may be locked; will be cleaned up on next play
    _current_temp_file = None


# ──────────────────────────────────────────────
#  MusicSkill
# ──────────────────────────────────────────────

class MusicSkill(BaseSkill):
    """Plays music from YouTube via yt-dlp + pygame."""

    @property
    def name(self) -> str:
        return "Music"

    @property
    def keywords(self) -> list[str]:
        return [
            "play", "music", "song",
            "pause music", "stop music", "resume music",
            "next song",
        ]

    # ── Smarter matching ──────────────────────

    def can_handle(self, query: str) -> bool:
        """
        Override default matching to reduce false positives.

        "play" alone is far too generic (could be "play a game"), so we
        require either a compound keyword ("pause music", "stop music",
        etc.) **or** "play" followed by content that looks like a music
        request.
        """
        q = query.lower()

        # Compound keywords — always match
        compound = [
            "pause music", "stop music", "resume music",
            "next song", "play song", "play music",
        ]
        if any(kw in q for kw in compound):
            return True

        # "play <something>" — match if there's actual content after "play"
        match = re.search(r"\bplay\s+(.+)", q)
        if match:
            after_play = match.group(1).strip()
            # Exclude commands that are clearly not music
            non_music = {"a game", "the video", "video", "game"}
            if after_play and after_play not in non_music:
                return True

        # Standalone "song" or "music" with intent words
        if any(kw in q for kw in ("put on some music", "i want to hear", "sing")):
            return True

        return False

    # ── Execution router ──────────────────────

    def execute(self, query: str) -> str:
        """Route to play / stop / pause / resume based on keywords."""
        q = query.lower()

        if "stop music" in q or "stop the music" in q:
            return self._stop()

        if "pause music" in q or "pause the music" in q:
            return self._pause()

        if "resume music" in q or "resume the music" in q or "unpause" in q:
            return self._resume()

        if "next song" in q:
            self._stop()
            return "Stopped the current song. Tell me what to play next."

        # Default: treat as a play request
        return self._play(query)

    # ── Playback controls ─────────────────────

    def _play(self, query: str) -> str:
        """Search YouTube and play the first result's audio."""
        global _is_downloading, _current_temp_file, _current_track_info

        search_query = self._extract_song_query(query)
        if not search_query:
            return "What would you like me to play? Try saying play followed by a song name."

        # Prevent overlapping downloads
        if _is_downloading:
            return "I'm already downloading a track. Please wait a moment."

        # Stop any current playback and clean up
        self._stop()

        try:
            _ensure_mixer()
        except Exception:
            return "Sorry, I couldn't initialise the audio system."

        # Download and play in the current thread (blocking but reliable)
        # The main loop's TTS will wait until we return.
        try:
            _is_downloading = True

            import yt_dlp

            # Create temp file for audio
            fd, temp_path = tempfile.mkstemp(suffix=".m4a", prefix="jarvis_music_")
            os.close(fd)

            ydl_opts = {
                "format": "bestaudio[ext=m4a]/bestaudio/best",
                "outtmpl": temp_path,
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                "extract_flat": False,
                # Overwrite the temp file we just created
                "overwrites": True,
            }

            print(f"   [♪] Searching YouTube for: {search_query}")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch1:{search_query}", download=True)

                if not info or "entries" not in info or not info["entries"]:
                    _cleanup_temp_file()
                    return "Sorry, I couldn't find that song on YouTube."

                entry = info["entries"][0]
                title = entry.get("title", "Unknown")
                artist = entry.get("uploader", entry.get("channel", "Unknown"))

                # yt-dlp may use a slightly different filename
                # Find the actual downloaded file
                actual_file = entry.get("requested_downloads", [{}])[0].get(
                    "filepath", temp_path
                )
                if not os.path.exists(actual_file):
                    actual_file = temp_path

            _current_temp_file = actual_file
            _current_track_info = {"title": title, "artist": artist}

            # Play via pygame
            import pygame
            pygame.mixer.music.load(actual_file)
            pygame.mixer.music.play()

            print(f"   [♪] Now playing: {title} — {artist}")
            return f"Playing {title} by {artist}."

        except Exception as e:
            print(f"   [!] Music playback error: {e}")
            _cleanup_temp_file()
            return f"Sorry, I couldn't play that. Error: {e}"

        finally:
            _is_downloading = False

    @staticmethod
    def _stop() -> str:
        """Stop playback and clean up resources."""
        try:
            import pygame
            if _mixer_initialised and pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
        except Exception:
            pass
        _cleanup_temp_file()
        return "Music stopped."

    @staticmethod
    def _pause() -> str:
        """Pause the currently playing track."""
        try:
            import pygame
            if _mixer_initialised and pygame.mixer.music.get_busy():
                pygame.mixer.music.pause()
                return "Music paused."
            return "Nothing is playing right now."
        except Exception as e:
            return f"Couldn't pause: {e}"

    @staticmethod
    def _resume() -> str:
        """Resume a paused track."""
        try:
            import pygame
            if _mixer_initialised:
                pygame.mixer.music.unpause()
                return "Music resumed."
            return "Nothing is paused right now."
        except Exception as e:
            return f"Couldn't resume: {e}"

    # ── Helpers ────────────────────────────────

    @staticmethod
    def _extract_song_query(query: str) -> str:
        """
        Extract the song/artist name from the user's query.

        Examples:
            "play Shape of You"               → "Shape of You"
            "play song Bohemian Rhapsody"      → "Bohemian Rhapsody"
            "play some music by Coldplay"      → "music by Coldplay"
            "I want to hear Blinding Lights"   → "Blinding Lights"
        """
        q = query.strip()

        # Try "play [song] <content>"
        match = re.search(
            r"\bplay\s+(?:song\s+|music\s+|some\s+)?(.+)",
            q,
            re.IGNORECASE,
        )
        if match:
            return match.group(1).strip()

        # Try "i want to hear <content>"
        match = re.search(r"(?:want to hear|listen to)\s+(.+)", q, re.IGNORECASE)
        if match:
            return match.group(1).strip()

        # Fallback — return the whole query minus common prefixes
        for prefix in ("play", "song", "music"):
            if q.lower().startswith(prefix):
                q = q[len(prefix):].strip()
        return q
