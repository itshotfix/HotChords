"""
tests/test_phase11_note_detection.py

Unit Tests for Real-Time DSP Pitch & Polyphonic Piano Note Detector (Phase 11):
- Single notes (C4, A4)
- Triads (C major, G major, A minor, F major, C minor)
- Four-note chords (C7, Cmaj7, C/E)
- Silence, noise, detuned signals
- Harmonic overtone suppression
- Temporal hysteresis (NOTE_ON persistence, NOTE_OFF release)
- Low confidence detection
"""

import pytest
import numpy as np

from backend.analysis.test_signals import (
    generate_piano_tone,
    generate_chord_signal,
    generate_silence,
    generate_noise,
    get_preset_signal,
    midi_to_freq,
    midi_to_note_name,
)
from backend.analysis.realtime_pitch import (
    PolyphonicPitchDetector,
    RealTimeNoteTracker,
    freq_to_midi_exact,
    midi_to_freq_exact,
)


@pytest.fixture
def detector():
    return PolyphonicPitchDetector(
        sample_rate=22050,
        n_fft=4096,
        hop_size=512,
        energy_threshold=0.005,
        peak_threshold=0.08,
    )


@pytest.fixture
def tracker(detector):
    return RealTimeNoteTracker(
        detector=detector,
        persistence_threshold=2,
        release_threshold=3,
    )


