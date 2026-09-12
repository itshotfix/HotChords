"""
tests/test_phase7_real_song_validation.py

Comprehensive Phase 7 Automated Test Suite:
1. RealSongTrack data model, metadata provenance & ground-truth status.
2. Engine Disagreement Analysis (LV-Chordia vs Legacy CQT/Template).
3. Root vs Quality error classification & full 17-error taxonomy.
4. Beginner Simplification rules (preserving root, minor quality, slash chords).
5. Inversion / Bass Note separate dimensional evaluation.
6. Four-Chord Loop beginner playability ranking.
7. Critical source attribution truthfulness & non-harmonic safety.
"""

import os
import pytest
import numpy as np
import tempfile
import soundfile as sf

from backend.benchmarks.real_song_dataset import RealSongTrack, RealSongDatasetRegistry
from backend.benchmarks.real_song_validator import (
    evaluate_loop_beginner_playability,
    validate_real_song
)
from backend.benchmarks.metrics import (
    compare_engine_predictions,
    classify_real_song_error,
    root_matches,
    majmin_matches,
    full_chord_matches
)
from backend.theory.simplification import (
    reduce_chord_harmony,
    simplify_progression,
    evaluate_beginner_difficulty
)
from backend.models.timeline import ChordEvent
from backend.analysis.pipeline import analyze_song


