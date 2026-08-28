"""
tests/test_simplification.py

Focused unit tests for the Beginner Simplification Engine (Phase 2B).
"""

import unittest
from backend.models.timeline import SongTimeline, ChordEvent, SongMetadata
from backend.theory.simplification import (
    reduce_chord_harmony,
    evaluate_beginner_difficulty,
    simplify_progression,
    simplify_timeline,
)


class TestBeginnerSimplificationEngine(unittest.TestCase):

    def test_harmonic_reduction_core_examples(self):
        """Test required chord reductions: Cmaj7 -> C, Am7 -> Am, Fmaj7 -> F, G7 -> G."""
        self.assertEqual(reduce_chord_harmony("Cmaj7"), "C")
        self.assertEqual(reduce_chord_harmony("Am7"), "Am")
        self.assertEqual(reduce_chord_harmony("Fmaj7"), "F")
        self.assertEqual(reduce_chord_harmony("G7"), "G")

    def test_major_and_minor_preservation(self):
        """Test that major chords remain major and minor chords remain minor."""
        major_chords = ["C", "D", "E", "F", "G", "A", "B", "Eb", "Ab", "Bb", "F#"]
        for c in major_chords:
            self.assertEqual(reduce_chord_harmony(c), c)

        minor_chords = ["Cm", "Dm", "Em", "Fm", "Gm", "Am", "Bm", "Ebm", "Abm", "Bbm", "F#m"]
        for c in minor_chords:
            self.assertEqual(reduce_chord_harmony(c), c)

    def test_extended_chord_reduction(self):
        """Test removing non-essential extensions (maj9, m9, 11, 13, etc.)."""
        self.assertEqual(reduce_chord_harmony("Cmaj9"), "C")
        self.assertEqual(reduce_chord_harmony("Dm9"), "Dm")
        self.assertEqual(reduce_chord_harmony("G13"), "G")
        self.assertEqual(reduce_chord_harmony("Em11"), "Em")
        self.assertEqual(reduce_chord_harmony("Aadd9"), "A")

    def test_diminished_harmony_resolution(self):
        """Test diminished chord diatonic resolution in key context and fallback."""
        # In C Major (major key): Bdim (vii°) -> G (V)
        self.assertEqual(reduce_chord_harmony("Bdim", key="C", scale="Major"), "G")
        # In A Minor (minor key): Bdim (ii°) -> Dm (iv)
        self.assertEqual(reduce_chord_harmony("Bdim", key="A", scale="Minor"), "Dm")
        # Without key context: safe fallback to root minor
        self.assertEqual(reduce_chord_harmony("Bdim"), "Bm")

    def test_suspended_and_fallback(self):
        """Test sus2/sus4 preservation and safe fallback for unknown inputs."""
        self.assertEqual(reduce_chord_harmony("Dsus4"), "Dsus4")
        self.assertEqual(reduce_chord_harmony("Gsus2"), "Gsus2")
        self.assertEqual(reduce_chord_harmony("N"), "N")
        self.assertEqual(reduce_chord_harmony(""), "N")
        self.assertEqual(reduce_chord_harmony("UnknownSymbol123"), "N")

    def test_difficulty_evaluation(self):
        """Test beginner difficulty categorization (EASY, MODERATE, DIFFICULT)."""
        self.assertEqual(evaluate_beginner_difficulty("C"), "EASY")
        self.assertEqual(evaluate_beginner_difficulty("Am"), "EASY")
        self.assertEqual(evaluate_beginner_difficulty("G"), "EASY")

        self.assertEqual(evaluate_beginner_difficulty("Eb"), "MODERATE")
        self.assertEqual(evaluate_beginner_difficulty("F#"), "MODERATE")

        self.assertEqual(evaluate_beginner_difficulty("Bdim"), "DIFFICULT")
        self.assertEqual(evaluate_beginner_difficulty("Abm"), "DIFFICULT")

    def test_consecutive_identical_chords_merge(self):
        """Test that adjacent identical simplified chords merge into a continuous block."""
        input_chords = [
            ChordEvent(startTime=0.0, endTime=1.0, chordName="Cmaj7", confidence=0.9),
            ChordEvent(startTime=1.0, endTime=2.0, chordName="C", confidence=0.95),
            ChordEvent(startTime=2.0, endTime=3.0, chordName="Am7", confidence=0.85),
            ChordEvent(startTime=3.0, endTime=4.0, chordName="Am", confidence=0.88),
        ]
        result = simplify_progression(input_chords, tempo=120.0)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].chord_name, "C")
        self.assertEqual(result[0].start_time, 0.0)
        self.assertEqual(result[0].end_time, 2.0)
        self.assertEqual(result[1].chord_name, "Am")
        self.assertEqual(result[1].start_time, 2.0)
        self.assertEqual(result[1].end_time, 4.0)

    def test_short_passing_chords_absorption(self):
        """Test that short passing chords below threshold are absorbed into surrounding context."""
        input_chords = [
            ChordEvent(startTime=0.0, endTime=4.0, chordName="C", confidence=0.95),
            ChordEvent(startTime=4.0, endTime=4.3, chordName="G", confidence=0.4),  # 0.3s transient
            ChordEvent(startTime=4.3, endTime=8.0, chordName="F", confidence=0.92),
        ]
        result = simplify_progression(input_chords, tempo=120.0, min_duration_seconds=1.0)
        # Passing chord absorbed, resulting in 2 stable chords
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].chord_name, "C")
        self.assertEqual(result[1].chord_name, "F")
        self.assertEqual(result[0].start_time, 0.0)
        self.assertEqual(result[1].end_time, 8.0)

    def test_bpm_aware_threshold(self):
        """Test that BPM-aware threshold scales passing duration based on tempo."""
        fast_chords = [
            ChordEvent(startTime=0.0, endTime=2.0, chordName="C", confidence=0.9),
            ChordEvent(startTime=2.0, endTime=2.7, chordName="D", confidence=0.5),  # 0.7s
            ChordEvent(startTime=2.7, endTime=5.0, chordName="G", confidence=0.9),
        ]
        # At 60 BPM (slow), 2 beats = 2.0s -> 0.7s chord is absorbed
        res_slow = simplify_progression(fast_chords, tempo=60.0)
        self.assertEqual(len(res_slow), 2)

        # At 180 BPM (fast), 2 beats = 0.67s -> clamped min 0.8s
        res_fast = simplify_progression(fast_chords, tempo=180.0, min_duration_seconds=0.5)
        self.assertEqual(len(res_fast), 3)

    def test_original_chords_remain_untouched(self):
        """Test that SongTimeline.original_chords is never mutated by simplification."""
        orig = [
            ChordEvent(startTime=0.0, endTime=2.0, chordName="Cmaj7", confidence=0.95),
            ChordEvent(startTime=2.0, endTime=4.0, chordName="Am7", confidence=0.92),
        ]
        meta = SongMetadata(duration=4.0, tempo=120.0, key="C", scale="Major")
        timeline = SongTimeline(
            metadata=meta,
            duration=4.0,
            originalChords=orig,
            beginnerChords=None
        )

        simplify_timeline(timeline)

        # original_chords must remain exactly Cmaj7 and Am7
        self.assertEqual(len(timeline.original_chords), 2)
        self.assertEqual(timeline.original_chords[0].chord_name, "Cmaj7")
        self.assertEqual(timeline.original_chords[1].chord_name, "Am7")

        # beginner_chords must be populated with C and Am
        self.assertIsNotNone(timeline.beginner_chords)
        self.assertEqual(len(timeline.beginner_chords), 2)
        self.assertEqual(timeline.beginner_chords[0].chord_name, "C")
        self.assertEqual(timeline.beginner_chords[1].chord_name, "Am")

    def test_missing_metadata_does_not_crash(self):
        """Test that missing optional metadata or empty timeline handles cleanly."""
        empty_timeline = SongTimeline(
            metadata=SongMetadata(duration=0.0),
            duration=0.0,
            originalChords=[]
        )
        res = simplify_timeline(empty_timeline)
        self.assertEqual(res.beginner_chords, [])

    # ══════════════════════════════════════════════════════════════
    #  PHASE 2D: REALISTIC MULTI-EVENT PROGRESSION FIXTURES
    # ══════════════════════════════════════════════════════════════

    def test_sample_a_pop_progression_cmaj7_g7_am7_fmaj7(self):
        """Sample A: Cmaj7 -> G7 -> Am7 -> Fmaj7 reduces to C -> G -> Am -> F."""
        chords = [
            ChordEvent(startTime=0.0, endTime=2.0, chordName="Cmaj7", confidence=0.95),
            ChordEvent(startTime=2.0, endTime=4.0, chordName="G7", confidence=0.92),
            ChordEvent(startTime=4.0, endTime=6.0, chordName="Am7", confidence=0.90),
            ChordEvent(startTime=6.0, endTime=8.0, chordName="Fmaj7", confidence=0.93),
        ]
        meta = SongMetadata(duration=8.0, tempo=120.0, key="C", scale="Major", key_full="C Major")
        timeline = SongTimeline(metadata=meta, duration=8.0, originalChords=chords, beginnerChords=None)

        simplify_timeline(timeline)

        # 1. original_chords must be 100% unchanged
        self.assertEqual(len(timeline.original_chords), 4)
        self.assertEqual([c.chord_name for c in timeline.original_chords], ["Cmaj7", "G7", "Am7", "Fmaj7"])

        # 2. beginner_chords must be simplified
        self.assertEqual(len(timeline.beginner_chords), 4)
        self.assertEqual([c.chord_name for c in timeline.beginner_chords], ["C", "G", "Am", "F"])

        # 3. Timing and event ordering preserved
        for orig, beg in zip(timeline.original_chords, timeline.beginner_chords):
            self.assertEqual(orig.start_time, beg.start_time)
            self.assertEqual(orig.end_time, beg.end_time)

        # 4. No auto-transposition
        self.assertEqual(timeline.metadata.easy_key, "C")
        self.assertEqual(timeline.metadata.transpose_offset, 0)

    def test_sample_b_jazz_progression_dm7_g7_cmaj7_am7(self):
        """Sample B: Dm7 -> G7 -> Cmaj7 -> Am7 reduces to Dm -> G -> C -> Am."""
        chords = [
            ChordEvent(startTime=0.0, endTime=2.0, chordName="Dm7", confidence=0.91),
            ChordEvent(startTime=2.0, endTime=4.0, chordName="G7", confidence=0.94),
            ChordEvent(startTime=4.0, endTime=6.0, chordName="Cmaj7", confidence=0.96),
            ChordEvent(startTime=6.0, endTime=8.0, chordName="Am7", confidence=0.89),
        ]
        meta = SongMetadata(duration=8.0, tempo=110.0, key="C", scale="Major", key_full="C Major")
        timeline = SongTimeline(metadata=meta, duration=8.0, originalChords=chords, beginnerChords=None)

        simplify_timeline(timeline)

        self.assertEqual([c.chord_name for c in timeline.original_chords], ["Dm7", "G7", "Cmaj7", "Am7"])
        self.assertEqual([c.chord_name for c in timeline.beginner_chords], ["Dm", "G", "C", "Am"])
        self.assertEqual([c.difficulty for c in timeline.beginner_chords], ["EASY", "EASY", "EASY", "EASY"])

    def test_sample_c_passing_chord_smoothing(self):
        """Sample C: C -> C#dim (0.35s passing) -> Dm7 -> G7 absorbs short passing chord."""
        chords = [
            ChordEvent(startTime=0.0, endTime=2.0, chordName="C", confidence=0.95),
            ChordEvent(startTime=2.0, endTime=2.35, chordName="C#dim", confidence=0.45),  # Passing
            ChordEvent(startTime=2.35, endTime=4.35, chordName="Dm7", confidence=0.90),
            ChordEvent(startTime=4.35, endTime=6.35, chordName="G7", confidence=0.92),
        ]
        meta = SongMetadata(duration=6.35, tempo=120.0, key="C", scale="Major", key_full="C Major")
        timeline = SongTimeline(metadata=meta, duration=6.35, originalChords=chords, beginnerChords=None)

        simplify_timeline(timeline)

        # Original chords untouched
        self.assertEqual(len(timeline.original_chords), 4)
        self.assertEqual(timeline.original_chords[1].chord_name, "C#dim")

        # Passing chord absorbed, resulting in 3 main chords
        self.assertEqual(len(timeline.beginner_chords), 3)
        self.assertEqual([c.chord_name for c in timeline.beginner_chords], ["C", "Dm", "G"])
        self.assertEqual(timeline.beginner_chords[0].start_time, 0.0)
        self.assertEqual(timeline.beginner_chords[0].end_time, 2.35)
        self.assertEqual(timeline.beginner_chords[1].start_time, 2.35)
        self.assertEqual(timeline.beginner_chords[1].end_time, 4.35)
        self.assertEqual(timeline.beginner_chords[2].start_time, 4.35)
        self.assertEqual(timeline.beginner_chords[2].end_time, 6.35)

    def test_sample_d_flat_key_bbmaj7_gm7_cm7_f7(self):
        """Sample D: Bbmaj7 -> Gm7 -> Cm7 -> F7 in Bb Major preserves flat spellings without transposition."""
        chords = [
            ChordEvent(startTime=0.0, endTime=2.0, chordName="Bbmaj7", confidence=0.93),
            ChordEvent(startTime=2.0, endTime=4.0, chordName="Gm7", confidence=0.91),
            ChordEvent(startTime=4.0, endTime=6.0, chordName="Cm7", confidence=0.88),
            ChordEvent(startTime=6.0, endTime=8.0, chordName="F7", confidence=0.94),
        ]
        meta = SongMetadata(duration=8.0, tempo=100.0, key="Bb", scale="Major", key_full="Bb Major")
        timeline = SongTimeline(metadata=meta, duration=8.0, originalChords=chords, beginnerChords=None)

        simplify_timeline(timeline)

        # Original chords untouched
        self.assertEqual([c.chord_name for c in timeline.original_chords], ["Bbmaj7", "Gm7", "Cm7", "F7"])

        # Beginner chords correctly simplified with flat names preserved
        self.assertEqual([c.chord_name for c in timeline.beginner_chords], ["Bb", "Gm", "Cm", "F"])

        # No auto-transposition occurred
        self.assertEqual(timeline.metadata.easy_key, "Bb")
        self.assertEqual(timeline.metadata.easy_key_full, "Bb Major")
        self.assertEqual(timeline.metadata.transpose_offset, 0)


if __name__ == "__main__":
    unittest.main()

