"""
tests/test_evidence_and_reliability.py

Tests for Phase 1 Harmonic Evidence, Instrument Evidence, and Detection Reliability:
- HarmonicEvidenceRouter candidate registration & metric calculation
- Instrument evidence non-fabrication guarantee
- DetectionReliability multi-dimensional evaluation
- Temporal stability evaluation
"""

import numpy as np
import pytest
from backend.analysis.harmonic_evidence import HarmonicEvidenceRouter
from backend.analysis.instrument_evidence import build_unclassified_instrument_registry, STANDARD_INSTRUMENT_TARGETS
from backend.analysis.confidence import evaluate_detection_reliability, evaluate_temporal_stability
from backend.models.analysis_types import AudioProfile, DetectionReliability


class TestEvidenceAndReliability:

    def test_harmonic_evidence_router_candidates(self):
        """Test candidate evidence extraction and unavailable candidate marking."""
        sr = 22050
        t = np.linspace(0, 2.0, int(sr * 2.0), endpoint=False)
        # Synthetic harmonic signal
        y_mix = 0.5 * (np.sin(2 * np.pi * 440 * t) + np.sin(2 * np.pi * 554.37 * t))
        y_harm = y_mix * 0.9

        router = HarmonicEvidenceRouter(sr=sr)
        router.register_source("mix", y_mix)
        router.register_source("harmonic_hpss", y_harm)

        evidence = router.extract_evidence()

        assert "mix" in evidence
        assert evidence["mix"].is_available is True
        assert evidence["mix"].harmonic_energy is not None
        assert evidence["mix"].harmonic_energy > 0.5

        assert "harmonic_hpss" in evidence
        assert evidence["harmonic_hpss"].is_available is True

        # Unregistered stems must be explicitly unavailable
        assert "guitar" in evidence
        assert evidence["guitar"].is_available is False
        assert evidence["guitar"].harmonic_energy is None

        assert "piano" in evidence
        assert evidence["piano"].is_available is False

    def test_instrument_evidence_no_fabrication(self):
        """Strictly verify that unclassified instruments are marked unavailable with no fake confidence."""
        registry = build_unclassified_instrument_registry()

        assert len(registry) == len(STANDARD_INSTRUMENT_TARGETS)
        for inst_name, evidence in registry.items():
            assert evidence.instrument == inst_name
            assert evidence.confidence is None
            assert evidence.is_available is False
            assert evidence.source is None

    def test_temporal_stability_stable_vs_erratic(self):
        """Verify temporal stability scores stable chord progressions higher than rapid 1-beat jitter."""
        stable_chords = [
            {"time": 0.0, "end": 2.0, "chord": "C"},
            {"time": 2.0, "end": 4.0, "chord": "G"},
            {"time": 4.0, "end": 6.0, "chord": "Am"},
            {"time": 6.0, "end": 8.0, "chord": "F"},
        ]
        
        # Erratic jitter changing on every single step
        erratic_chords = [
            {"time": i * 0.5, "end": (i + 1) * 0.5, "chord": f"C_{i}"}
            for i in range(16)
        ]

        stable_score = evaluate_temporal_stability(stable_chords)
        erratic_score = evaluate_temporal_stability(erratic_chords)

        assert stable_score > 0.8
        assert erratic_score < 0.5
        assert stable_score > erratic_score

    def test_detection_reliability_structure(self):
        """Verify DetectionReliability schema and component values."""
        profile = AudioProfile(
            duration=3.0,
            sample_rate=22050,
            channels=1,
            rms=0.25,
            silence_ratio=0.0,
            clipping_ratio=0.0,
            harmonic_energy=0.85,
            pitch_activity=0.90,
            spectral_flatness=0.10,
            chroma_strength=0.75,
            chroma_entropy=0.20,
            beat_confidence=0.80
        )
        chords = [
            {"time": 0.0, "end": 2.0, "chord": "C"},
            {"time": 2.0, "end": 4.0, "chord": "G"},
        ]

        reliability = evaluate_detection_reliability(profile, chords, beat_confidence=0.80)

        assert isinstance(reliability, DetectionReliability)
        assert reliability.overall is not None and 0.0 <= reliability.overall <= 1.0
        assert reliability.harmonic_strength is not None and reliability.harmonic_strength > 0.6
        assert reliability.temporal_stability is not None
        assert reliability.beat_alignment == 0.80
        # Multi-engine and multi-source agreement must remain None in Phase 1
        assert reliability.source_agreement is None
        assert reliability.engine_agreement is None
