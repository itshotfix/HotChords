"""
tests/test_four_chord_loop.py

Comprehensive tests for Phase 4 Four-Chord Loop & Progression Detection Engine:
1. Standard C -> G -> Am -> F progression detection
2. Repeated 4-chord progression ranking
3. Sustained single chord rejection (C | C | C | C != 4 chords)
4. NO_CHORD ('N') exclusion
5. Transposition-aware matching (C-G-Am-F vs D-A-Bm-G)
6. Complex extension simplification (Cmaj7 -> G7 -> Am7 -> Fmaj7)
7. Clean available=False output on songs without reliable loops
"""

import pytest
from backend.analysis.loop_detection import (
    FourChordLoopDetector,
    detect_four_chord_loop,
)
from backend.models.analysis_types import (
    FourChordLoopResult,
    StructureAnalysisResult,
    StructureSection,
)


class TestFourChordLoop:

    def test_standard_four_chord_progression(self):
        """Verify clean extraction and high confidence on classic C -> G -> Am -> F progression."""
        # 16-second progression repeating twice (total 32s)
        chords = [
            # Pass 1 (0-16s)
            {"time": 0.0, "end": 4.0, "chord": "C", "confidence": 0.95},
            {"time": 4.0, "end": 8.0, "chord": "G", "confidence": 0.92},
            {"time": 8.0, "end": 12.0, "chord": "Am", "confidence": 0.94},
            {"time": 12.0, "end": 16.0, "chord": "F", "confidence": 0.91},
            # Pass 2 (16-32s)
            {"time": 16.0, "end": 20.0, "chord": "C", "confidence": 0.96},
            {"time": 20.0, "end": 24.0, "chord": "G", "confidence": 0.93},
            {"time": 24.0, "end": 28.0, "chord": "Am", "confidence": 0.95},
            {"time": 28.0, "end": 32.0, "chord": "F", "confidence": 0.90},
        ]

        res = detect_four_chord_loop(chords=chords, duration=32.0)
        assert isinstance(res, FourChordLoopResult)
        assert res.available is True
        assert res.chords == ["C", "G", "Am", "F"]
        assert res.simplified_chords == ["C", "G", "Am", "F"]
        assert res.repetition_count >= 2
        assert len(res.occurrences) >= 2
        assert res.confidence >= 0.70
        assert res.start == 0.0

    def test_sustained_chord_rejection(self):
        """Verify that four consecutive slices of a sustained C chord are rejected as a 4-chord loop."""
        # 4 slices of C: C | C | C | C (sustained single chord)
        chords = [
            {"time": 0.0, "end": 2.0, "chord": "C", "confidence": 0.95},
            {"time": 2.0, "end": 4.0, "chord": "C", "confidence": 0.95},
            {"time": 4.0, "end": 6.0, "chord": "C", "confidence": 0.95},
            {"time": 6.0, "end": 8.0, "chord": "C", "confidence": 0.95},
        ]

        res = detect_four_chord_loop(chords=chords, duration=8.0)
        assert isinstance(res, FourChordLoopResult)
        assert res.available is False
        assert "INSUFFICIENT" in res.reason or "NO_VALID" in res.reason

    def test_no_chord_exclusion(self):
        """Verify that NO_CHORD ('N') cannot count as one of the 4 chords."""
        chords = [
            {"time": 0.0, "end": 2.0, "chord": "C", "confidence": 0.90},
            {"time": 2.0, "end": 4.0, "chord": "G", "confidence": 0.90},
            {"time": 4.0, "end": 6.0, "chord": "Am", "confidence": 0.90},
            {"time": 6.0, "end": 8.0, "chord": "N", "confidence": 0.90},
        ]

        res = detect_four_chord_loop(chords=chords, duration=8.0)
        assert isinstance(res, FourChordLoopResult)
        assert res.available is False

    def test_transposition_aware_matching(self):
        """Verify that key-shifted repetitions (C-G-Am-F and D-A-Bm-G) match under relative root cycle analysis."""
        chords = [
            # Section 1 in C (0-16s)
            {"time": 0.0, "end": 4.0, "chord": "C", "confidence": 0.92},
            {"time": 4.0, "end": 8.0, "chord": "G", "confidence": 0.90},
            {"time": 8.0, "end": 12.0, "chord": "Am", "confidence": 0.91},
            {"time": 12.0, "end": 16.0, "chord": "F", "confidence": 0.89},
            # Section 2 modulated +2 semitones to D (16-32s)
            {"time": 16.0, "end": 20.0, "chord": "D", "confidence": 0.93},
            {"time": 20.0, "end": 24.0, "chord": "A", "confidence": 0.91},
            {"time": 24.0, "end": 28.0, "chord": "Bm", "confidence": 0.92},
            {"time": 28.0, "end": 32.0, "chord": "G", "confidence": 0.90},
        ]

        res = detect_four_chord_loop(chords=chords, duration=32.0)
        assert isinstance(res, FourChordLoopResult)
        assert res.available is True
        # Both share the exact relative root delta cycle: (+7, +2, +8, +5) and qualities (maj, maj, min, maj)
        assert res.repetition_count >= 2
        assert res.confidence >= 0.70

    def test_extended_chord_simplification_preservation(self):
        """Verify that raw extended chords are preserved alongside simplified triads."""
        chords = [
            {"time": 0.0, "end": 4.0, "chord": "Cmaj7", "raw_chord": "C:maj7", "confidence": 0.95},
            {"time": 4.0, "end": 8.0, "chord": "G7", "raw_chord": "G:7", "confidence": 0.92},
            {"time": 8.0, "end": 12.0, "chord": "Am7", "raw_chord": "A:min7", "confidence": 0.94},
            {"time": 12.0, "end": 16.0, "chord": "Fmaj7", "raw_chord": "F:maj7", "confidence": 0.91},
            {"time": 16.0, "end": 20.0, "chord": "Cmaj7", "raw_chord": "C:maj7", "confidence": 0.95},
            {"time": 20.0, "end": 24.0, "chord": "G7", "raw_chord": "G:7", "confidence": 0.92},
            {"time": 24.0, "end": 28.0, "chord": "Am7", "raw_chord": "A:min7", "confidence": 0.94},
            {"time": 28.0, "end": 32.0, "chord": "Fmaj7", "raw_chord": "F:maj7", "confidence": 0.91},
        ]

        res = detect_four_chord_loop(chords=chords, duration=32.0)
        assert isinstance(res, FourChordLoopResult)
        assert res.available is True
        assert res.chords == ["Cmaj7", "G7", "Am7", "Fmaj7"]
        assert res.simplified_chords == ["C", "G", "Am", "F"]

    def test_no_reliable_loop_song(self):
        """Verify that erratic / through-composed harmony returns available=False with clean explanation."""
        # 12 completely unrelated random chords with low confidence
        chords = [
            {"time": float(i * 2), "end": float((i + 1) * 2), "chord": c, "confidence": 0.35}
            for i, c in enumerate(["F#dim", "B7", "Edim", "A7", "Ddim", "G7", "Cdim", "F7", "Bbdim", "Eb7", "Abdim", "Db7"])
        ]

        res = detect_four_chord_loop(chords=chords, duration=24.0)
        assert isinstance(res, FourChordLoopResult)
        assert res.available is False
        assert "LOW_CONFIDENCE" in res.reason or "NO_RELIABLE" in res.reason
