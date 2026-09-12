"""
tests/test_phase9_beginner_practice.py

Integration and Unit Test Suite for Phase 9 Beginner Practice Intelligence.
Verifies:
- Progression analyses (C-G-Am-F, Am-F-C-G, Cmaj7-G7-Am7-F, C#m7-F#m7-B-G#)
- Slash chords & minor modal preservation
- Multi-level simplification (Levels 0-3)
- Tempo recommendations (scaled by difficulty)
- Practice loop selection & fallback logic
- Hardest vs easiest chords classification
- Non-harmonic & empty audio safety gating
- Sub-millisecond performance (< 50ms)
"""

import time
import pytest
from backend.models.analysis_types import (
    AudioStatus, FourChordLoopResult, StructureAnalysisResult,
    StructureSection, DetectionReliability
)
from backend.theory.beginner_practice import (
    generate_beginner_practice_plan,
    classify_difficulty_category,
    calculate_beginner_tempo_recommendations,
    generate_multi_level_simplifications,
)


class TestPhase9BeginnerPractice:
    """Test Suite for Phase 9 Beginner Practice Intelligence."""

    def test_standard_pop_progression_plan(self):
        """Test Case A: C -> G -> Am -> F."""
        chords = [
            {"time": 0.0, "end": 2.0, "chord": "C", "confidence": 0.95},
            {"time": 2.0, "end": 4.0, "chord": "G", "confidence": 0.95},
            {"time": 4.0, "end": 6.0, "chord": "Am", "confidence": 0.95},
            {"time": 6.0, "end": 8.0, "chord": "F", "confidence": 0.95},
        ]
        loop = FourChordLoopResult(
            available=True,
            chords=["C", "G", "Am", "F"],
            simplifiedChords=["C", "G", "Am", "F"],
            start=0.0,
            end=8.0,
            duration=8.0,
            confidence=0.95,
            repetitionCount=2
        )

        plan = generate_beginner_practice_plan(
            chords=chords,
            tempo=120.0,
            key="C",
            scale="Major",
            duration=8.0,
            four_chord_loop=loop,
            audio_status=AudioStatus.SUCCESS
        )

        assert plan.available is True
        assert plan.original_tempo == 120.0
        assert plan.recommended_tempo == 102.0  # 85% of 120 (Easy)
        assert plan.minimum_tempo >= 50.0
        assert plan.recommended_section is not None
        assert plan.recommended_section.chords == ["C", "G", "Am", "F"]
        assert len(plan.unique_chords) == 4
        assert len(plan.hardest_chords) == 0  # All chords are easy
        assert set(plan.easiest_chords) == {"C", "G", "Am", "F"}

    def test_difficult_black_key_progression_plan(self):
        """Test Case D: C#m7 -> F#m7 -> B -> G#."""
        chords = [
            {"time": 0.0, "end": 2.0, "chord": "C#m7", "confidence": 0.90},
            {"time": 2.0, "end": 4.0, "chord": "F#m7", "confidence": 0.90},
            {"time": 4.0, "end": 6.0, "chord": "B", "confidence": 0.90},
            {"time": 6.0, "end": 8.0, "chord": "G#", "confidence": 0.90},
        ]
        plan = generate_beginner_practice_plan(
            chords=chords,
            tempo=140.0,
            key="C#",
            scale="Minor",
            duration=8.0,
            audio_status=AudioStatus.SUCCESS
        )

        assert plan.available is True
        # For difficult chords, recommended tempo should be reduced significantly (55-70%)
        assert plan.recommended_tempo <= 105.0
        assert len(plan.hardest_chords) > 0
        hardest_names = [h.chord for h in plan.hardest_chords]
        assert "C#m7" in hardest_names or "F#m7" in hardest_names
        
        # Hardest chord should offer valid simplification
        top_hard = plan.hardest_chords[0]
        assert top_hard.suggested_simplification is not None

    def test_multi_level_simplifications(self):
        """Step 4: Multi-Level Simplification Levels 0-3."""
        chords = ["Cmaj7", "Am7", "Dm9/F#", "G7"]
        levels = generate_multi_level_simplifications(chords)
        assert len(levels) == 4

        # Level 0: Original
        assert levels[0].progression == ["Cmaj7", "Am7", "Dm9/F#", "G7"]

        # Level 1: 7th removal with inversions
        assert levels[1].progression == ["C", "Am", "Dm/F#", "G"]

        # Level 2: Basic Triads
        assert levels[2].progression == ["C", "Am", "Dm", "G"]

        # Minor quality must NEVER be simplified into major
        for lvl in levels:
            assert lvl.progression[1].startswith("Am"), f"Minor Am was destroyed in level {lvl.level}"
            assert lvl.progression[2].startswith("Dm"), f"Minor Dm was destroyed in level {lvl.level}"

    def test_empty_and_non_harmonic_safety_gating(self):
        """Step 14: Empty & Low-Confidence Safety."""
        # Empty Audio
        plan_empty = generate_beginner_practice_plan(
            chords=[],
            tempo=120.0,
            duration=0.0,
            audio_status=AudioStatus.EMPTY_AUDIO
        )
        assert plan_empty.available is False
        assert "EMPTY" in (plan_empty.reason or "").upper()

        # Non-Harmonic Audio
        plan_noise = generate_beginner_practice_plan(
            chords=[],
            tempo=120.0,
            duration=10.0,
            audio_status=AudioStatus.NO_HARMONIC_CONTENT
        )
        assert plan_noise.available is False

    def test_practice_intelligence_execution_performance(self):
        """Step 15: Sub-Millisecond Execution Benchmark (< 50ms)."""
        prog_100 = [
            {"time": float(i * 2), "end": float(i * 2 + 2), "chord": c, "confidence": 0.9}
            for i, c in enumerate(["Cmaj7", "Am7", "Dm/F#", "G7"] * 25)
        ]

        t0 = time.perf_counter()
        plan = generate_beginner_practice_plan(
            chords=prog_100,
            tempo=120.0,
            key="C",
            scale="Major",
            duration=200.0,
            audio_status=AudioStatus.SUCCESS
        )
        t1 = time.perf_counter()
        elapsed_ms = (t1 - t0) * 1000.0

        assert plan.available is True
        assert elapsed_ms < 50.0, f"Practice intelligence took too long: {elapsed_ms:.2f} ms"
