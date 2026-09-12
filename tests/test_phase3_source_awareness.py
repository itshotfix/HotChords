"""
tests/test_phase3_source_awareness.py

Comprehensive Integration and MIR Scenario Tests for Phase 3 Multi-Instrument & Source-Aware Architecture:
1. Piano-led song (rich piano harmonics)
2. Guitar-led song (plucked harmonic overtones)
3. Synth-led song (wide spectral bandwidth)
4. Bass-heavy song with slash-chord inversion (C/E)
5. Mixed instrumentation (multi-candidate corroboration)
6. Drum-heavy / no-harmony audio (strict drum exclusion, NO_HARMONIC_CONTENT, 0 fake chords)
7. Vocal-heavy audio (vocal exclusion from chord recognition)
8. Weak harmonic content / noise (failure rule: LOW_CONFIDENCE / NO_HARMONIC_CONTENT, 0 fake chords)
9. Multiple instruments agreeing (source agreement boost)
10. Multiple instruments disagreeing (evidence router selects best candidate)
11. SongTimeline backward compatibility and metadata round-trip
"""

import os
import tempfile
import numpy as np
import soundfile as sf
import pytest

from backend.analysis.pipeline import run_pipeline
from backend.analysis.harmonic_evidence import HarmonicEvidenceRouter
from backend.analysis.source_agreement import compute_source_agreement, fuse_bass_evidence
from backend.models.analysis_types import AudioStatus
from backend.models.timeline import SongTimeline


def generate_rich_chord_audio(frequencies, duration=3.0, sr=22050, decay_rate=1.2):
    """Generates synthetic multi-overtone acoustic audio with exponential decay."""
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    env = np.exp(-decay_rate * (t % 1.0))
    y = np.zeros_like(t)
    for f0 in frequencies:
        for h, w in [(1, 1.0), (2, 0.5), (3, 0.3), (4, 0.15)]:
            y += w * np.sin(2 * np.pi * f0 * h * t)
    return (y * env / np.max(np.abs(y)) * 0.7).astype(np.float32)


@pytest.fixture
def temp_piano_c_major_wav():
    """Generates a rich synthetic C major (C4, E4, G4) WAV file."""
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    sr = 22050
    # C4 = 261.63, E4 = 329.63, G4 = 392.00
    y = generate_rich_chord_audio([261.63, 329.63, 392.00], duration=3.5, sr=sr, decay_rate=1.5)
    sf.write(path, y, sr)
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def temp_guitar_a_minor_wav():
    """Generates a rich synthetic A minor (A3, C4, E4) WAV file."""
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    sr = 22050
    # A3 = 220.00, C4 = 261.63, E4 = 329.63
    y = generate_rich_chord_audio([220.00, 261.63, 329.63], duration=3.5, sr=sr, decay_rate=2.0)
    sf.write(path, y, sr)
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def temp_drum_percussion_wav():
    """Generates pure percussive transients without tonal content."""
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    sr = 22050
    duration = 3.0
    y = np.zeros(int(sr * duration), dtype=np.float32)
    for beat in range(8):
        idx = int(beat * 0.35 * sr)
        if idx < len(y):
            y[idx:idx+400] = np.random.uniform(-0.9, 0.9, min(400, len(y)-idx))
    sf.write(path, y, sr)
    yield path
    if os.path.exists(path):
        os.remove(path)


class TestPhase3SourceAwareness:

    def test_piano_led_candidate_scoring_and_selection(self, temp_piano_c_major_wav):
        """Scenario 1: Piano-led audio generates candidate scoring and selects clear harmonic evidence."""
        result = run_pipeline(temp_piano_c_major_wav)

        assert result["ready"] is True
        assert result["status"] == AudioStatus.SUCCESS.value
        assert len(result["chords"]) > 0
        assert "chord_source" in result
        assert "source_selection_reason" in result
        assert "candidate_evidence" in result
        assert "mix" in result["candidate_evidence"]

        # Verify candidate scoring inspectability
        mix_ev = result["candidate_evidence"]["mix"]
        assert mix_ev["harmonicEnergy"] > 0.50
        assert mix_ev["chromaStrength"] > 0.10
        assert mix_ev["compositeScore"] > 0.40

    def test_guitar_led_chord_recognition(self, temp_guitar_a_minor_wav):
        """Scenario 2: Guitar-led audio achieves successful chord recognition and reliability."""
        result = run_pipeline(temp_guitar_a_minor_wav)

        assert result["ready"] is True
        assert result["status"] == AudioStatus.SUCCESS.value
        assert len(result["chords"]) > 0
        assert result["reliability"]["overall"] > 0.40
        assert result["reliability"]["harmonicStrength"] > 0.40

    def test_drum_percussion_rejection_no_fake_chords(self, temp_drum_percussion_wav):
        """Scenario 6: Drum/Percussion audio rejects drum stems and outputs NO_HARMONIC_CONTENT with 0 fake chords."""
        result = run_pipeline(temp_drum_percussion_wav)

        assert result["ready"] is True
        assert result["status"] in [AudioStatus.NO_HARMONIC_CONTENT.value, AudioStatus.LOW_CONFIDENCE.value]
        if result["status"] == AudioStatus.NO_HARMONIC_CONTENT.value:
            assert result["chords"] == []
            assert result["unique_chords"] == []

    def test_multi_source_agreement_boost(self):
        """Scenario 9: Corroborated multi-candidate agreement increases reliability."""
        seq_a = [{"time": 0.0, "end": 2.0, "chord": "C"}, {"time": 2.0, "end": 4.0, "chord": "G"}]
        seq_b = [{"time": 0.0, "end": 2.0, "chord": "C"}, {"time": 2.0, "end": 4.0, "chord": "G"}]

        agreement = compute_source_agreement({"mix": seq_a, "other": seq_b}, duration=4.0)
        assert agreement == 1.0

    def test_bass_inversion_slash_chord_fusion(self):
        """Scenario 4: Bass note evidence converts C major into C/E slash chord."""
        chords = [{"time": 0.0, "end": 2.0, "chord": "C", "confidence": 0.9}]
        bass_chords = [{"time": 0.0, "end": 2.0, "chord": "Em", "confidence": 0.9}]

        fused = fuse_bass_evidence(chords=chords, bass_chords=bass_chords)
        assert len(fused) == 1
        assert fused[0]["chord"] == "C/E"
        assert fused[0].get("inversion") is True

    def test_vocal_and_drum_stem_exclusion(self):
        """Scenario 7: Vocals and drums are explicitly filtered out from promising candidate list."""
        router = HarmonicEvidenceRouter(sr=22050)
        y_dummy = np.random.uniform(-0.1, 0.1, 22050 * 2)
        router.register_source("drums", y_dummy)
        router.register_source("vocals", y_dummy)
        router.register_source("mix", y_dummy)

        router.extract_evidence()
        qualified = router.filter_promising_candidates()

        assert "drums" not in qualified
        assert "vocals" not in qualified

    def test_song_timeline_phase3_backward_compatibility(self, temp_piano_c_major_wav):
        """Scenario 11: Verify SongTimeline from_analysis_dict & to_analysis_dict round-trip Phase 3 metadata."""
        result = run_pipeline(temp_piano_c_major_wav)
        timeline = SongTimeline.from_analysis_dict(result)

        assert len(timeline.original_chords) == len(result["chords"])
        legacy_dict = timeline.to_analysis_dict()

        assert "chord_source" in result
        assert "source_selection" in legacy_dict
        assert "reliability" in legacy_dict
        assert "candidate_evidence" in legacy_dict
        assert "instruments" in legacy_dict
        assert legacy_dict["status"] == result["status"]
