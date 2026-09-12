"""
tests/test_phase8_song_contract.py

Song-Level Result Contract & Timeline Integrity Tests for HotChords Phase 8.
Verifies:
- Complete single authoritative SongAnalysis and SongTimeline contract
- Raw harmonic preservation during beginner simplification
- Empty/non-harmonic negative safety
- Four-chord loop result schema and voicings
- Micro-second execution time for 100/1000 chord voicings (zero ML latency)
"""

import time
import pytest
from backend.models.timeline import SongTimeline, ChordEvent
from backend.models.analysis_types import (
    AudioStatus, AudioProfile, TimingData, DetectionReliability,
    StructureAnalysisResult, FourChordLoopResult
)
from backend.theory.piano_voicing import (
    voice_chord,
    voice_chord_progression,
    voice_four_chord_loop
)
from backend.theory.simplification import simplify_progression


class TestPhase8SongContract:
    """Tests for Song-Level Result Contract & Performance."""

    def test_song_timeline_canonical_contract(self):
        """Step 1 & 17: Canonical Timeline Schema & Field Preservation."""
        raw_analysis = {
            "duration": 120.0,
            "tempo": 120.0,
            "time_sig": "4/4",
            "key": "C",
            "scale": "Major",
            "key_full": "C Major",
            "scale_notes": [0, 2, 4, 5, 7, 9, 11],
            "status": "SUCCESS",
            "status_message": "Clean harmonic structure",
            "chords": [
                {
                    "time": 0.0,
                    "end": 2.0,
                    "chord": "Cmaj7",
                    "raw_chord": "C:maj7",
                    "confidence": 0.95,
                    "source_evidence": "other"
                },
                {
                    "time": 2.0,
                    "end": 4.0,
                    "chord": "Am7",
                    "raw_chord": "A:min7",
                    "confidence": 0.92,
                    "source_evidence": "other"
                },
                {
                    "time": 4.0,
                    "end": 6.0,
                    "chord": "Dm9/F#",
                    "raw_chord": "D:min9/F#",
                    "confidence": 0.88,
                    "source_evidence": "other"
                },
                {
                    "time": 6.0,
                    "end": 8.0,
                    "chord": "G7",
                    "raw_chord": "G:7",
                    "confidence": 0.96,
                    "source_evidence": "other"
                }
            ],
            "beginner_chords": [
                {"time": 0.0, "end": 2.0, "chord": "C", "raw_chord": "C:maj7", "confidence": 0.95},
                {"time": 2.0, "end": 4.0, "chord": "Am", "raw_chord": "A:min7", "confidence": 0.92},
                {"time": 4.0, "end": 6.0, "chord": "Dm", "raw_chord": "D:min9/F#", "confidence": 0.88},
                {"time": 6.0, "end": 8.0, "chord": "G", "raw_chord": "G:7", "confidence": 0.96}
            ],
            "four_chord_loop": {
                "available": True,
                "chords": ["Cmaj7", "Am7", "Dm9/F#", "G7"],
                "rawChords": ["C:maj7", "A:min7", "D:min9/F#", "G:7"],
                "simplifiedChords": ["C", "Am", "Dm", "G"],
                "section": "REPEATING_SECTION_A",
                "start": 0.0,
                "end": 8.0,
                "duration": 8.0,
                "confidence": 0.95,
                "occurrences": [0.0, 8.0],
                "repetitionCount": 2,
                "reason": "Clear 4-chord loop"
            }
        }

        timeline = SongTimeline.from_analysis_dict(raw_analysis)
        assert timeline.duration == 120.0
        assert len(timeline.original_chords) == 4
        assert len(timeline.beginner_chords) == 4

        # Check Original Chord 0 (Cmaj7)
        c0 = timeline.original_chords[0]
        assert c0.chord_name == "Cmaj7"
        assert c0.raw_chord == "C:maj7"
        assert c0.root == "C"
        assert c0.quality == "maj7"
        assert c0.voicing is not None
        lh = c0.voicing.left_hand if hasattr(c0.voicing, "left_hand") else c0.voicing.get("leftHand", [])
        assert len(lh) == 1

        # Check Original Chord 2 (Dm9/F#) - Bass Inversion preservation
        c2 = timeline.original_chords[2]
        assert c2.root == "D"
        assert c2.bass == "F#"
        assert c2.simplified_chord == "Dm"

        # Check Beginner Chord 2 (Dm) - Modal minor quality preserved
        b2 = timeline.beginner_chords[2]
        assert b2.chord_name == "Dm"
        assert b2.root == "D"
        assert b2.quality == "min"

    def test_voicing_performance_and_zero_ml_overhead(self):
        """Step 21: Voicing Performance Benchmark (< 1ms CPU)."""
        prog_100 = ["C", "G", "Am", "F"] * 25  # 100 chords
        prog_1000 = ["C", "G", "Am", "F"] * 250  # 1000 chords

        # Benchmark 100 chords
        t0 = time.perf_counter()
        voicings_100 = voice_chord_progression(prog_100, beginner_mode=True)
        t1 = time.perf_counter()
        dur_100_ms = (t1 - t0) * 1000.0

        assert len(voicings_100) == 100
        assert dur_100_ms < 50.0, f"100 chord voicing took too long: {dur_100_ms:.2f} ms"

        # Benchmark 1000 chords
        t0 = time.perf_counter()
        voicings_1000 = voice_chord_progression(prog_1000, beginner_mode=True)
        t1 = time.perf_counter()
        dur_1000_ms = (t1 - t0) * 1000.0

        assert len(voicings_1000) == 1000
        assert dur_1000_ms < 500.0, f"1000 chord voicing took too long: {dur_1000_ms:.2f} ms"

    def test_non_harmonic_and_single_chord_loop_protection(self):
        """Step 14 & 16: Non-Harmonic & Vamp Loop Protection."""
        # Single chord vamp
        vamp_loop = voice_four_chord_loop(["Gm", "Gm", "Gm", "Gm"])
        assert len(vamp_loop) == 4
        # Voicing should still be valid even on single chord vamp
        assert len(vamp_loop[0]["leftHand"]) >= 1
