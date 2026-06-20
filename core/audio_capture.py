"""
core/audio_capture.py — Microphone Audio Capture & Clap Detection

Provides two main capabilities:
  1. record_speech()        — Streams mic audio and auto-stops on silence.
  2. ClapDetector class     — Detects double-clap patterns in audio chunks.

All audio is captured at 16 kHz, mono, float32 — the format expected by
both faster-whisper and openwakeword.
"""

import time
import numpy as np
import sounddevice as sd


# ──────────────────────────────────────────────
#  Speech Recording with Silence Detection
# ──────────────────────────────────────────────

def _rms(audio_chunk: np.ndarray) -> float:
    """Compute the Root Mean Square of an audio chunk."""
    return float(np.sqrt(np.mean(audio_chunk ** 2)))


# ──────────────────────────────────────────────
#  Auto-Calibrating Silence Threshold
# ──────────────────────────────────────────────

# Hard limits to keep the threshold sensible regardless of mic noise
_MIN_THRESHOLD = 0.005
_MAX_THRESHOLD = 0.05


def calibrate_silence_threshold(
    duration: float = 1.0,
    sample_rate: int = 16000,
) -> float:
    """
    Record ambient noise for `duration` seconds and derive a silence threshold.

    The threshold is set to 4× the ambient RMS, clamped to
    [0.005, 0.05] so that an unusually quiet or noisy environment
    doesn't produce an extreme value.

    Returns:
        float — calibrated silence threshold.
    """
    print("🔇  Calibrating mic... (stay quiet)")
    block_size = 1024
    frames: list[np.ndarray] = []

    try:
        with sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
            blocksize=block_size,
        ) as stream:
            samples_needed = int(sample_rate * duration)
            samples_read = 0
            while samples_read < samples_needed:
                data, _ = stream.read(block_size)
                chunk = data[:, 0] if data.ndim > 1 else data.flatten()
                frames.append(chunk.copy())
                samples_read += len(chunk)
    except Exception as e:
        print(f"⚠️  Calibration failed ({e}) — using default threshold {_MIN_THRESHOLD}")
        return _MIN_THRESHOLD

    ambient = np.concatenate(frames, axis=0)
    ambient_rms = _rms(ambient)
    threshold = float(np.clip(ambient_rms * 4, _MIN_THRESHOLD, _MAX_THRESHOLD))
    return threshold


def record_speech(
    sample_rate: int = 16000,
    channels: int = 1,
    block_size: int = 1024,
    silence_threshold: float = 0.01,
    silence_duration: float = 1.5,
    max_record_seconds: float = 30.0,
    lead_in_discard: float = 0.3,
) -> np.ndarray | None:
    """
    Record speech from the microphone and return a numpy array.

    Recording starts immediately and stops after `silence_duration` seconds
    of continuous silence (RMS below `silence_threshold`).  A safety cap of
    `max_record_seconds` prevents infinite recordings.

    The first `lead_in_discard` seconds of audio are silently thrown away
    to skip any residual speaker echo picked up by the mic.

    Returns:
        np.ndarray  — Recorded audio (float32, mono, 16 kHz).
        None        — If no speech was detected at all.
    """
    frames: list[np.ndarray] = []
    silent_time: float = 0.0
    has_speech: bool = False
    start_time = time.time()

    # Number of samples to discard at the start (echo grace period)
    discard_samples = int(sample_rate * lead_in_discard)
    discarded_so_far = 0

    print("🎙️  Listening... (speak now)")

    try:
        with sd.InputStream(
            samplerate=sample_rate,
            channels=channels,
            dtype="float32",
            blocksize=block_size,
        ) as stream:
            while True:
                # Read a chunk of audio
                data, overflowed = stream.read(block_size)
                if overflowed:
                    print("⚠️  Audio buffer overflowed — some audio may be lost.")

                chunk = data[:, 0] if data.ndim > 1 else data.flatten()

                # ── Discard early frames to skip speaker echo residue ──
                if discarded_so_far < discard_samples:
                    discarded_so_far += len(chunk)
                    continue

                rms = _rms(chunk)

                # Track whether we've heard any speech
                if rms >= silence_threshold:
                    has_speech = True
                    silent_time = 0.0
                else:
                    silent_time += block_size / sample_rate

                # Only start collecting frames once speech is detected
                if has_speech:
                    frames.append(chunk.copy())

                # Stop conditions
                if has_speech and silent_time >= silence_duration:
                    print("🔇  Silence detected — stopping recording.")
                    break

                if (time.time() - start_time) >= max_record_seconds:
                    print("⏱️  Max recording time reached — stopping.")
                    break

    except Exception as e:
        print(f"❌  Audio capture error: {e}")
        return None

    if not frames:
        print("🤷  No speech detected.")
        return None

    # Concatenate all captured frames into a single array
    audio = np.concatenate(frames, axis=0)
    duration = len(audio) / sample_rate
    print(f"✅  Captured {duration:.1f}s of audio ({len(audio)} samples)")
    return audio


# ──────────────────────────────────────────────
#  Double-Clap Detector
# ──────────────────────────────────────────────

class ClapDetector:
    """
    Detects a double-clap pattern in a streaming audio signal.

    A "clap" is defined as a short amplitude spike above `spike_threshold`.
    Two claps occurring within `max_interval` seconds trigger a detection.

    Usage:
        detector = ClapDetector(spike_threshold=0.3, max_interval=0.8)
        # In your audio loop:
        if detector.feed(audio_chunk, sample_rate):
            print("Double clap!")
    """

    def __init__(
        self,
        spike_threshold: float = 0.3,
        max_interval: float = 0.8,
        cooldown: float = 1.0,
    ):
        self.spike_threshold = spike_threshold
        self.max_interval = max_interval
        self.cooldown = cooldown

        self._last_spike_time: float | None = None
        self._last_detection_time: float = 0.0
        self._in_spike: bool = False  # prevents counting a single clap as multiple

    def feed(self, audio_chunk: np.ndarray, sample_rate: int) -> bool:
        """
        Feed an audio chunk and return True if a double-clap is detected.

        Args:
            audio_chunk:  1-D float32 numpy array of audio samples.
            sample_rate:  Sample rate (e.g. 16000).

        Returns:
            True if a double-clap pattern was detected in this chunk.
        """
        now = time.time()

        # Cooldown — ignore detections that are too close together
        if (now - self._last_detection_time) < self.cooldown:
            return False

        peak = float(np.max(np.abs(audio_chunk)))

        if peak >= self.spike_threshold:
            if not self._in_spike:
                # Rising edge — new spike detected
                self._in_spike = True

                if self._last_spike_time is not None:
                    interval = now - self._last_spike_time
                    if interval <= self.max_interval:
                        # Double clap detected!
                        self._last_spike_time = None
                        self._last_detection_time = now
                        self._in_spike = False
                        return True

                self._last_spike_time = now
        else:
            # Signal dropped below threshold — reset spike flag
            self._in_spike = False

            # If too much time has passed since the first spike, reset
            if (
                self._last_spike_time is not None
                and (now - self._last_spike_time) > self.max_interval
            ):
                self._last_spike_time = None

        return False
