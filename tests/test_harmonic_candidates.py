"""
tests/test_harmonic_candidates.py

Unit tests for HarmonicEvidenceRouter candidate registration, transparent scoring, and filtering:
- Dynamic candidate source registration (mix, harmonic_hpss, other, bass, vocals, drums)
- Objective metrics calculation (harmonic energy, chroma strength, chroma entropy, spectral flatness, temporal stability)
- Candidate filtering (drums and vocals exclusion, noisy signal rejection)
- Inspectability of scoring components
"""

import numpy as np
import pytest
from backend.analysis.harmonic_evidence import HarmonicEvidenceRouter


@pytest.fixture
def synthetic_piano_c_major():
    """Generates 3 seconds of rich synthetic C major piano chord."""
    sr = 22050
    duration = 3.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    env = np.exp(-1.2 * (t % 1.0))
    y = np.zeros_like(t)
    # C4, E4, G4 with overtones
    for f0 in [261.63, 329.63, 392.00]:
        for h, w in [(1, 1.0), (2, 0.5), (3, 0.3), (4, 0.15)]:
            y += w * np.sin(2 * np.pi * f0 * h * t)
    return (y * env / np.max(np.abs(y)) * 0.7).astype(np.float32), sr


@pytest.fixture
def synthetic_percussion_noise():
    """Generates 3 seconds of transient percussive clicks and noise."""
    sr = 22050
    duration = 3.0
    y = np.zeros(int(sr * duration), dtype=np.float32)
    # Clicks every 0.5s
    for beat in range(6):
        idx = int(beat * 0.5 * sr)
        if idx < len(y):
            y[idx:idx+500] = np.random.uniform(-0.8, 0.8, min(500, len(y)-idx))
    return y, sr


def test_harmonic_candidate_evidence_scoring(synthetic_piano_c_major, synthetic_percussion_noise):
    """Verify objective evidence metrics across candidate sources."""
    y_piano, sr = synthetic_piano_c_major
    y_perc, _ = synthetic_percussion_noise

    router = HarmonicEvidenceRouter(sr=sr)
    router.register_source("piano", y_piano)
    router.register_source("drums", y_perc)

    evidence = router.extract_evidence()

    assert "piano" in evidence
    assert "drums" in evidence

    piano_ev = evidence["piano"]
    drums_ev = evidence["drums"]

    # Piano candidate should exhibit high harmonic energy and low flatness
    assert piano_ev.is_available is True
    assert piano_ev.harmonic_energy is not None and piano_ev.harmonic_energy > 0.50
    assert piano_ev.chroma_strength is not None and piano_ev.chroma_strength > 0.10
    assert piano_ev.spectral_flatness is not None and piano_ev.spectral_flatness < 0.20
    assert piano_ev.composite_score is not None and piano_ev.composite_score > 0.40
    assert piano_ev.rejection_reason is None

    # Drums candidate should be filtered / excluded
    assert drums_ev.is_available is True
    assert drums_ev.rejection_reason is not None
    assert "Excluded" in drums_ev.rejection_reason or "drums" in drums_ev.rejection_reason


def test_candidate_filtering_strategy(synthetic_piano_c_major, synthetic_percussion_noise):
    """Verify filter_promising_candidates selects harmonic candidates and rejects non-harmonic/stems."""
    y_piano, sr = synthetic_piano_c_major
    y_perc, _ = synthetic_percussion_noise

    router = HarmonicEvidenceRouter(sr=sr)
    router.register_source("mix", y_piano)
    router.register_source("other", y_piano)
    router.register_source("vocals", y_piano)
    router.register_source("drums", y_perc)

    router.extract_evidence()
    qualified = router.filter_promising_candidates()

    assert "other" in qualified or "mix" in qualified
    assert "drums" not in qualified
    assert "vocals" not in qualified
