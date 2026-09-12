"""
tests/test_phase8_piano_voicing.py

Comprehensive Test Suite for Phase 8 Production Piano Voicing & Voice-Leading Engine.
Verifies:
- Standard triads & qualities (C, Cm, C7, Cmaj7, Cm7, Csus2, Csus4, Cdim, Caug)
- Slash chords & bass notes (C/E, G/B, D/F#, D/E)
- Voice-leading continuity across progressions (C-G-Am-F, Am-F-C-G, Dm-Bb-F-C, C-G-C-F, Cmaj7-Am7-Dm7-G7)
- Range constraints (LH: MIDI 36-55, RH: MIDI 55-79)
- Hand assignment ergonomics (LH bass anchor, RH triad/voicing)
- Difficulty scoring calibration
- Cyclic 4-chord loop voice-leading wrap
"""

import pytest
from backend.theory.piano_voicing import (
    parse_chord_components,
    generate_candidate_rh_voicings,
    score_voice_leading,
    generate_lh_voicing,
    calculate_chord_difficulty_score,
    voice_chord,
    voice_chord_progression,
    voice_four_chord_loop,
    evaluate_loop_beginner_playability,
    LH_MIN_MIDI, LH_MAX_MIDI,
    RH_MIN_MIDI, RH_MAX_MIDI
)


class TestPhase8PianoVoicing:
    """Test Suite for Phase 8 Piano Voicings."""

    def test_component_parsing_and_quality_preservation(self):
        """Step 2: Canonical Chord Representation & Component Extraction."""
        cases = [
            ("C", "C", "maj", None),
            ("Cm", "C", "min", None),
            ("C7", "C", "7", None),
            ("Cmaj7", "C", "maj7", None),
            ("Cm7", "C", "min7", None),
            ("Csus2", "C", "sus2", None),
            ("Csus4", "C", "sus4", None),
            ("Cdim", "C", "dim", None),
            ("Caug", "C", "aug", None),
            ("C/E", "C", "maj", "E"),
            ("G/B", "G", "maj", "B"),
            ("D/F#", "D", "maj", "F#"),
            ("D:min9/F#", "D", "min9", "F#"),
            ("A:min7", "A", "min7", None),
            ("N", None, "N", None),
        ]
        for chord_str, expected_root, expected_qual, expected_bass in cases:
            root, qual, bass = parse_chord_components(chord_str)
            assert root == expected_root, f"Failed root for {chord_str}: got {root}, expected {expected_root}"
            assert qual == expected_qual, f"Failed quality for {chord_str}: got {qual}, expected {expected_qual}"
            assert bass == expected_bass, f"Failed bass for {chord_str}: got {bass}, expected {expected_bass}"

    def test_individual_chord_voicings_and_ranges(self):
        """Step 6 & 7: Voicing Generation within Register Bounds."""
        chords_to_test = [
            "C", "Cm", "C7", "Cmaj7", "Cm7", "Csus2", "Csus4", "Cdim", "Caug",
            "C/E", "G/B", "D/F#", "Abm", "F#m7", "Ebmaj7"
        ]
        for chord_name in chords_to_test:
            v = voice_chord(chord_name, beginner_mode=True)
            assert "leftHand" in v and len(v["leftHand"]) >= 1, f"Missing LH for {chord_name}"
            assert "rightHand" in v and len(v["rightHand"]) >= 1, f"Missing RH for {chord_name}"
            
            # Verify LH within bass bounds
            for lh_note in v["leftHand"]:
                assert LH_MIN_MIDI <= lh_note["midi"] <= LH_MAX_MIDI, (
                    f"LH note {lh_note['midi']} out of bounds [{LH_MIN_MIDI}, {LH_MAX_MIDI}] for {chord_name}"
                )
                assert lh_note["finger"] in (1, 2, 3, 4, 5)
                assert lh_note["color"] is not None

            # Verify RH within treble bounds
            for rh_note in v["rightHand"]:
                assert RH_MIN_MIDI <= rh_note["midi"] <= RH_MAX_MIDI, (
                    f"RH note {rh_note['midi']} out of bounds [{RH_MIN_MIDI}, {RH_MAX_MIDI}] for {chord_name}"
                )
                assert rh_note["finger"] in (1, 2, 3, 4, 5)
                assert rh_note["color"] is not None

    def test_slash_chord_bass_assignment(self):
        """Step 9: Hand Assignment for Slash Chords (Bass Note in LH)."""
        # C/E should place E in the Left Hand and C major triad in Right Hand
        v_ce = voice_chord("C/E")
        assert len(v_ce["leftHand"]) == 1
        assert v_ce["leftHand"][0]["note"].startswith("E")
        rh_notes = [n["note"][0] for n in v_ce["rightHand"]]
        assert set(rh_notes) == {"C", "E", "G"}

        # G/B should place B in LH
        v_gb = voice_chord("G/B")
        assert v_gb["leftHand"][0]["note"].startswith("B")
        rh_notes_gb = [n["note"][0] for n in v_gb["rightHand"]]
        assert set(rh_notes_gb) == {"G", "B", "D"}

    def test_voice_leading_progression_smoothness(self):
        """Step 8: Voice-Leading Minimizes Movement Across Progressions."""
        progressions = [
            ["C", "G", "Am", "F"],
            ["Am", "F", "C", "G"],
            ["Dm", "Bb", "F", "C"],
            ["C", "G", "C", "F"],
            ["Cmaj7", "Am7", "Dm7", "G7"],
        ]
        for prog in progressions:
            voicings = voice_chord_progression(prog, beginner_mode=True)
            assert len(voicings) == len(prog)

            # Evaluate max jump between consecutive RH average pitches
            for i in range(len(voicings) - 1):
                rh_curr = [n["midi"] for n in voicings[i]["rightHand"]]
                rh_next = [n["midi"] for n in voicings[i + 1]["rightHand"]]
                avg_curr = sum(rh_curr) / len(rh_curr)
                avg_next = sum(rh_next) / len(rh_next)
                jump = abs(avg_next - avg_curr)
                # Smooth voice leading should maintain avg jump <= 7 semitones
                assert jump <= 7.0, f"Excessive voice leading jump ({jump} semitones) between {prog[i]} and {prog[i+1]}"

    def test_cyclic_four_chord_loop_voice_leading(self):
        """Step 11: 4-Chord Loop Cyclical Continuity."""
        loop = ["C", "G", "Am", "F"]
        voicings = voice_four_chord_loop(loop)
        assert len(voicings) == 4

        # Verify chord 4 -> chord 1 loop transition is also voice-led
        rh_4 = [n["midi"] for n in voicings[3]["rightHand"]]
        rh_1 = [n["midi"] for n in voicings[0]["rightHand"]]
        avg_4 = sum(rh_4) / len(rh_4)
        avg_1 = sum(rh_1) / len(rh_1)
        wrap_jump = abs(avg_1 - avg_4)
        assert wrap_jump <= 7.0, f"Loop wrap jump {wrap_jump} too large between chord 4 and chord 1"

    def test_playability_scoring_accuracy(self):
        """Step 10: Playability Scoring Formula."""
        # Simple pop progression should have high playability
        score_easy = evaluate_loop_beginner_playability(["C", "G", "Am", "F"])
        assert score_easy >= 0.85, f"Expected high playability for C-G-Am-F, got {score_easy}"

        # Difficult cluster with altered/diminished chords should have lower score
        score_diff = evaluate_loop_beginner_playability(["C#m", "Abm", "F#dim", "Baug"])
        assert score_diff < 0.60, f"Expected lower playability for altered chords, got {score_diff}"