def test_real_song_track_provenance_and_ground_truth_status():
    """Verify that tracks without ground truth are explicitly marked UNAVAILABLE."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = f.name
    
    sr = 22050
    y = np.sin(2 * np.pi * 440.0 * np.linspace(0, 2.0, int(2.0 * sr))).astype(np.float32)
    sf.write(wav_path, y, sr)

    try:
        track = RealSongTrack(
            track_id="test_local_user_song",
            filepath=wav_path,
            source="user_upload",
            license_provenance="Local Audio (Fair Use)",
            ground_truth=None
        )
        d = track.to_dict()
        assert d["track_id"] == "test_local_user_song"
        assert d["ground_truth_status"] == "UNAVAILABLE"
        assert d["has_ground_truth"] is False
        assert len(d["audio_hash"]) > 0
        assert d["duration"] == 2.0
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)


def test_engine_disagreement_analysis_categories():
    """Verify exact 4-way classification: AGREE, ROOT_AGREE_QUALITY_DISAGREE, ROOT_DISAGREE, NO_CHORD_DISAGREEMENT."""
    duration = 4.0
    # Engine A: C (0-1s), Am7 (1-2s), G (2-3s), N (3-4s)
    engine_a = [
        {"time": 0.0, "end": 1.0, "chord": "C"},
        {"time": 1.0, "end": 2.0, "chord": "Am7"},
        {"time": 2.0, "end": 3.0, "chord": "G"},
        {"time": 3.0, "end": 4.0, "chord": "N"}
    ]
    # Engine B: C (0-1s), A (1-2s: root agree, qual disagree), F (2-3s: root disagree), C (3-4s: no chord disagree)
    engine_b = [
        {"time": 0.0, "end": 1.0, "chord": "C"},
        {"time": 1.0, "end": 2.0, "chord": "A"},
        {"time": 2.0, "end": 3.0, "chord": "F"},
        {"time": 3.0, "end": 4.0, "chord": "C"}
    ]

    res = compare_engine_predictions(engine_a, engine_b, duration=duration, sample_rate_hz=10.0)
    pcts = res["category_percentages"]

    assert pcts["AGREE"] == 25.0  # 0-1s
    assert pcts["ROOT_AGREE_QUALITY_DISAGREE"] == 25.0  # 1-2s
    assert pcts["ROOT_DISAGREE"] == 25.0  # 2-3s
    assert pcts["NO_CHORD_DISAGREEMENT"] == 25.0  # 3-4s
    assert res["agreement_rate"] == 0.25
    assert res["root_agreement_rate"] == 0.50


def test_root_vs_quality_error_classification():
    """Verify distinct classification between WRONG_ROOT and CORRECT_ROOT_WRONG_QUALITY."""
    # Fundamental root error
    err1 = classify_real_song_error(ref_chord="Am7", est_chord="F#")
    assert err1 == "WRONG_ROOT"

    # Root correct, quality differing (acceptable for beginner piano simplification)
    err2 = classify_real_song_error(ref_chord="Am7", est_chord="Am")
    assert err2 == "NO_ERROR" or err2 == "CORRECT_ROOT_WRONG_QUALITY"

    # Root correct, major vs minor mismatch
    err3 = classify_real_song_error(ref_chord="Am7", est_chord="A")
    assert err3 == "WRONG_QUALITY"

    # Inversion bass mismatch
    err4 = classify_real_song_error(ref_chord="C/E", est_chord="C/G", ref_bass="E", est_bass="G")
    assert err4 == "WRONG_BASS"

    # No chord errors
    assert classify_real_song_error(ref_chord="N", est_chord="C") == "FALSE_CHORD"
    assert classify_real_song_error(ref_chord="C", est_chord="N") == "MISSED_CHORD"
    assert classify_real_song_error(ref_chord="N", est_chord="N") == "NO_ERROR"


def test_beginner_simplification_preservation_and_coverage():
    """
    Verify beginner simplification on all test qualities:
    maj, min, 7, maj7, min7, sus2, sus4, dim, aug, slash chords, add9, 9, 11, 13.
    Strictly verify that Am -> Am (NOT A) and Dm -> Dm (NOT D).
    """
    # 1. Major Family Extensions
    assert reduce_chord_harmony("Cmaj7") == "C"
    assert reduce_chord_harmony("C:maj7") == "C"
    assert reduce_chord_harmony("C7") == "C"
    assert reduce_chord_harmony("Cadd9") == "C"
    assert reduce_chord_harmony("C9") == "C"
    assert reduce_chord_harmony("C11") == "C"
    assert reduce_chord_harmony("C13") == "C"

    # 2. Minor Family (CRITICAL: Preserves minor quality!)
    assert reduce_chord_harmony("Am") == "Am"
    assert reduce_chord_harmony("Am7") == "Am"
    assert reduce_chord_harmony("A:min7") == "Am"
    assert reduce_chord_harmony("Dm9") == "Dm"
    assert reduce_chord_harmony("Em11") == "Em"
    assert reduce_chord_harmony("F#m7") == "F#m"
    # Never simplify minor to major!
    assert reduce_chord_harmony("Am") != "A"
    assert reduce_chord_harmony("Dm") != "D"

    # 3. Suspended Chords (Preserve suspension)
    assert reduce_chord_harmony("Gsus4") == "Gsus4"
    assert reduce_chord_harmony("Dsus2") == "Dsus2"

    # 4. Augmented & Diminished
    assert reduce_chord_harmony("Caug") == "C"
    assert "dim" in reduce_chord_harmony("Bdim") or reduce_chord_harmony("Bdim") == "Bm"

    # 5. Slash Chords / Inversions
    assert reduce_chord_harmony("C/E") == "C"
    assert reduce_chord_harmony("G/B") == "G"
    assert reduce_chord_harmony("Dmin9/F#") == "Dm"
    assert reduce_chord_harmony("F/A") == "F"


def test_beginner_playability_ranking():
    """Verify playability scoring favors accessible triads over complex clusters."""
    easy_loop = ["C", "G", "Am", "F"]
    mod_loop = ["D", "A", "Bm", "G"]
    hard_loop = ["Abm", "Ebm", "Bdim", "F#"]

    score_easy = evaluate_loop_beginner_playability(easy_loop)
    score_mod = evaluate_loop_beginner_playability(mod_loop)
    score_hard = evaluate_loop_beginner_playability(hard_loop)

    assert score_easy > score_mod > score_hard
    assert score_easy >= 0.90
    assert score_hard < 0.60


def test_critical_source_attribution_rule():
    """Verify that pipeline source attribution does not falsely claim isolated instrument without evidence."""
    sr = 22050
    t = np.linspace(0, 4.0, int(4.0 * sr))
    # Simple synthetic mix
    y = (0.5 * np.sin(2 * np.pi * 261.63 * t) + 0.5 * np.sin(2 * np.pi * 329.63 * t)).astype(np.float32)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = f.name
    sf.write(wav_path, y, sr)

    try:
        res = analyze_song(wav_path)
        chord_source = res.get("chord_source")
        # Must be mixed, hpss, or original mix, NEVER a fabricated isolated instrument like 'guitar'
        assert chord_source in ["mix", "harmonic_hpss", "other", "ORIGINAL_MIX", "MIXED_HARMONIC_EVIDENCE"]
        assert res["ready"] is True
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)
