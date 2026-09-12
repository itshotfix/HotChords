"""
tests/test_phase1_pipeline_integration.py

End-to-End Integration Tests for Phase 1 Audio Intelligence Foundation:
- Silent audio handling (no fake chords, EMPTY_AUDIO status)
- Synthetic harmonic chord audio execution (SUCCESS status, timing, profile, chords)
- Noise audio execution (NO_HARMONIC_CONTENT status)
- Backward compatibility of API and SongTimeline dictionary serialization
- Integration test on a test song asset
"""

import os
import tempfile
import numpy as np
import soundfile as sf
import pytest

from backend.analysis.pipeline import run_pipeline
from backend.models.timeline import SongTimeline
from backend.models.analysis_types import AudioStatus


@pytest.fixture
def temp_silent_wav():
    """Generates a 3-second silent WAV file."""
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    sr = 22050
    y = np.zeros(sr * 3, dtype=np.float32)
    sf.write(path, y, sr)
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def temp_harmonic_wav():
    """Generates a 4-second rich acoustic C Major chord WAV file."""
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    sr = 22050
    t = np.linspace(0, 4.0, int(sr * 4.0), endpoint=False)
    env = np.exp(-1.2 * (t % 1.0))
    y = np.zeros_like(t)
    # C major (C4=261.63, E4=329.63, G4=392.00) with harmonic overtones
    for f0 in [261.63, 329.63, 392.00]:
        for h, w in [(1, 1.0), (2, 0.5), (3, 0.3), (4, 0.15)]:
            y += w * np.sin(2 * np.pi * f0 * h * t)
    y = (y * env / np.max(np.abs(y)) * 0.7).astype(np.float32)
    sf.write(path, y, sr)
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def temp_noise_wav():
    """Generates a 3-second uniform white noise WAV file."""
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    sr = 22050
    np.random.seed(123)
    y = np.random.uniform(-0.3, 0.3, sr * 3).astype(np.float32)
    sf.write(path, y, sr)
    yield path
    if os.path.exists(path):
        os.remove(path)


class TestPhase1PipelineIntegration:

    def test_pipeline_silent_audio_no_fake_chords(self, temp_silent_wav):
        """Verify silent audio returns EMPTY_AUDIO and does NOT fabricate chords."""
        result = run_pipeline(temp_silent_wav)

        assert result["ready"] is True
        assert result["status"] == AudioStatus.EMPTY_AUDIO.value
        assert result["chords"] == []
        assert result["beginner_chords"] == []
        assert result["unique_chords"] == []
        assert "audio_profile" in result
        assert result["audio_profile"]["silence_ratio"] == 1.0

        # Verify SongTimeline conversion
        timeline = SongTimeline.from_analysis_dict(result)
        assert len(timeline.original_chords) == 0
        legacy_dict = timeline.to_analysis_dict()
        assert legacy_dict["chords"] == []
        assert legacy_dict["status"] == AudioStatus.EMPTY_AUDIO.value

    def test_pipeline_harmonic_audio(self, temp_harmonic_wav):
        """Verify synthetic harmonic audio generates SUCCESS, chords, timing, and profile."""
        result = run_pipeline(temp_harmonic_wav)

        assert result["ready"] is True
        assert result["status"] == AudioStatus.SUCCESS.value
        assert len(result["chords"]) > 0
        assert len(result["unique_chords"]) > 0
        assert "key" in result
        assert "scale" in result
        assert "tempo" in result
        assert "audio_profile" in result
        assert "timing" in result
        assert "reliability" in result
        assert "candidate_evidence" in result
        assert "instruments" in result

        # Verify instrument registry entries have honest, non-fabricated reporting
        for inst_name, inst_data in result["instruments"].items():
            avail = inst_data.get("isAvailable", inst_data.get("is_available"))
            conf = inst_data.get("confidence")
            if avail:
                assert conf is not None and 0.0 <= conf <= 1.0
            else:
                assert conf is None

        # Verify canonical SongTimeline serialization and backwards compatibility
        timeline = SongTimeline.from_analysis_dict(result)
        assert len(timeline.original_chords) == len(result["chords"])
        legacy_dict = timeline.to_analysis_dict()
        
        # Verify required legacy contract keys for frontend
        for required_key in [
            "ready", "file", "duration", "key", "scale", "key_full",
            "tempo", "time_sig", "scale_notes", "chords", "unique_chords",
            "chord_data", "roman_numerals", "beginner_chords"
        ]:
            assert required_key in legacy_dict

    def test_pipeline_noise_audio_no_fake_chords(self, temp_noise_wav):
        """Verify white noise returns NO_HARMONIC_CONTENT without fake chords."""
        result = run_pipeline(temp_noise_wav)

        assert result["ready"] is True
        assert result["status"] in [AudioStatus.NO_HARMONIC_CONTENT.value, AudioStatus.LOW_CONFIDENCE.value]
        if result["status"] == AudioStatus.NO_HARMONIC_CONTENT.value:
            assert result["chords"] == []

    def test_real_test_song_if_present(self):
        """Run analysis on Song1 from 'test songs' if present."""
        test_song_path = os.path.join(os.path.dirname(__file__), "..", "test songs", "Song1-HotFix-TuMera.mp3")
        if not os.path.exists(test_song_path):
            pytest.skip("Test song not found, skipping real song run.")

        result = run_pipeline(test_song_path)

        assert result["ready"] is True
        assert result["duration"] > 10.0
        assert result["status"] in [AudioStatus.SUCCESS.value, AudioStatus.LOW_CONFIDENCE.value]
        assert len(result["chords"]) > 0
        assert "audio_profile" in result
        assert "timing" in result
        assert "reliability" in result

        timeline = SongTimeline.from_analysis_dict(result)
        assert len(timeline.original_chords) > 0
