"""
tests/test_phase12_feedback_events.py

Unit Tests for Player Feedback Events & Bounded Memory Ring Buffer (Phase 12):
- Discrete player feedback event emissions (CHORD_READY, CHORD_MATCHED, CHORD_PARTIAL, CHORD_MISSED, WRONG_NOTES, NO_INPUT)
- Bounded event buffer capacity (max 50 events)
- Timing offset tracking
"""

import pytest
from backend.theory.practice_metrics import (
    PracticeMetricsTracker,
    PlayerFeedbackEvent,
    PlayerFeedbackEventType,
)


class TestPhase12FeedbackEvents:

    def test_discrete_feedback_events_types(self):
        """13. Discrete feedback event objects preserve structured metadata."""
        event = PlayerFeedbackEvent(
            eventType=PlayerFeedbackEventType.CHORD_MATCHED,
            timestamp=2.5,
            chordName="G",
            expectedMidi=[55, 59, 62],
            observedMidi=[55, 59, 62],
            timingOffsetMs=35.0,
            notePrecision=1.0,
            noteRecall=1.0,
            noteF1=1.0,
            details={"attackConfidence": 0.92},
        )

        assert event.event_type == PlayerFeedbackEventType.CHORD_MATCHED
        assert event.timestamp == 2.5
        assert event.chord_name == "G"
        assert event.timing_offset_ms == 35.0
        assert event.details["attackConfidence"] == 0.92

    def test_bounded_ring_buffer_behavior(self):
        """23 & 28. Event buffer does not exceed max_recent_events=50 under continuous logging."""
        tracker = PracticeMetricsTracker(max_recent_events=50)

        # Feed 120 events
        for i in range(120):
            tracker.record_feedback_event(PlayerFeedbackEvent(
                eventType=PlayerFeedbackEventType.CHORD_MATCHED,
                timestamp=float(i),
                chordName="C",
                expectedMidi=[60, 64, 67],
                observedMidi=[60, 64, 67],
            ))

        # Invariant: Ring buffer length is capped at exactly 50
        assert len(tracker.recent_events) == 50
        # The oldest event in the buffer is event index 70
        assert tracker.recent_events[0].timestamp == 70.0
        assert tracker.recent_events[-1].timestamp == 119.0
        # Incremental totals continue to count all 120
        assert tracker.chords_attempted == 120
        assert tracker.chords_matched == 120
