"""
core/tts.py — Text-to-Speech Engine (Microsoft Edge TTS)

Uses the edge-tts library to synthesize speech from text using
Microsoft Edge's free neural TTS voices.  Audio is played through
pygame.mixer to avoid conflicts with sounddevice (used for recording).

Typical voice: "en-US-GuyNeural" — deep, calm, professional tone.
"""

import asyncio
import os
import tempfile
import time
import edge_tts
import pygame


class TTS:
    """
    Text-to-Speech engine powered by edge-tts.

    Args:
        voice:   Edge TTS voice identifier (e.g. "en-US-GuyNeural").
        rate:    Speech rate adjustment (e.g. "+10%", "-5%").
        volume:  Volume adjustment (e.g. "+0%", "+20%").
    """

    def __init__(
        self,
        voice: str = "en-US-GuyNeural",
        rate: str = "+0%",
        volume: str = "+0%",
    ):
        self.voice = voice
        self.rate = rate
        self.volume = volume
        self._is_speaking = False

        # Initialize pygame mixer once — 22050 Hz is fine for speech playback
        pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=2048)

    # ──────────────────────────────────────────
    #  Public API
    # ──────────────────────────────────────────

    def speak(self, text: str) -> None:
        """
        Synthesize and play the given text as speech.

        Blocks until playback finishes.  Empty/whitespace-only text
        is silently ignored.

        Args:
            text:  The string to speak aloud.
        """
        if not text or not text.strip():
            return

        self._is_speaking = True
        tmp_path = None

        try:
            # Create a temp file for the synthesized audio
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
            os.close(tmp_fd)  # close the file descriptor; edge-tts writes by path

            # Run the async synthesis in a sync context (Windows fix)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._synthesize(text, tmp_path))
            finally:
                loop.close()

            # Play the generated audio
            self._play(tmp_path)

        except Exception as e:
            print(f"⚠️  TTS error: {e}")

        finally:
            self._is_speaking = False
            # Clean up the temp file
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass  # non-critical — OS will clean up temp dir eventually

    def speak_stream(self, sentence_generator) -> str:
        """
        Speak sentences from a generator as they arrive — streaming TTS.

        Uses a producer/consumer pattern:
          • Producer thread: iterates the generator, synthesizes each sentence
            to a temp MP3 file, and pushes the path onto a queue.
          • Consumer (this thread): pops paths and plays them sequentially.

        Pre-buffers the next sentence during playback to eliminate gaps.

        Args:
            sentence_generator: An iterable/generator yielding sentence strings.

        Returns:
            str — The full concatenated response text (for history/logging).
        """
        import queue
        import threading

        audio_queue: queue.Queue = queue.Queue(maxsize=2)
        full_text_parts: list[str] = []
        producer_error: list[Exception] = []

        def _producer():
            """Synthesize sentences in a background thread."""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                for sentence in sentence_generator:
                    if not sentence or not sentence.strip():
                        continue
                    full_text_parts.append(sentence)
                    try:
                        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
                        os.close(tmp_fd)
                        loop.run_until_complete(self._synthesize(sentence, tmp_path))
                        audio_queue.put(tmp_path)
                    except Exception as e:
                        print(f"⚠️  TTS stream synthesis error: {e}")
                        producer_error.append(e)
            finally:
                loop.close()
                audio_queue.put(None)  # sentinel — signals end of stream

        self._is_speaking = True
        producer_thread = threading.Thread(target=_producer, daemon=True)
        producer_thread.start()

        try:
            while True:
                audio_path = audio_queue.get()
                if audio_path is None:
                    break  # sentinel — producer is done

                try:
                    self._play(audio_path)
                except Exception as e:
                    print(f"⚠️  TTS stream playback error: {e}")
                finally:
                    try:
                        os.remove(audio_path)
                    except OSError:
                        pass
        finally:
            self._is_speaking = False
            producer_thread.join(timeout=5)

        return " ".join(full_text_parts)

    def stop(self) -> None:
        """Stop any currently playing speech immediately."""
        try:
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
        except Exception:
            pass
        self._is_speaking = False

    @property
    def is_speaking(self) -> bool:
        """Return True if TTS audio is currently playing."""
        return self._is_speaking

    # ──────────────────────────────────────────
    #  Internal helpers
    # ──────────────────────────────────────────

    async def _synthesize(self, text: str, output_path: str) -> None:
        """
        Use edge-tts to synthesize speech and save it to `output_path`.

        Args:
            text:         Text to synthesize.
            output_path:  File path to write the .mp3 audio to.
        """
        communicate = edge_tts.Communicate(
            text,
            voice=self.voice,
            rate=self.rate,
            volume=self.volume,
        )
        await communicate.save(output_path)

    def _play(self, audio_path: str) -> None:
        """
        Play an audio file through pygame.mixer and block until complete.

        Args:
            audio_path:  Path to the .mp3 file to play.
        """
        try:
            pygame.mixer.music.load(audio_path)
            pygame.mixer.music.play()

            clock = pygame.time.Clock()
            # Block until playback fully finishes or stop() is called
            while pygame.mixer.music.get_busy() and self._is_speaking:
                clock.tick(10)

            # Post-playback grace period — lets speaker output fully decay
            # before the mic starts listening again (prevents echo pickup)
            time.sleep(0.5)

        except Exception as e:
            print(f"⚠️  Audio playback error: {e}")
        finally:
            # Unload so the temp file can be deleted on Windows
            pygame.mixer.music.unload()
