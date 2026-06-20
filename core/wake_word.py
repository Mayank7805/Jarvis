"""
core/wake_word.py — Wake Word Detection using openwakeword

Listens continuously for the "hey jarvis" wake word and/or a double-clap
pattern.  When either trigger fires, the function returns True so the
main loop can begin recording user speech.
"""

import numpy as np
import sounddevice as sd

import openwakeword
from openwakeword.model import Model as OWWModel

from core.audio_capture import ClapDetector


class WakeWordDetector:
    """
    Continuous wake-word listener with optional double-clap detection.

    Uses openwakeword's pre-trained "hey_jarvis" model running on CPU.
    Audio is streamed in 80 ms chunks (1280 frames at 16 kHz) — the
    frame size expected by openwakeword.

    Args:
        model_name:       Name of the openwakeword model to load.
        threshold:        Confidence score threshold for detection.
        chunk_size:       Frames per prediction chunk (default 1280 = 80 ms).
        sample_rate:      Audio sample rate (must be 16000 for openwakeword).
        clap_threshold:   Amplitude threshold for clap spike detection.
        clap_max_interval: Max seconds between two claps.
    """

    def __init__(
        self,
        model_name: str = "hey_jarvis",
        threshold: float = 0.5,
        chunk_size: int = 1280,
        sample_rate: int = 16000,
        clap_threshold: float = 0.3,
        clap_max_interval: float = 0.8,
    ):
        self.model_name = model_name
        self.threshold = threshold
        self.chunk_size = chunk_size
        self.sample_rate = sample_rate

        # Download pre-trained models if not already cached
        print("🔄  Downloading openwakeword models (if needed)...")
        openwakeword.utils.download_models()

        # Initialize the wake word model
        print(f"🔄  Loading wake word model '{model_name}'...")
        self.model = OWWModel(
            wakeword_models=[model_name],
            vad_threshold=0.5,
        )
        print(f"✅  Wake word model '{model_name}' loaded.")

        # Initialize the clap detector
        self.clap_detector = ClapDetector(
            spike_threshold=clap_threshold,
            max_interval=clap_max_interval,
        )

    def listen_for_wake_word(self, clap_enabled: bool = True) -> bool:
        """
        Block and listen continuously until the wake word or double-clap
        is detected.

        Args:
            clap_enabled: If True, also trigger on double-clap patterns.

        Returns:
            True when a trigger event is detected.
        """
        print(f"\n👂  Listening for '{self.model_name}'", end="")
        if clap_enabled:
            print(" or double-clap", end="")
        print("...\n")

        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                blocksize=self.chunk_size,
            ) as stream:
                while True:
                    # Read a chunk of audio
                    data, overflowed = stream.read(self.chunk_size)

                    # Convert to 1-D int16 array for openwakeword
                    audio_int16 = data[:, 0] if data.ndim > 1 else data.flatten()

                    # ── Wake Word Detection ──────────────────
                    prediction = self.model.predict(audio_int16)

                    score = prediction.get(self.model_name, 0)
                    if score > self.threshold:
                        print(f"🎯  Wake word detected! (confidence: {score:.2f})")
                        # Reset the model's internal buffer to avoid
                        # re-triggering on the same audio
                        self.model.reset()
                        return True

                    # ── Clap Detection ───────────────────────
                    if clap_enabled:
                        # Convert to float32 for clap detection
                        audio_float = audio_int16.astype(np.float32) / 32768.0
                        if self.clap_detector.feed(audio_float, self.sample_rate):
                            print("👏  Double clap detected!")
                            return True

        except KeyboardInterrupt:
            print("\n⏹️  Wake word listener stopped.")
            raise
        except Exception as e:
            print(f"❌  Wake word listener error: {e}")
            raise
