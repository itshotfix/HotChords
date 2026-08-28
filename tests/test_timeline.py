"""
tests/test_timeline.py
Unit tests for canonical SongTimeline and ChordEvent data models and conversion adapters.
"""

import unittest
from backend.models import (
    SongTimeline,
    ChordEvent,
    SongMetadata,
    SectionEvent,
    HandVoicing,
    NotationData,
    analysis_to_song_timeline,
)



class TestSongTimeline(unittest.TestCase):

    def setUp(self):
        self.sample_analysis = {
            "file": "test_track.mp3",
            "duration": 150.75,
            "tempo": 124.0,
            "time_sig": "4/4",
            "key": "C",
            "scale": "Major",
            "key_full": "C Major",
            "scale_notes": [0, 2, 4, 5, 7, 9, 11],
            "chords": [
                {
                    "time": 0.0,
                    "end": 2.0,
                    "chord": "C",
                    "raw_chord": "C",
                    "confidence": 0.95,
                },
                {
                    "time": 2.0,
                    "end": 4.0,
                    "chord": "G",
                    "raw_chord": "G",
                    "confidence": 0.92,
                },
                {
                    "time": 4.0,
                    "end": 6.0,
                    "chord": "Am",
                    "raw_chord": "Am",
                    "confidence": 0.89,
                },
                {
                    "time": 6.0,
                    "end": 8.0,
                    "chord": "F",
                    "raw_chord": "F",
                    "confidence": 0.91,
                },
            ],
            "unique_chords": ["C", "G", "Am", "F"],
            "chord_data": {
                "C": {
                    "notes": [0, 4, 7],
                    "note_names": ["C", "E", "G"],
                    "fingers": {0: 1, 4: 3, 7: 5},
                    "difficulty": "easy",
                },
                "G": {
                    "notes": [7, 11, 2],
                    "note_names": ["G", "B", "D"],
                    "fingers": {7: 1, 11: 3, 2: 5},
                    "difficulty": "easy",
                },
                "Am": {
                    "notes": [9, 0, 4],
                    "note_names": ["A", "C", "E"],
                    "fingers": {9: 1, 0: 3, 4: 5},
                    "difficulty": "medium",
                },
                "F": {
                    "notes": [5, 9, 0],
                    "note_names": ["F", "A", "C"],
                    "fingers": {5: 1, 9: 3, 0: 5},
                    "difficulty": "medium",
                },
            },
            "roman_numerals": {"C": "I", "G": "V", "Am": "vi", "F": "IV"},
            "beginner_chords": [
                {
                    "time": 0.0,
                    "end": 4.0,
                    "chord": "C",
                    "raw_chord": "C",
                    "confidence": 0.95,
                },
                {
                    "time": 4.0,
                    "end": 8.0,
                    "chord": "Am",
                    "raw_chord": "Am",
                    "confidence": 0.89,
                },
            ],
            "unique_beginner_chords": ["C", "Am"],
            "easy_key": "C",
            "easy_key_full": "C Major",
            "transpose_offset": 0,
            "sections": [
                {"label": "Intro", "start": 0.0, "end": 4.0},
                {"label": "Verse", "start": 4.0, "end": 8.0},
            ],
        }

    def test_1_create_from_valid_analysis_data(self):
        """1. SongTimeline can be created from valid analysis data."""
        timeline = SongTimeline.from_analysis_dict(self.sample_analysis)
        self.assertIsInstance(timeline, SongTimeline)
        self.assertEqual(timeline.duration, 150.75)
        self.assertEqual(timeline.metadata.file, "test_track.mp3")
        self.assertEqual(timeline.metadata.tempo, 124.0)
        self.assertEqual(timeline.metadata.key, "C")
        self.assertEqual(timeline.metadata.scale, "Major")
        self.assertEqual(timeline.metadata.key_full, "C Major")
        self.assertEqual(timeline.metadata.time_sig, "4/4")
        self.assertEqual(len(timeline.original_chords), 4)

    def test_2_chord_event_preserves_required_fields(self):
        """2. ChordEvent preserves startTime, endTime, and chordName."""
        event = ChordEvent(
            startTime=1.25,
            endTime=3.5,
            chordName="Dm7",
            notes=[2, 5, 9, 0],
            confidence=0.88,
        )
        self.assertEqual(event.start_time, 1.25)
        self.assertEqual(event.end_time, 3.5)
        self.assertEqual(event.chord_name, "Dm7")
        self.assertEqual(event.notes, [2, 5, 9, 0])
        self.assertEqual(event.confidence, 0.88)

        # Also test model_dump aliases
        dumped = event.model_dump(by_alias=True)
        self.assertEqual(dumped["startTime"], 1.25)
        self.assertEqual(dumped["endTime"], 3.5)
        self.assertEqual(dumped["chordName"], "Dm7")

    def test_3_timelines_remain_separate(self):
        """3. Original and beginner chord timelines remain separate."""
        timeline = SongTimeline.from_analysis_dict(self.sample_analysis)
        self.assertIsNotNone(timeline.original_chords)
        self.assertIsNotNone(timeline.beginner_chords)
        self.assertIsNot(timeline.original_chords, timeline.beginner_chords)

        # Original has 4 chords, beginner has 2 chords
        self.assertEqual(len(timeline.original_chords), 4)
        self.assertEqual(len(timeline.beginner_chords), 2)
        self.assertEqual(
            [c.chord_name for c in timeline.original_chords], ["C", "G", "Am", "F"]
        )
        self.assertEqual(
            [c.chord_name for c in timeline.beginner_chords], ["C", "Am"]
        )

    def test_4_timing_preserved_during_conversion(self):
        """4. Existing chord timing is preserved during conversion."""
        timeline = SongTimeline.from_analysis_dict(self.sample_analysis)
        for original, converted in zip(
            self.sample_analysis["chords"], timeline.original_chords
        ):
            self.assertAlmostEqual(converted.start_time, original["time"], places=3)
            self.assertAlmostEqual(converted.end_time, original["end"], places=3)
            self.assertEqual(converted.chord_name, original["chord"])

    def test_5_optional_fields_can_be_empty(self):
        """5. Optional notation/beginner fields can be empty without errors."""
        minimal_metadata = SongMetadata(duration=60.0)
        timeline = SongTimeline(
            metadata=minimal_metadata,
            duration=60.0,
            originalChords=[],
            beginnerChords=None,
            sections=[],
            notation=None,
        )
        self.assertIsNone(timeline.notation)
        self.assertIsNone(timeline.beginner_chords)

        # Serialization to JSON must succeed without errors
        json_str = timeline.model_dump_json()
        restored = SongTimeline.model_validate_json(json_str)
        self.assertEqual(restored.duration, 60.0)
        self.assertIsNone(restored.notation)


    def test_6_missing_optional_metadata_does_not_crash(self):
        """6. Missing optional chord metadata does not crash conversion."""
        sparse_analysis = {
            "duration": 45.0,
            "chords": [
                {"time": 0.0, "end": 2.5, "chord": "C"},
                {"time": 2.5, "end": 5.0, "chord": "F"},
            ],
            # No chord_data, no roman_numerals, no tempo, no key, no beginner_chords
        }
        timeline = SongTimeline.from_analysis_dict(sparse_analysis)
        self.assertEqual(timeline.duration, 45.0)
        self.assertEqual(len(timeline.original_chords), 2)
        self.assertEqual(timeline.original_chords[0].chord_name, "C")
        self.assertIsNone(timeline.original_chords[0].notes)
        self.assertIsNone(timeline.original_chords[0].fingering)
        self.assertIsNone(timeline.beginner_chords)

    def test_7_existing_analysis_behavior_remains_compatible(self):
        """7. Existing analysis behavior remains compatible."""
        timeline = SongTimeline.from_analysis_dict(self.sample_analysis)
        legacy = timeline.to_analysis_dict()

        self.assertTrue(legacy["ready"])
        self.assertEqual(legacy["file"], "test_track.mp3")
        self.assertEqual(legacy["duration"], 150.75)
        self.assertEqual(legacy["tempo"], 124.0)
        self.assertEqual(legacy["key"], "C")
        self.assertEqual(legacy["scale"], "Major")
        self.assertEqual(legacy["key_full"], "C Major")
        self.assertEqual(len(legacy["chords"]), 4)
        self.assertEqual(len(legacy["beginner_chords"]), 2)
        self.assertEqual(legacy["chords"][0]["time"], 0.0)
        self.assertEqual(legacy["chords"][0]["end"], 2.0)
        self.assertEqual(legacy["chords"][0]["chord"], "C")
        self.assertEqual(legacy["unique_chords"], ["C", "G", "Am", "F"])
        self.assertEqual(legacy["roman_numerals"]["C"], "I")


if __name__ == "__main__":
    unittest.main()
