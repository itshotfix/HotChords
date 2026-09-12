"""
tests/test_temporal_postprocessing.py

Tests for Temporal Post-Processing & Beat Alignment:
- Adjacent identical chord merging
- Short prediction spike suppression (< 0.15s)
- Musical beat grid snapping
- Full progression post-processing
"""

import pytest
from backend.analysis.temporal_postprocessing import (
    merge_adjacent_identical_chords,
    remove_short_spikes,
    snap_chord_boundaries_to_beats,
    postprocess_chord_progression
)
from backend.models.analysis_types import TimingData


class TestTemporalPostprocessing:

    def test_merge_adjacent_identical_chords(self):
        events = [
            {"time": 0.0, "end": 1.0, "chord": "C", "confidence": 0.9},
            {"time": 1.0, "end": 2.0, "chord": "C", "confidence": 0.9},
            {"time": 2.0, "end": 4.0, "chord": "G", "confidence": 0.8},
        ]
        merged = merge_adjacent_identical_chords(events)
        assert len(merged) == 2
        assert merged[0]["chord"] == "C"
        assert merged[0]["time"] == 0.0
        assert merged[0]["end"] == 2.0
        assert merged[1]["chord"] == "G"

    def test_remove_short_spikes(self):
        # A 0.05s glitch between C and G
        events = [
            {"time": 0.0, "end": 2.0, "chord": "C"},
            {"time": 2.0, "end": 2.05, "chord": "D#m"},  # glitch
            {"time": 2.05, "end": 4.0, "chord": "G"},
        ]
        cleaned = remove_short_spikes(events, min_duration=0.15)
        # Glitch should be absorbed
        assert len(cleaned) == 2
        assert cleaned[0]["chord"] == "C"
        assert cleaned[0]["end"] == 2.05
        assert cleaned[1]["chord"] == "G"

    def test_snap_chord_boundaries_to_beats(self):
        events = [
            {"time": 0.0, "end": 1.95, "chord": "C"},
            {"time": 1.95, "end": 4.0, "chord": "G"},
        ]
        beat_times = [0.0, 1.0, 2.0, 3.0, 4.0]
        snapped = snap_chord_boundaries_to_beats(events, beat_times, tolerance=0.18)

        # 1.95s is within 0.18s of 2.0s beat -> snaps to 2.0s
        assert snapped[0]["end"] == 2.0
        assert snapped[1]["time"] == 2.0

    def test_full_pipeline_postprocessing(self):
        events = [
            {"time": 0.0, "end": 0.98, "chord": "C", "confidence": 0.9},
            {"time": 0.98, "end": 1.96, "chord": "C", "confidence": 0.9},
            {"time": 1.96, "end": 2.02, "chord": "F#", "confidence": 0.4}, # spike
            {"time": 2.02, "end": 4.0, "chord": "Am", "confidence": 0.9},
        ]
        timing_data = TimingData(
            tempo=120.0,
            time_signature="4/4",
            beat_times=[0.0, 1.0, 2.0, 3.0, 4.0],
            beat_confidence=0.9
        )

        result = postprocess_chord_progression(events, timing_data=timing_data, min_duration=0.15)
        assert len(result) == 2
        assert result[0]["chord"] == "C"
        assert result[1]["chord"] == "Am"
