"""
tests/test_phase9_transposition.py

Unit and Integration Tests for Phase 9 Transposition Engine & Beginner Key Recommendation.
Verifies:
- Note name transposition
- Chord symbol transposition (triads, 7ths, suspensions, altered)
- Slash chord transposition (root + bass note)
- Harte syntax preservation during transposition
- Global progression transposition
- Beginner key recommendation ranking
"""

import pytest
from backend.theory.transposition import (
    transpose_pitch_class,
    transpose_note_name,
    transpose_chord_symbol,
    transpose_progression,
    transpose_key_name,
    evaluate_key_transpositions,
)


class TestPhase9Transposition:
    """Test Suite for Phase 9 Transposition Engine."""

    def test_single_note_transposition(self):
        """Step 10: Single Note Transposition."""
        assert transpose_note_name("C", 2) == "D"
        assert transpose_note_name("C", 4) == "E"
        assert transpose_note_name("C", 7) == "G"
        assert transpose_note_name("F#", 1) == "G"
        assert transpose_note_name("Bb", 2) == "C"
        assert transpose_note_name("Ab", 2) == "Bb"

    def test_chord_symbol_transposition(self):
        """Step 10: Standard Chord Symbol Transposition."""
        cases = [
            # (Input, offset, expected)
            ("C", 2, "D"),
            ("Am", 2, "Bm"),
            ("F", 2, "G"),
            ("G", 2, "A"),
            ("Cmaj7", 2, "Dmaj7"),
            ("Am7", 2, "Bm7"),
            ("G7", 2, "A7"),
            ("Csus4", 2, "Dsus4"),
            ("Bdim", 1, "Cdim"),
            ("Caug", 2, "Daug"),
            ("C/E", 2, "D/F#"),
            ("G/B", 2, "A/C#"),
            ("D/F#", -2, "C/E"),
            ("C:maj7", 2, "D:maj7"),
            ("A:min7", 2, "B:min7"),
            ("D:min9/F#", 2, "E:min9/G#"),
            ("N", 2, "N"),
        ]
        for chord_in, offset, expected in cases:
            trans = transpose_chord_symbol(chord_in, offset)
            assert trans == expected, f"Failed transpose '{chord_in}' by {offset}: got '{trans}', expected '{expected}'"

    def test_progression_transposition_consistency(self):
        """Step 10: Global Progression Transposition."""
        prog = ["C", "G", "Am", "F"]
        trans_prog = transpose_progression(prog, 2)
        assert trans_prog == ["D", "A", "Bm", "G"]

        # Minor Pop Progression
        prog_minor = ["Am", "F", "C", "G"]
        trans_minor = transpose_progression(prog_minor, -2)
        assert trans_minor == ["Gm", "Eb", "Bb", "F"]

        # Progression with Dict structure
        dict_prog = [
            {"time": 0.0, "end": 2.0, "chord": "C/E", "raw_chord": "C:maj/3"},
            {"time": 2.0, "end": 4.0, "chord": "G/B", "raw_chord": "G:maj/3"},
        ]
        trans_dict = transpose_progression(dict_prog, 2)
        assert trans_dict[0]["chord"] == "D/F#"
        assert trans_dict[1]["chord"] == "A/C#"

    def test_beginner_key_recommendation_ranking(self):
        """Step 11: Beginner Key Recommendation Evaluation."""
        # A difficult black-key progression (E Major: C#m -> Abm -> A -> B)
        e_prog = ["C#m", "Abm", "A", "B"]
        rec = evaluate_key_transpositions(e_prog, current_key="E", current_scale="Major")
        assert rec["currentKey"] == "E"
        assert "recommendedKey" in rec
        assert "recommendedOffset" in rec
        assert len(rec["options"]) > 0

        # Transposing to C Major (offset -4) should lower difficulty
        top_opt = rec["options"][0]
        assert top_opt["averageDifficulty"] <= 0.40, "Recommended key should have low chord difficulty"

    def test_key_name_transposition(self):
        """Step 10: Key Label Transposition."""
        assert transpose_key_name("E Major", -4) == "C Major"
        assert transpose_key_name("C# Minor", -4) == "A Minor"
        assert transpose_key_name("Bb Major", 2) == "C Major"
