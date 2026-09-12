"""
tests/test_source_agreement.py

Unit tests for musical source agreement and bass slash-chord fusion:
- evaluate_chord_compatibility across roots, qualities, 7th extensions, and slash chords
- compute_source_agreement continuous score
- fuse_bass_evidence: Bass note detection, root reinforcement, and slash chord inversion (e.g. C/E)
"""

import numpy as np
import pytest
from backend.analysis.source_agreement import (
    evaluate_chord_compatibility,
    compute_source_agreement,
    fuse_bass_evidence,
    parse_chord_root_and_quality
)


def test_parse_chord_root_and_quality():
    """Verify parsing of standard triads, 7ths, and slash chords."""
    assert parse_chord_root_and_quality("C") == ("C", "", None)
    assert parse_chord_root_and_quality("Am7") == ("A", "m7", None)
    assert parse_chord_root_and_quality("F#m") == ("F#", "m", None)
    assert parse_chord_root_and_quality("Bbmaj7") == ("Bb", "maj7", None)
    assert parse_chord_root_and_quality("C/E") == ("C", "", "E")
    assert parse_chord_root_and_quality("N") == (None, "N", None)


def test_chord_compatibility():
    """Verify musical compatibility grading between chord symbols."""
    # Exact match
    assert evaluate_chord_compatibility("C", "C") == 1.0
    assert evaluate_chord_compatibility("Am", "Am") == 1.0
    assert evaluate_chord_compatibility("N", "N") == 1.0

    # Extension / Triad match
    assert evaluate_chord_compatibility("C", "C7") >= 0.85
    assert evaluate_chord_compatibility("Am", "Am7") >= 0.85

    # Slash chord / Inversion agreement
    assert evaluate_chord_compatibility("C/E", "E") >= 0.80

    # Dissonant / Unrelated clash
    assert evaluate_chord_compatibility("C", "F#") <= 0.10
    assert evaluate_chord_compatibility("C", "N") <= 0.20


def test_compute_source_agreement():
    """Verify cross-source agreement calculation over time."""
    # Source 1 & Source 2 agreeing perfectly on C -> G -> Am -> F
    seq1 = [
        {"time": 0.0, "end": 1.0, "chord": "C"},
        {"time": 1.0, "end": 2.0, "chord": "G"},
        {"time": 2.0, "end": 3.0, "chord": "Am"},
        {"time": 3.0, "end": 4.0, "chord": "F"},
    ]
    seq2 = [
        {"time": 0.0, "end": 1.0, "chord": "C"},
        {"time": 1.0, "end": 2.0, "chord": "G"},
        {"time": 2.0, "end": 3.0, "chord": "Am"},
        {"time": 3.0, "end": 4.0, "chord": "F"},
    ]

    agreement = compute_source_agreement({"mix": seq1, "other": seq2}, duration=4.0)
    assert agreement is not None
    assert agreement == 1.0

    # Disagreeing sequences
    seq_disagree = [
        {"time": 0.0, "end": 1.0, "chord": "F#"},
        {"time": 1.0, "end": 2.0, "chord": "C#"},
        {"time": 2.0, "end": 3.0, "chord": "D#m"},
        {"time": 3.0, "end": 4.0, "chord": "B"},
    ]
    disagree_score = compute_source_agreement({"mix": seq1, "other": seq_disagree}, duration=4.0)
    assert disagree_score is not None
    assert disagree_score < 0.20


def test_fuse_bass_evidence_slash_chord():
    """Verify fuse_bass_evidence transforms C major into C/E when bass sustains E."""
    chords = [
        {"time": 0.0, "end": 2.0, "chord": "C", "confidence": 0.90},
        {"time": 2.0, "end": 4.0, "chord": "G", "confidence": 0.90}
    ]
    
    # Bass playing E (pitch class 4) during the first 2 seconds, and G (pitch class 7) during the next 2s
    bass_chords = [
        {"time": 0.0, "end": 2.0, "chord": "Em", "confidence": 0.85},
        {"time": 2.0, "end": 4.0, "chord": "G", "confidence": 0.85}
    ]

    fused = fuse_bass_evidence(chords=chords, bass_chords=bass_chords)

    assert len(fused) == 2
    # C major with E in bass becomes C/E
    assert fused[0]["chord"] == "C/E"
    assert fused[0].get("inversion") is True
    # G major with G in bass retains G and reinforces root
    assert fused[1]["chord"] == "G"
    assert fused[1].get("root_reinforced") is True
