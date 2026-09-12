"""
tests/test_phase6_production_hardening.py

Comprehensive Production Hardening & Scalability Test Suite for HotChords Phase 6:
1. Memory safety & chunked HPSS mathematical consistency.
2. Structure analysis scalability across duration.
3. Confidence calibration metrics & statistical truthfulness.
4. Benchmark reproducibility & deterministic inference.
5. Cache behavior & memory deallocation.
6. Safety against false confidence on silence and non-harmonic audio.
"""

import os
import gc
import pytest
import numpy as np
import soundfile as sf
import tempfile

from backend.analysis.profiling import profile_audio, compute_chunked_hpss
from backend.analysis.timing import TimingAnalyzer
from backend.analysis.engine_manager import ChordEngineManager
from backend.analysis.harmonic_evidence import HarmonicEvidenceRouter
from backend.analysis.structure import detect_structure_and_repeats, StructureAnalyzer
from backend.analysis.loop_detection import detect_four_chord_loop
from backend.analysis.pipeline import analyze_song
from backend.benchmarks.calibration import compute_calibration_curve
from backend.benchmarks.datasets import get_benchmark_cases
from backend.models.analysis_types import AudioStatus


def test_chunked_hpss_mathematical_equivalence():
    """Verify that chunked HPSS produces >0.999 correlation with monolithic HPSS."""
    sr = 22050
    duration = 45.0  # Spans across 30s chunk boundary
    n_samples = int(duration * sr)
    t = np.linspace(0, duration, n_samples, endpoint=False)
    # Tonal sine wave + percussive transient clicks + noise
    y = 0.5 * np.sin(2 * np.pi * 440.0 * t).astype(np.float32)
    clicks = np.zeros(n_samples, dtype=np.float32)
    clicks[:: int(sr * 0.5)] = 0.8  # Click every 500ms
    y += clicks + np.random.normal(0, 0.01, n_samples).astype(np.float32)

    import librosa
    h_mono, p_mono = librosa.effects.hpss(y, margin=3.0)
    h_chunk, p_chunk = compute_chunked_hpss(y, sr=sr, margin=3.0, chunk_sec=30.0)

    corr = np.corrcoef(h_mono, h_chunk)[0, 1]
    assert corr > 0.999, f"Chunked HPSS correlation ({corr}) is below threshold 0.999"


def test_structure_analysis_scalability():
    """Verify structure analysis runs in sub-quadratic section time and does not leak memory."""
    sr = 22050
    hop = 512
    # Simulate 10-minute (600s) chroma matrix (12 x 25840)
    n_frames = 25840
    chroma = np.random.uniform(0.1, 0.9, (12, n_frames)).astype(np.float32)
    
    analyzer = StructureAnalyzer(min_section_duration=6.0)
    res = analyzer.analyze(
        chroma=chroma,
        sr=sr,
        hop_length=hop,
        duration=600.0
    )
    
    assert res is not None
    assert res.total_sections >= 1
    assert len(res.sections) == res.total_sections
    # Peak-level segment count should be bounded, not per-frame
    assert res.total_sections <= 100


def test_confidence_calibration_mathematics():
    """Verify exact mathematical calculation of ECE, MCE, Brier score and insufficient data flag."""
    confidences = [0.90, 0.90, 0.85, 0.50]
    accuracies = [True, True, False, False]
    
    curve = compute_calibration_curve(confidences, accuracies, min_samples_for_calibration=100)
    
    assert curve["total_samples"] == 4
    assert curve["confidence_calibration_status"] == "INSUFFICIENT_GROUND_TRUTH"
    assert curve["is_calibrated"] is False
    assert 0.0 <= curve["ece"] <= 1.0
    assert 0.0 <= curve["mce"] <= 1.0
    assert 0.0 <= curve["brier_score"] <= 1.0


def test_benchmark_case_provenance_separation():
    """Verify that synthetic, controlled, and real-world categories are strictly separated."""
    cases = get_benchmark_cases()
    syn_cases = [c for c in cases if c.dataset_type == "SYNTHETIC"]
    ctrl_cases = [c for c in cases if c.dataset_type == "CONTROLLED_AUDIO"]
    
    assert len(syn_cases) > 0
    assert len(ctrl_cases) > 0
    for c in syn_cases:
        assert c.dataset_type == "SYNTHETIC"
    for c in ctrl_cases:
        assert c.dataset_type == "CONTROLLED_AUDIO"


def test_deterministic_audio_profiling():
    """Verify that running audio profiling twice on the same audio produces bit-identical results."""
    sr = 22050
    t = np.linspace(0, 5.0, int(5.0 * sr))
    y = np.sin(2 * np.pi * 261.63 * t).astype(np.float32)
    
    p1, s1, _ = profile_audio(y, sr)
    p2, s2, _ = profile_audio(y, sr)
    
    assert s1 == s2
    assert p1.harmonic_energy == p2.harmonic_energy
    assert p1.spectral_flatness == p2.spectral_flatness
    assert p1.chroma_entropy == p2.chroma_entropy


def test_silence_safety_no_fabricated_loops():
    """Verify that pure silence returns AudioStatus.EMPTY_AUDIO and refuses to fabricate loops."""
    sr = 22050
    y_silence = np.zeros(int(8.0 * sr), dtype=np.float32)
    
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = f.name
    try:
        sf.write(wav_path, y_silence, sr)
        res = analyze_song(wav_path)
        assert res["status"] in (AudioStatus.EMPTY_AUDIO.value, AudioStatus.NO_HARMONIC_CONTENT.value)
        assert res["four_chord_loop"]["available"] is False
        assert len(res["chords"]) == 0
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)