class TestRealTimeNoteDetection:

    def test_single_c4_detection(self, detector):
        """1. Detect single C4 note (MIDI 60, 261.63 Hz)."""
        signal = generate_piano_tone(midi_to_freq(60), duration=0.5, sr=22050)
        result = detector.detect_frame(signal[:4096])

        assert result["status"] == "DETECTED"
        assert result["polyphony_type"] == "MONOPHONIC"
        assert len(result["notes"]) == 1
        note = result["notes"][0]
        assert note.midi == 60
        assert note.note_name == "C4"
        assert abs(note.frequency - 261.63) < 3.0
        assert note.confidence >= 0.70

    def test_single_a4_detection(self, detector):
        """2. Detect single A4 note (MIDI 69, 440.00 Hz)."""
        signal = generate_piano_tone(440.0, duration=0.5, sr=22050)
        result = detector.detect_frame(signal[:4096])

        assert result["status"] == "DETECTED"
        assert len(result["notes"]) == 1
        assert result["notes"][0].midi == 69
        assert result["notes"][0].note_name == "A4"
        assert abs(result["notes"][0].frequency - 440.0) < 3.0

    def test_c_major_triad(self, detector):
        """3. Detect C Major triad (C4, E4, G4 = MIDI 60, 64, 67)."""
        signal = get_preset_signal("C_MAJOR", duration=0.5, sr=22050)
        result = detector.detect_frame(signal[:4096])

        assert result["status"] == "DETECTED"
        assert result["polyphony_type"] == "POLYPHONIC"
        detected_midis = [n.midi for n in result["notes"]]
        assert 60 in detected_midis
        assert 64 in detected_midis
        assert 67 in detected_midis

    def test_g_major_triad(self, detector):
        """4. Detect G Major triad (G3, B3, D4 = MIDI 55, 59, 62)."""
        signal = get_preset_signal("G_MAJOR", duration=0.5, sr=22050)
        result = detector.detect_frame(signal[:4096])

        assert result["status"] == "DETECTED"
        detected_midis = [n.midi for n in result["notes"]]
        assert 55 in detected_midis
        assert 59 in detected_midis
        assert 62 in detected_midis

    def test_a_minor_triad(self, detector):
        """5. Detect A Minor triad (A3, C4, E4 = MIDI 57, 60, 64)."""
        signal = get_preset_signal("A_MINOR", duration=0.5, sr=22050)
        result = detector.detect_frame(signal[:4096])

        assert result["status"] == "DETECTED"
        detected_midis = [n.midi for n in result["notes"]]
        assert 57 in detected_midis
        assert 60 in detected_midis
        assert 64 in detected_midis

    def test_c_minor_triad(self, detector):
        """6. Detect C Minor triad (C4, Eb4, G4 = MIDI 60, 63, 67)."""
        signal = get_preset_signal("C_MINOR", duration=0.5, sr=22050)
        result = detector.detect_frame(signal[:4096])

        assert result["status"] == "DETECTED"
        detected_midis = [n.midi for n in result["notes"]]
        assert 60 in detected_midis
        assert 63 in detected_midis
        assert 67 in detected_midis

    def test_c7_four_note_chord(self, detector):
        """7. Detect C7 dominant 7th chord (C4, E4, G4, Bb4 = MIDI 60, 64, 67, 70)."""
        signal = get_preset_signal("C7", duration=0.5, sr=22050)
        result = detector.detect_frame(signal[:4096])

        assert result["status"] == "DETECTED"
        detected_midis = [n.midi for n in result["notes"]]
        assert 60 in detected_midis
        assert 64 in detected_midis
        assert 67 in detected_midis
        assert 70 in detected_midis

    def test_cmaj7_four_note_chord(self, detector):
        """8. Detect Cmaj7 major 7th chord (C4, E4, G4, B4 = MIDI 60, 64, 67, 71)."""
        signal = get_preset_signal("CMAJ7", duration=0.5, sr=22050)
        result = detector.detect_frame(signal[:4096])

        assert result["status"] == "DETECTED"
        detected_midis = [n.midi for n in result["notes"]]
        assert 60 in detected_midis
        assert 64 in detected_midis
        assert 67 in detected_midis
        assert 71 in detected_midis

    def test_c_over_e_slash_chord(self, detector):
        """9. Detect C/E slash chord (E3 bass + C4, E4, G4 = MIDI 52, 60, 64, 67)."""
        signal = get_preset_signal("C_OVER_E", duration=0.5, sr=22050)
        result = detector.detect_frame(signal[:4096])

        assert result["status"] == "DETECTED"
        detected_midis = [n.midi for n in result["notes"]]
        assert 52 in detected_midis  # E3 bass note
        assert 60 in detected_midis  # C4
        assert 67 in detected_midis  # G4

    def test_silence_input(self, detector):
        """14. Silence produces NO_INPUT status and zero notes."""
        silence = generate_silence(duration=0.5, sr=22050)
        result = detector.detect_frame(silence[:4096])

        assert result["status"] == "NO_INPUT"
        assert len(result["notes"]) == 0
        assert result["confidence"] == 0.0

    def test_noise_input(self, detector):
        """15. White/Pink noise without harmonic structure is rejected or marked LOW_CONFIDENCE."""
        noise = generate_noise(duration=0.5, sr=22050, amplitude=0.08)
        result = detector.detect_frame(noise[:4096])

        # Noise has no coherent harmonic comb, should have low confidence or zero notes
        assert result["confidence"] < 0.40

    def test_harmonic_overtone_suppression(self, detector):
        """16. Strong overtone harmonics (C5/G5) are suppressed when playing single C4."""
        # Synthesize C4 with 8 strong harmonics
        signal = generate_piano_tone(midi_to_freq(60), duration=0.5, sr=22050, num_harmonics=8)
        result = detector.detect_frame(signal[:4096])

        assert result["status"] == "DETECTED"
        assert len(result["notes"]) == 1
        assert result["notes"][0].midi == 60
        # C5 (72) and G5 (79) must NOT be reported as distinct played notes
        detected_midis = [n.midi for n in result["notes"]]
        assert 72 not in detected_midis
        assert 79 not in detected_midis

    def test_temporal_persistence_and_release(self, tracker):
        """17 & 18. Note-On requires >= 2 frames; Note-Off requires >= 3 frames of absence."""
        c4_signal = generate_piano_tone(midi_to_freq(60), duration=0.5, sr=22050)
        c4_frame = c4_signal[:4096]
        silence_frame = generate_silence(duration=0.5, sr=22050)[:4096]

        tracker.reset()

        # Frame 1: Candidate count = 1 (< 2 threshold -> not yet active)
        f1 = tracker.process_frame(c4_frame)
        assert len(f1["notes"]) == 0

        # Frame 2: Candidate count = 2 (>= 2 threshold -> active)
        f2 = tracker.process_frame(c4_frame)
        assert len(f2["notes"]) == 1
        assert f2["notes"][0].midi == 60

        # Frame 3: Consecutive active frame continues
        f3 = tracker.process_frame(c4_frame)
        assert len(f3["notes"]) == 1

        # Now test release hysteresis: Note stops sounding
        # Frame 4 (1st silent frame): Still held active (missing = 1 < 3)
        f4 = tracker.process_frame(silence_frame)
        assert len(f4["notes"]) == 1

        # Frame 5 (2nd silent frame): Still held active (missing = 2 < 3)
        f5 = tracker.process_frame(silence_frame)
        assert len(f5["notes"]) == 1

        # Frame 6 (3rd silent frame): Released (missing = 3 >= 3)
        f6 = tracker.process_frame(silence_frame)
        assert len(f6["notes"]) == 0
