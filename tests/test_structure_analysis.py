"""
tests/test_structure_analysis.py

Comprehensive tests for Phase 4 Structure Analysis & Repeating Section Detection:
1. Repeating section detection (ABAB structure)
2. Non-repeating song (through-composed / unique sections)
3. Multi-cluster repeating sections (A B A B / A B C B)
4. Evidence-based non-fabricated labeling
5. Graceful fallback on empty/short audio
"""

import pytest
import numpy as np
import librosa

from backend.analysis.structure import (
    StructureAnalyzer,
    detect_structure,
    detect_structure_and_repeats,
)
from backend.models.analysis_types import StructureSection, StructureAnalysisResult, TimingData


class TestStructureAnalysis:

    def test_repeating_section_detection(self):
        """Verify that identical harmonic passages separated in time form repeating clusters."""
        sr = 22050
        hop = 512
        duration = 60.0  # 60s song: Section A (0-15s), Section B (15-30s), Section A (30-45s), Section B (45-60s)
        n_frames = int(duration * sr / hop)

        # Construct synthetic chroma with distinct harmonic profiles
        chroma = np.zeros((12, n_frames), dtype=np.float32)

        # Profile A: C major (C=0, E=4, G=7)
        prof_a = np.zeros(12, dtype=np.float32)
        prof_a[[0, 4, 7]] = 1.0

        # Profile B: F major (F=5, A=9, C=0)
        prof_b = np.zeros(12, dtype=np.float32)
        prof_b[[0, 5, 9]] = 1.0

        f_15 = int(15.0 * sr / hop)
        f_30 = int(30.0 * sr / hop)
        f_45 = int(45.0 * sr / hop)

        chroma[:, 0:f_15] = prof_a[:, None]
        chroma[:, f_15:f_30] = prof_b[:, None]
        chroma[:, f_30:f_45] = prof_a[:, None]
        chroma[:, f_45:n_frames] = prof_b[:, None]

        timing = TimingData(
            tempo=120.0,
            timeSignature="4/4",
            beatTimes=[i * 0.5 for i in range(120)],
            downbeatTimes=[0.0, 15.0, 30.0, 45.0, 60.0],
            beatConfidence=0.9
        )

        analyzer = StructureAnalyzer(min_section_duration=8.0, similarity_threshold=0.75)
        res = analyzer.analyze(chroma=chroma, sr=sr, hop_length=hop, duration=duration, timing_data=timing)

        assert isinstance(res, StructureAnalysisResult)
        assert res.total_sections >= 2
        assert res.has_repeating_patterns is True
        assert len(res.repeating_sections) >= 2
        assert res.structure_confidence >= 0.70

        # Verify repeating section labels
        labels = [s.label for s in res.repeating_sections]
        assert any("REPEATING" in l for l in labels)

    def test_non_repeating_song(self):
        """Verify that completely changing / through-composed harmony produces unique section labels."""
        sr = 22050
        hop = 512
        duration = 40.0
        n_frames = int(duration * sr / hop)

        # Each 10s segment has completely orthogonal pitch class profiles
        chroma = np.zeros((12, n_frames), dtype=np.float32)
        for i in range(4):
            f_start = int(i * 10.0 * sr / hop)
            f_end = int((i + 1) * 10.0 * sr / hop)
            pitch_idx = (i * 3) % 12
            chroma[pitch_idx : pitch_idx + 3, f_start:f_end] = 1.0

        analyzer = StructureAnalyzer(min_section_duration=6.0, similarity_threshold=0.85)
        res = analyzer.analyze(chroma=chroma, sr=sr, hop_length=hop, duration=duration)

        assert isinstance(res, StructureAnalysisResult)
        # All sections should be unique (no fabricated repeating groups)
        assert len(res.repeating_sections) == 0
        assert res.has_repeating_patterns is False

    def test_non_fabrication_of_semantic_labels(self):
        """Verify that no fake 'Chorus' or 'Verse' labels are fabricated."""
        sr = 22050
        hop = 512
        duration = 30.0
        n_frames = int(duration * sr / hop)

        chroma = np.ones((12, n_frames), dtype=np.float32) * 0.1

        analyzer = StructureAnalyzer()
        res = analyzer.analyze(chroma=chroma, sr=sr, hop_length=hop, duration=duration)

        for sec in res.sections:
            # Labels must be evidence-driven ('INTRO', 'OUTRO', 'SECTION_...', 'REPEATING_...')
            assert sec.label not in ("Chorus", "Verse", "Bridge", "Pre-Chorus")

    def test_empty_or_short_audio_fallback(self):
        """Verify graceful single-section fallback on zero or short duration."""
        analyzer = StructureAnalyzer()
        empty_chroma = np.zeros((12, 0), dtype=np.float32)

        res = analyzer.analyze(chroma=empty_chroma, sr=22050, hop_length=512, duration=0.0)
        assert isinstance(res, StructureAnalysisResult)
        assert res.total_sections == 1
        assert res.sections[0].label == "SECTION_1"
        assert res.has_repeating_patterns is False
        assert res.structure_confidence == 0.5
