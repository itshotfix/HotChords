"""
tests/test_phase12_practice_metrics.py

Unit Tests for Practice Session Metrics, Chord Mastery & Recommendations (Phase 12):
- Incremental session statistics tracking (objective separation without single player-accuracy score)
- Per-chord mastery maps
- Targeted practice recommendations
- Conservative adaptive tempo recommendations
- Exportable session JSON summary
"""

import pytest
from backend.theory.practice_metrics import (
    PracticeMetricsTracker,
    PlayerFeedbackEvent,
    PlayerFeedbackEventType,
    ChordMasteryStats,
)


@pytest.fixture
def tracker():
    t = PracticeMetricsTracker(max_recent_events=50)
    t.start_session(0.0)
    return t


class TestPhase12PracticeMetrics:

    def test_session_metrics_accumulation(self, tracker):
        """18. Objective session metrics accumulation without single score collapse."""
        # Record 3 matched chords, 1 partial chord, 1 wrong note event
        tracker.record_feedback_event(PlayerFeedbackEvent(
            eventType=PlayerFeedbackEventType.CHORD_MATCHED,
            timestamp=1.0,
            chordName="C",
            expectedMidi=[60, 64, 67],
            observedMidi=[60, 64, 67],
            timingOffsetMs=20.0,
            notePrecision=1.0,
            noteRecall=1.0,
            noteF1=1.0,
        ))
        tracker.record_feedback_event(PlayerFeedbackEvent(
            eventType=PlayerFeedbackEventType.CHORD_MATCHED,
            timestamp=3.0,
            chordName="G",
            expectedMidi=[55, 59, 62],
            observedMidi=[55, 59, 62],
            timingOffsetMs=35.0,
            notePrecision=1.0,
            noteRecall=1.0,
            noteF1=1.0,
        ))
        tracker.record_feedback_event(PlayerFeedbackEvent(
            eventType=PlayerFeedbackEventType.CHORD_PARTIAL,
            timestamp=5.0,
            chordName="Am",
            expectedMidi=[57, 60, 64],
            observedMidi=[57, 60],
            timingOffsetMs=40.0,
            notePrecision=1.0,
            noteRecall=0.667,
            noteF1=0.80,
        ))
        tracker.record_feedback_event(PlayerFeedbackEvent(
            eventType=PlayerFeedbackEventType.WRONG_NOTES,
            timestamp=7.0,
            chordName="F",
            expectedMidi=[53, 57, 60],
            observedMidi=[54, 58, 61],
            notePrecision=0.0,
            noteRecall=0.0,
            noteF1=0.0,
        ))

        tracker.update_duration(8.0)
        summary = tracker.get_session_summary()

        assert summary["chordsAttempted"] == 3
        assert summary["chordsMatched"] == 2
        assert summary["chordsPartial"] == 1
        assert summary["wrongNoteEvents"] == 1
        assert summary["practiceDurationSeconds"] == 8.0
        assert summary["averageTimingOffsetMs"] > 0.0
        assert summary["noteRecall"] > 0.80
        # Invariant: No single "player_accuracy" score exists in summary
        assert "playerAccuracy" not in summary

    def test_chord_mastery_tracking(self, tracker):
        """17. Per-chord mastery statistics tracking."""
        # 2 attempts on C (both matched)
        for t in [1.0, 5.0]:
            tracker.record_feedback_event(PlayerFeedbackEvent(
                eventType=PlayerFeedbackEventType.CHORD_MATCHED,
                timestamp=t,
                chordName="C",
                expectedMidi=[60, 64, 67],
                observedMidi=[60, 64, 67],
                timingOffsetMs=15.0,
                notePrecision=1.0,
                noteRecall=1.0,
            ))

        # 2 attempts on C#m (both missed)
        for t in [3.0, 7.0]:
            tracker.record_feedback_event(PlayerFeedbackEvent(
                eventType=PlayerFeedbackEventType.CHORD_MISSED,
                timestamp=t,
                chordName="C#m",
                expectedMidi=[49, 52, 56],
                observedMidi=[],
                notePrecision=0.0,
                noteRecall=0.0,
            ))

        mastery = tracker.get_chord_mastery_map()

        assert "C" in mastery
        assert mastery["C"].attempts == 2
        assert mastery["C"].matches == 2
        assert mastery["C"].avg_note_recall == 1.0

        assert "C#m" in mastery
        assert mastery["C#m"].attempts == 2
        assert mastery["C#m"].matches == 0
        assert mastery["C#m"].misses == 2
        assert mastery["C#m"].avg_note_recall == 0.0

    def test_targeted_practice_recommendation_engine(self, tracker):
        """19. Deterministic recommendations for weak chords, timing lag, and extra notes."""
        # 1. Feed low recall for C#m
        for t in [1.0, 3.0, 5.0]:
            tracker.record_feedback_event(PlayerFeedbackEvent(
                eventType=PlayerFeedbackEventType.CHORD_MISSED,
                timestamp=t,
                chordName="C#m",
                expectedMidi=[49, 52, 56],
                observedMidi=[],
                timingOffsetMs=180.0,  # Also large timing offset (>150ms)
                notePrecision=0.50,    # Low precision
                noteRecall=0.0,
            ))

        tracker.record_feedback_event(PlayerFeedbackEvent(
            eventType=PlayerFeedbackEventType.CHORD_MATCHED,
            timestamp=7.0,
            chordName="C",
            expectedMidi=[60, 64, 67],
            observedMidi=[60, 64, 67],
            timingOffsetMs=160.0,
            notePrecision=0.60,
            noteRecall=1.0,
        ))

        recs = tracker.get_targeted_recommendations()
        rec_types = [r["type"] for r in recs]

        # Should identify C#m weak chord
        assert "CHORD_FOCUS" in rec_types
        chord_rec = next(r for r in recs if r["type"] == "CHORD_FOCUS")
        assert chord_rec["chord"] == "C#m"

        # Should identify timing lag
        assert "TIMING" in rec_types

        # Should identify extra note precision error
        assert "ACCURACY" in rec_types

    def test_conservative_adaptive_tempo_recommendation(self, tracker):
        """20. Conservative tempo adjustment advice based on consecutive loop history."""
        # Scenario A: Initial session (< 2 loops) -> MAINTAIN
        advice1 = tracker.get_adaptive_tempo_recommendation(current_practice_bpm=60.0, original_bpm=120.0)
        assert advice1["recommendation"] == "MAINTAIN"

        # Scenario B: 2 consecutive high-accuracy loops (>=90%) -> INCREASE_TEMPO
        for _ in range(2):
            for _ in range(4):
                tracker.record_feedback_event(PlayerFeedbackEvent(
                    eventType=PlayerFeedbackEventType.CHORD_MATCHED,
                    timestamp=1.0,
                    chordName="C",
                ))
            tracker.record_loop_completed()

        advice2 = tracker.get_adaptive_tempo_recommendation(current_practice_bpm=60.0, original_bpm=120.0)
        assert advice2["recommendation"] == "INCREASE_TEMPO"
        assert advice2["recommendedBpm"] > 60.0

        # Scenario C: 2 consecutive struggling loops (<=45%) -> DECREASE_TEMPO
        tracker.reset_session()
        for _ in range(2):
            for _ in range(4):
                tracker.record_feedback_event(PlayerFeedbackEvent(
                    eventType=PlayerFeedbackEventType.CHORD_MISSED,
                    timestamp=1.0,
                    chordName="C",
                ))
            tracker.record_loop_completed()

        advice3 = tracker.get_adaptive_tempo_recommendation(current_practice_bpm=60.0, original_bpm=120.0)
        assert advice3["recommendation"] == "DECREASE_TEMPO"
        assert advice3["recommendedBpm"] < 60.0

    def test_exportable_session_report(self, tracker):
        """29. Export lightweight JSON report without raw audio."""
        tracker.record_feedback_event(PlayerFeedbackEvent(
            eventType=PlayerFeedbackEventType.CHORD_MATCHED,
            timestamp=1.0,
            chordName="C",
        ))
        tracker.record_loop_completed()

        report = tracker.export_session_report()
        assert "summary" in report
        assert "chordMastery" in report
        assert "loopHistory" in report
        assert "recommendations" in report
        assert "rawAudio" not in report
