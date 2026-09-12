"""
tests/test_chord_normalization.py

Tests for Chord Normalization & Harte Syntax Parsing:
- Major, minor, dominant 7th, major 7th, minor 7th
- Suspended, diminished, augmented, 6th chords
- Slash and inversion chords (e.g. C:maj/3 -> C/E)
- Explicit NO_CHORD ('N') preservation
- Simplified triad generation for beginner pedagogy
"""

import pytest
from backend.theory.normalization import parse_harte_chord, normalize_chord_sequence
from backend.theory.theory import chord_note_indices, get_chord_notes_musician, chord_difficulty, chord_roman


class TestChordNormalization:

    def test_major_triad(self):
        parsed = parse_harte_chord("C:maj")
        assert parsed.root == "C"
        assert parsed.display_symbol == "C"
        assert parsed.simplified_triad == "C"
        assert parsed.is_no_chord is False
        assert chord_note_indices("C") == [0, 4, 7]

    def test_minor_triad(self):
        parsed = parse_harte_chord("A:min")
        assert parsed.root == "A"
        assert parsed.display_symbol == "Am"
        assert parsed.simplified_triad == "Am"
        assert parsed.is_no_chord is False
        assert chord_note_indices("Am") == [9, 0, 4]

    def test_dominant_seventh(self):
        parsed = parse_harte_chord("G:7")
        assert parsed.root == "G"
        assert parsed.display_symbol == "G7"
        assert parsed.simplified_triad == "G"
        assert chord_note_indices("G7") == [7, 11, 2, 5]

    def test_major_seventh(self):
        parsed = parse_harte_chord("C:maj7")
        assert parsed.root == "C"
        assert parsed.display_symbol == "Cmaj7"
        assert parsed.simplified_triad == "C"
        assert chord_note_indices("Cmaj7") == [0, 4, 7, 11]

    def test_minor_seventh(self):
        parsed = parse_harte_chord("D:min7")
        assert parsed.root == "D"
        assert parsed.display_symbol == "Dm7"
        assert parsed.simplified_triad == "Dm"
        assert chord_note_indices("Dm7") == [2, 5, 9, 0]

    def test_suspended_chords(self):
        sus4 = parse_harte_chord("D:sus4")
        assert sus4.display_symbol == "Dsus4"
        assert sus4.simplified_triad == "D"
        assert chord_note_indices("Dsus4") == [2, 7, 9]

        sus2 = parse_harte_chord("A:sus2")
        assert sus2.display_symbol == "Asus2"
        assert sus2.simplified_triad == "A"
        assert chord_note_indices("Asus2") == [9, 11, 4]

    def test_diminished_and_augmented(self):
        dim = parse_harte_chord("B:dim")
        assert dim.display_symbol == "Bdim"
        assert dim.simplified_triad == "Bdim"
        assert chord_note_indices("Bdim") == [11, 2, 5]

        aug = parse_harte_chord("C:aug")
        assert aug.display_symbol == "Caug"
        assert aug.simplified_triad == "Caug"
        assert chord_note_indices("Caug") == [0, 4, 8]

    def test_slash_inversion_chords(self):
        # C/E (3rd inversion of C major)
        slash = parse_harte_chord("C:maj/3")
        assert slash.root == "C"
        assert slash.bass in ["E", "Fb"]
        assert slash.display_symbol in ["C/E", "C/Fb"]
        assert slash.simplified_triad == "C"
        
        # Check notes include E and C
        notes = chord_note_indices("C/E")
        assert 4 in notes and 0 in notes and 7 in notes
        assert notes[0] == 4  # Bass note in bass position

    def test_no_chord_handling(self):
        for token in ["N", "X", "", "no_chord"]:
            parsed = parse_harte_chord(token)
            assert parsed.is_no_chord is True
            assert parsed.display_symbol == "N"
            assert parsed.simplified_triad == "N"

    def test_normalize_sequence(self):
        raw_seq = [
            {"start_time": 0.0, "end_time": 2.0, "chord": "C:maj"},
            {"start_time": 2.0, "end_time": 4.0, "chord": "A:min7"},
            {"start_time": 4.0, "end_time": 6.0, "chord": "N"},
        ]
        norm = normalize_chord_sequence(raw_seq)
        assert len(norm) == 3
        assert norm[0]["chord"] == "C"
        assert norm[1]["chord"] == "Am7"
        assert norm[1]["simplified"] == "Am"
        assert norm[2]["chord"] == "N"
        assert norm[2]["is_no_chord"] is True
