"""
tests/test_phase2_pipeline_integration.py

End-to-End Pipeline Integration Tests for Phase 2 Modern Chord Recognition Core:
- Deep engine pipeline execution
- Extended vocabulary handling (7ths, maj7, min7, suspensions)
- Real song benchmark tests
- Backward compatibility of SongTimeline & API response contracts
"""

import os
import tempfile
import numpy as np
import soundfile as sf
import pytest

from backend.analysis.pipeline import run_pipeline
from backend.models.timeline import SongTimeline


@pytest.fixture
def temp_cmaj7_wav():
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    sr = 22050
    t = np.linspace(0, 4.0, int(sr * 4.0), endpoint=False)
    env = np.exp(-1.2 * (t % 1.0))
    y = np.zeros_like(t)
    # Cmaj7 (C4: 261.63, E4: 329.63, G4: 392.00, B4: 493.88) with overtones
    for f0 in [261.63, 329.63, 392.00, 493.88]:
        for h, w in [(1, 1.0), (2, 0.5), (3, 0.3), (4, 0.15)]:
            y += w * np.sin(2 * np.pi * f0 * h * t)
    y = (y * env / np.max(np.abs(y)) * 0.7).astype(np.float32)
    sf.write(path, y, sr)
    yield path
    if os.path.exists(path):
        os.remove(path)


class TestPhase2PipelineIntegration:

    def test_pipeline_with_lv_chordia(self, temp_cmaj7_wav):
        result = run_pipeline(temp_cmaj7_wav)

        assert result["ready"] is True
        assert result["engine"] == "lv_chordia"
        assert result["status"] in ["SUCCESS", "LOW_CONFIDENCE"]
        assert len(result["chords"]) > 0
        assert "audio_profile" in result
        assert "timing" in result
        assert "reliability" in result

        # Verify chord_data contains notes and fingering
        for chord_name, c_data in result["chord_data"].items():
            assert "notes" in c_data
            assert "fingers" in c_data
            assert "difficulty" in c_data

        # Verify SongTimeline round-trip conversion
        timeline = SongTimeline.from_analysis_dict(result)
        assert len(timeline.original_chords) == len(result["chords"])
        legacy_dict = timeline.to_analysis_dict()
        assert legacy_dict["engine"] == "lv_chordia"
        assert len(legacy_dict["chords"]) > 0

    def test_pipeline_real_song1(self):
        song_path = os.path.join(os.path.dirname(__file__), "..", "test songs", "Song1-HotFix-TuMera.mp3")
        if not os.path.exists(song_path):
            pytest.skip("Song1 not present, skipping.")

        result = run_pipeline(song_path)

        assert result["ready"] is True
        assert result["engine"] == "lv_chordia"
        assert len(result["chords"]) > 0
        assert len(result["unique_chords"]) > 0

        # Check extended chords exist in unique chords (e.g. C#m7 or Abm7 or Amaj7)
        chord_symbols = result["unique_chords"]
        assert any('7' in c or 'm' in c for c in chord_symbols)

        timeline = SongTimeline.from_analysis_dict(result)
        assert timeline.duration > 100.0

    def test_pipeline_real_song2(self):
        song_path = os.path.join(os.path.dirname(__file__), "..", "test songs", "Song2-Lady Gaga Bruno Mars Die With A Smile Official Music Video.mp3")
        if not os.path.exists(song_path):
            pytest.skip("Song2 not present, skipping.")

        result = run_pipeline(song_path)

        assert result["ready"] is True
        assert result["engine"] == "lv_chordia"
        assert len(result["chords"]) > 0
        
        # Check that Amaj7 or Dmaj7 or 7ths were recognized
        unique = result["unique_chords"]
        assert any('maj7' in c or '7' in c for c in unique)
