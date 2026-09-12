"""
tests/test_phase12_calibration.py

Unit Tests for Input Calibration & Signal Quality Classification (Phase 12):
- Calibration lifecycle (start, process, finish, reset)
- Ambient noise floor estimation
- Dynamic noise gate threshold derivation
- Signal quality state classifications (GOOD_SIGNAL, WEAK_SIGNAL, NOISE, CLIPPING, LOW_CONFIDENCE)
- Metadata-only PracticeInputProfile serialization
"""

import pytest
import numpy as np

from backend.analysis.test_signals import (
    generate_piano_tone,
    generate_chord_signal,
    generate_silence,
    generate_noise,
    midi_to_freq,
)
from backend.analysis.input_calibration import (
    InputCalibrator,
    PracticeInputProfile,
    SignalQualityState,
    compute_spectral_flatness,
)


@pytest.fixture
def calibrator():
    return InputCalibrator(sample_rate=22050, default_noise_gate=0.010)


class TestPhase12InputCalibration:

    def test_calibration_lifecycle_and_noise_gate(self, calibrator):
        """1 & 2. Full calibration lifecycle derives dynamic noise floor and noise gate."""
        calibrator.start_calibration(duration_seconds=1.0)
        assert calibrator.is_calibrating is True

        # Feed 30 ambient frames with low noise (RMS ~ 0.004)
        for _ in range(30):
            frame = np.random.normal(0, 0.004, 2048).astype(np.float32)
            calibrator.process_calibration_frame(frame)

        profile = calibrator.finish_calibration()

        assert calibrator.is_calibrating is False
        assert isinstance(profile, PracticeInputProfile)
        assert profile.noise_floor_rms > 0.001
        assert profile.noise_gate_rms > profile.noise_floor_rms
        assert profile.signal_quality == SignalQualityState.READY
        assert profile.frames_evaluated == 30

    def test_good_piano_signal_classification(self, calibrator):
        """6. Clean piano chord audio classified as GOOD_SIGNAL."""
        calibrator.start_calibration(duration_seconds=0.5)
        for _ in range(10):
            calibrator.process_calibration_frame(np.random.normal(0, 0.003, 2048).astype(np.float32))
        profile = calibrator.finish_calibration()

        # Generate clean C major chord (amplitude 0.5)
        piano_chord = generate_chord_signal([60, 64, 67], duration=0.3, sr=22050, amplitude=0.5)
        result = calibrator.classify_signal(piano_chord[:2048], profile)

        assert result["qualityState"] == "GOOD_SIGNAL"
        assert result["isPlayable"] is True
        assert result["signalLevel"] > 0.30

    def test_weak_signal_classification(self, calibrator):
        """3. Very quiet audio below noise gate classified as WEAK_SIGNAL or LOW_CONFIDENCE."""
        calibrator.start_calibration(duration_seconds=0.5)
        for _ in range(10):
            calibrator.process_calibration_frame(np.random.normal(0, 0.004, 2048).astype(np.float32))
        profile = calibrator.finish_calibration()

        # Very faint tone (amplitude 0.006, below noise gate)
        weak_tone = generate_piano_tone(midi_to_freq(60), duration=0.3, sr=22050, amplitude=0.006)
        result = calibrator.classify_signal(weak_tone[:2048], profile)

        assert result["qualityState"] in ["WEAK_SIGNAL", "LOW_CONFIDENCE"]
        assert result["isPlayable"] is False

    def test_room_noise_classification(self, calibrator):
        """4. Broadband room noise / fan audio classified as NOISE."""
        calibrator.start_calibration(duration_seconds=0.5)
        for _ in range(10):
            calibrator.process_calibration_frame(np.random.normal(0, 0.002, 2048).astype(np.float32))
        profile = calibrator.finish_calibration()

        # Loud broadband noise (amplitude 0.15, high Wiener entropy)
        noise_frame = generate_noise(duration=0.3, sr=22050, amplitude=0.15)
        result = calibrator.classify_signal(noise_frame[:2048], profile)

        assert result["qualityState"] == "NOISE"
        assert result["isPlayable"] is False

    def test_clipping_signal_classification(self, calibrator):
        """5. Overloaded microphone audio with digital clipping classified as CLIPPING."""
        calibrator.start_calibration(duration_seconds=0.5)
        profile = calibrator.finish_calibration()

        # Clipped square-like signal (amplitude 1.0)
        clipped_frame = np.ones(2048, dtype=np.float32) * 0.99
        result = calibrator.classify_signal(clipped_frame, profile)

        assert result["qualityState"] == "CLIPPING"
        assert result["isPlayable"] is False

    def test_calibration_reset(self, calibrator):
        """21. Resetting calibration purges all state cleanly."""
        calibrator.start_calibration(duration_seconds=1.0)
        calibrator.process_calibration_frame(np.random.normal(0, 0.01, 2048).astype(np.float32))
        calibrator.reset_calibration()

        assert calibrator.is_calibrating is False
        assert len(calibrator.rms_values) == 0
        assert calibrator.profile is None
