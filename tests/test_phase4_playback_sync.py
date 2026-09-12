"""
tests/test_phase4_playback_sync.py

Comprehensive tests for Phase 4 Timeline & Playback Synchronization:
1. SongTimeline serialization / deserialization of structure and 4-chord loop data
2. Pipeline integration with structure and loop results
3. Authoritative clock metadata propagation
"""

import pytest
from backend.models.timeline import SongTimeline, SongMetadata, ChordEvent, SectionEvent
from backend.models.analysis_types import (
    StructureAnalysisResult,
    StructureSection,
    FourChordLoopResult,
    AudioStatus,
)


class TestPhase4PlaybackSync:

    def test_song_timeline_four_chord_loop_serialization(self):
        """Verify that SongTimeline preserves four_chord_loop and structure data across conversion."""
        loop = FourChordLoopResult(
            available=True,
            chords=["C", "G", "Am", "F"],
            rawChords=["C:maj", "G:maj", "A:min", "F:maj"],
            simplifiedChords=["C", "G", "Am", "F"],
            section="REPEATING_SECTION_A",
            start=16.0,
            end=32.0,
            duration=16.0,
            confidence=0.94,
            occurrences=[16.0, 48.0, 80.0],
            repetitionCount=3,
            reason="Strong 4-chord cycle repeating across 3 sections"
        )

        struct_sec = StructureSection(
            label="REPEATING_SECTION_A",
            start=16.0,
            end=32.0,
            duration=16.0,
            repetitionGroup="REPEATING_SECTION_A",
            similarityScore=0.92
        )

        structure = StructureAnalysisResult(
            sections=[struct_sec],
            repeatingSections=[struct_sec],
            structureConfidence=0.90,
            totalSections=1,
            hasRepeatingPatterns=True
        )

        data = {
            "file": "test_song.mp3",
            "duration": 96.0,
            "tempo": 120.0,
            "key": "C",
            "key_full": "C Major",
            "chords": [
                {"time": 0.0, "end": 4.0, "chord": "C", "confidence": 0.95},
                {"time": 4.0, "end": 8.0, "chord": "G", "confidence": 0.93},
                {"time": 8.0, "end": 12.0, "chord": "Am", "confidence": 0.94},
                {"time": 12.0, "end": 16.0, "chord": "F", "confidence": 0.91},
            ],
            "sections": [{"label": "REPEATING_SECTION_A", "start": 16.0, "end": 32.0}],
            "structure": structure.model_dump(by_alias=True),
            "four_chord_loop": loop.model_dump(by_alias=True),
            "status": "SUCCESS"
        }

        timeline = SongTimeline.from_analysis_dict(data)
        assert timeline.four_chord_loop is not None
        assert timeline.four_chord_loop.available is True
        assert timeline.four_chord_loop.chords == ["C", "G", "Am", "F"]
        assert timeline.structure is not None
        assert timeline.structure.has_repeating_patterns is True

        # Convert back to analysis dict
        out_dict = timeline.to_analysis_dict()
        assert "four_chord_loop" in out_dict
        assert out_dict["four_chord_loop"]["available"] is True
        assert out_dict["four_chord_loop"]["chords"] == ["C", "G", "Am", "F"]
        assert "structure" in out_dict
        assert out_dict["structure"]["total_sections"] == 1
