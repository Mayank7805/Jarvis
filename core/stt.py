"""
core/stt.py — Speech-to-Text using faster-whisper

Wraps the faster-whisper WhisperModel for CPU-optimized inference with
int8 quantization.  Designed for the Intel i7-1360P (no dedicated GPU).
"""

import numpy as np
from faster_whisper import WhisperModel


class STT:
    """
    Speech-to-Text engine backed by faster-whisper.

    The model is loaded once on initialization and reused for all
    subsequent transcriptions to avoid repeated loading overhead.

    Args:
        model_size:          Whisper model name (e.g. "base.en").
        device:              Compute device — "cpu" for CPU-only systems.
        compute_type:        Quantization type — "int8" for fast CPU inference.
        beam_size:           Beam search width (higher = more accurate, slower).
        no_speech_threshold: Segments with no_speech_prob above this are
                             considered noise and discarded.
    """

    def __init__(
        self,
        model_size: str = "base.en",
        device: str = "cpu",
        compute_type: str = "int8",
        beam_size: int = 5,
        no_speech_threshold: float = 0.6,
    ):
        self.beam_size = beam_size
        self.no_speech_threshold = no_speech_threshold

        print(f"🔄  Loading Whisper model '{model_size}' ({compute_type} on {device})...")
        self.model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
        )
        print("✅  Whisper model loaded.")

    def transcribe(self, audio_np: np.ndarray) -> str | None:
        """
        Transcribe a numpy audio array to text.

        Args:
            audio_np: 1-D float32 numpy array of audio samples at 16 kHz.

        Returns:
            str   — The transcribed text (stripped and cleaned).
            None  — If transcription is empty, too short, or mostly noise.
        """
        if audio_np is None or len(audio_np) == 0:
            return None

        # Ensure the audio is float32
        if audio_np.dtype != np.float32:
            audio_np = audio_np.astype(np.float32)

        try:
            segments, info = self.model.transcribe(
                audio_np,
                beam_size=self.beam_size,
                vad_filter=True,  # filter out non-speech segments
            )

            # Collect text from segments, filtering noisy ones
            texts: list[str] = []
            for segment in segments:
                # Skip segments that are likely noise / silence
                if segment.no_speech_prob > self.no_speech_threshold:
                    continue
                text = segment.text.strip()
                if text:
                    texts.append(text)

            if not texts:
                return None

            result = " ".join(texts).strip()

            # Filter out very short / meaningless transcriptions
            if len(result) < 2:
                return None

            return result

        except Exception as e:
            print(f"❌  Transcription error: {e}")
            return None
