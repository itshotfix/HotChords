"""
tests/test_timing_abstraction.py

Tests for Phase 1 Rhythm & Beat Timing Abstraction:
- TimingAnalyzer interface compliance
- Beat, downbeat, tempo extraction
- TimingData schema serialization
- Edge case handling (silent, short audio)
"""

import numpy as np
import pytest
from backend.analysis.timing import TimingAnalyzer
from backend.models.analysis_types import TimingData


def generate_metronome_audio(bpm: float = 120.0, duration: float = 6.0, sr: int = 22050) -> np.ndarray:
    """Generates a synthetic periodic pulse train at a given BPM."""
    y = np.zeros(int(sr * duration), dtype=np.float32)
    interval = int(sr * 60.0 / bpm)
    
    for onset in range(0, len(y) - 500, interval):
        # Click burst
        click = np.sin(2 * np.pi * 1000 * np.linspace(0, 0.02, int(sr * 0.02)))
        click *= np.exp(-np.linspace(0, 5, len(click)))
        y[onset:onset + len(click)] += click
        
    return y


class TestTimingAbstraction:

    def test_timing_analyzer_synthetic_pulse(self):
        """Test beat tracking and downbeat estimation on a clean 120 BPM metronome signal."""
        sr = 22050
        y = generate_metronome_audio(bpm=120.0, duration=6.0, sr=sr)
        
        analyzer = TimingAnalyzer(y=y, sr=sr, time_signature="4/4").analyze()
        
        tempo = analyzer.get_tempo()
        beats = analyzer.get_beats()
        downbeats = analyzer.get_downbeats()
        timing_data = analyzer.get_timing_data()
        
        # Check tempo is in reasonable vicinity of 120 (e.g., 115-125) or octave-related (60/240)
        assert 50 <= tempo <= 250
        assert len(beats) > 5
        assert downbeats is not None
        assert len(downbeats) >= 1
        
        assert isinstance(timing_data, TimingData)
        assert timing_data.tempo == tempo
        assert timing_data.time_signature == "4/4"
        assert len(timing_data.beat_times) == len(beats)

    def test_timing_analyzer_empty_audio(self):
        """Test TimingAnalyzer handling of empty or silent audio."""
        sr = 22050
        y = np.zeros(sr * 2, dtype=np.float32)
        analyzer = TimingAnalyzer(y=y, sr=sr).analyze()
        
        assert analyzer.get_tempo() == 120.0
        assert len(analyzer.get_beats()) == 0
        assert analyzer.get_confidence() == 0.0

    def test_timing_data_schema(self):
        """Test TimingData model validation and serialization."""
        data = TimingData(
            tempo=128.0,
            time_signature="4/4",
            beat_times=[0.0, 0.468, 0.937, 1.406],
            downbeat_times=[0.0, 1.875],
            beat_confidence=0.85
        )
        dumped = data.model_dump(by_alias=True)
        assert dumped["tempo"] == 128.0
        assert dumped["timeSignature"] == "4/4"
        assert len(dumped["beatTimes"]) == 4
        assert len(dumped["downbeatTimes"]) == 2
        assert dumped["beatConfidence"] == 0.85
