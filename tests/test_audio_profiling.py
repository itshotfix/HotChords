"""
tests/test_audio_profiling.py

Tests for Phase 1 Audio Profiling & Quality Control:
- Silent audio handling (EMPTY_AUDIO)
- Extremely short audio handling (UNSUPPORTED_AUDIO)
- Normal harmonic chords (SUCCESS)
- Clipped / distorted audio (clipping detection)
- Pure noise / non-harmonic audio (NO_HARMONIC_CONTENT)
"""

import numpy as np
import pytest
from backend.analysis.profiling import profile_audio, compute_chroma_entropy, compute_beat_confidence
from backend.models.analysis_types import AudioStatus, AudioProfile


def generate_sine_wave(freq: float, duration: float = 3.0, sr: int = 22050, amplitude: float = 0.5) -> np.ndarray:
    """Generates a deterministic single-frequency sine wave."""
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    return amplitude * np.sin(2 * np.pi * freq * t)


def generate_c_major_chord(duration: float = 3.0, sr: int = 22050, amplitude: float = 0.5) -> np.ndarray:
    """Generates a deterministic C Major triad (C4: 261.63Hz, E4: 329.63Hz, G4: 392.00Hz)."""
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    c4 = np.sin(2 * np.pi * 261.63 * t)
    e4 = np.sin(2 * np.pi * 329.63 * t)
    g4 = np.sin(2 * np.pi * 392.00 * t)
    chord = (c4 + e4 + g4) / 3.0
    return amplitude * chord


class TestAudioProfiling:

    def test_silent_audio(self):
        """Test completely silent audio (zero amplitude)."""
        sr = 22050
        y = np.zeros(sr * 3, dtype=np.float32)
        profile, status, msg = profile_audio(y, sr=sr)

        assert status == AudioStatus.EMPTY_AUDIO
        assert profile.duration == 3.0
        assert profile.rms == 0.0
        assert profile.silence_ratio == 1.0
        assert profile.harmonic_energy == 0.0

    def test_extremely_short_audio(self):
        """Test audio shorter than 0.1s."""
        sr = 22050
        y = np.sin(np.linspace(0, 10, int(sr * 0.05)))
        profile, status, msg = profile_audio(y, sr=sr)

        assert status == AudioStatus.UNSUPPORTED_AUDIO
        assert profile.duration < 0.1

    def test_normal_harmonic_audio(self):
        """Test clean harmonic audio (C major chord triad)."""
        sr = 22050
        y = generate_c_major_chord(duration=3.0, sr=sr, amplitude=0.6)
        profile, status, msg = profile_audio(y, sr=sr)

        assert status == AudioStatus.SUCCESS
        assert profile.duration == 3.0
        assert profile.rms > 0.1
        assert profile.silence_ratio < 0.1
        assert profile.harmonic_energy > 0.4
        assert profile.chroma_strength > 0.0
        assert profile.chroma_entropy < 0.90
        assert profile.spectral_flatness < 0.40

    def test_clipped_distorted_audio(self):
        """Test audio with intentional digital clipping / saturation."""
        sr = 22050
        t = np.linspace(0, 2.0, int(sr * 2.0), endpoint=False)
        y = 2.5 * np.sin(2 * np.pi * 440 * t)  # severe overdrive
        y = np.clip(y, -1.0, 1.0)

        profile, status, msg = profile_audio(y, sr=sr)

        assert profile.clipping_ratio > 0.10
        assert profile.rms > 0.5

    def test_pure_noise_no_harmonic_content(self):
        """Test uniform white noise without harmonic structure."""
        sr = 22050
        np.random.seed(42)
        y = np.random.uniform(-0.4, 0.4, sr * 3).astype(np.float32)

        profile, status, msg = profile_audio(y, sr=sr)

        # White noise should be classified as NO_HARMONIC_CONTENT or LOW_CONFIDENCE
        assert status in [AudioStatus.NO_HARMONIC_CONTENT, AudioStatus.LOW_CONFIDENCE]
        assert profile.spectral_flatness > 0.35
        assert profile.chroma_entropy > 0.85

    def test_chroma_entropy_bounds(self):
        """Test chroma entropy calculation bounds."""
        # Single pitch class -> near 0.0 entropy
        single_pitch = np.zeros((12, 10))
        single_pitch[0, :] = 1.0
        assert compute_chroma_entropy(single_pitch) == pytest.approx(0.0, abs=1e-3)

        # Uniform 12 bins -> 1.0 entropy
        uniform_pitch = np.ones((12, 10))
        assert compute_chroma_entropy(uniform_pitch) == pytest.approx(1.0, abs=1e-3)
