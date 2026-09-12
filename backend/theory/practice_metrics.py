"""
backend/theory/practice_metrics.py

Real-Time Practice Session Metrics, Chord Mastery & Targeted Pedagogy Engine for HotChords (Phase 12).

Key Principles:
1. Strict Objective Separation: Does NOT collapse distinct metrics into a single misleading "player accuracy %" score.
2. Bounded In-Memory Event Log: Fixed-size ring buffer (max 50 events) preventing memory accumulation.
3. Per-Chord Mastery Tracking: Real-time statistical accumulation for each unique chord.
4. Deterministic Recommendations: Actionable targeted advice for weak chords, timing lag, and extra notes.
5. Conservative Adaptive Tempo: Recommends tempo adjustments based on consecutive loop completion rates.
6. Exportable Session Report: Lightweight, safe JSON summary with zero audio storage.
"""

from enum import Enum
from typing import List, Dict, Optional, Any, Tuple
from collections import deque
import numpy as np
from pydantic import BaseModel, Field, ConfigDict


class PlayerFeedbackEventType(str, Enum):
    CHORD_READY = "CHORD_READY"
    CHORD_MATCHED = "CHORD_MATCHED"
    CHORD_PARTIAL = "CHORD_PARTIAL"
    CHORD_MISSED = "CHORD_MISSED"
    WRONG_NOTES = "WRONG_NOTES"
    NO_INPUT = "NO_INPUT"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    INPUT_PROBLEM = "INPUT_PROBLEM"


class PlayerFeedbackEvent(BaseModel):
    """Structured discrete feedback event emitted during practice."""
    event_type: PlayerFeedbackEventType = Field(..., alias="eventType")
    timestamp: float = Field(..., alias="timestamp")
    chord_name: str = Field(default="", alias="chordName")
    expected_midi: List[int] = Field(default_factory=list, alias="expectedMidi")
    observed_midi: List[int] = Field(default_factory=list, alias="observedMidi")
    timing_offset_ms: float = Field(default=0.0, alias="timingOffsetMs")
    note_precision: float = Field(default=1.0, alias="notePrecision")
    note_recall: float = Field(default=1.0, alias="noteRecall")
    note_f1: float = Field(default=1.0, alias="noteF1")
    details: Dict[str, Any] = Field(default_factory=dict, alias="details")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ChordMasteryStats(BaseModel):
    """Objective mastery and practice statistics for an individual chord."""
    chord_name: str = Field(..., alias="chordName")
    attempts: int = Field(default=0, alias="attempts")
    matches: int = Field(default=0, alias="matches")
    partials: int = Field(default=0, alias="partials")
    misses: int = Field(default=0, alias="misses")
    avg_timing_offset_ms: float = Field(default=0.0, alias="avgTimingOffsetMs")
    avg_note_recall: float = Field(default=0.0, alias="avgNoteRecall")
    avg_note_precision: float = Field(default=0.0, alias="avgNotePrecision")
    difficulty_score: float = Field(default=0.0, alias="difficultyScore")
    simplification_level: int = Field(default=0, alias="simplificationLevel")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class PracticeMetricsTracker:
    """
    Incremental Session Metrics Tracker and Pedagogy Recommendation Engine.
    """

    def __init__(self, max_recent_events: int = 50):
        self.max_recent_events = max_recent_events
        self.recent_events: deque = deque(maxlen=max_recent_events)
        
        # Session Aggregates
        self.session_start_time = 0.0
        self.total_practice_duration_s = 0.0
        self.completed_loops = 0
        self.chords_attempted = 0
        self.chords_matched = 0
        self.chords_partial = 0
        self.chords_missed = 0
        self.wrong_note_events = 0
        self.no_input_events = 0
        self.low_confidence_events = 0

        # Timing and accuracy accumulators
        self.timing_offsets: List[float] = []
        self.note_precisions: List[float] = []
        self.note_recalls: List[float] = []
        self.note_f1s: List[float] = []

        # Per-Chord Accumulators: chord -> stats
        self.chord_stats: Dict[str, Dict[str, Any]] = {}
        
        # Loop tracking for adaptive tempo
        self.loop_history: List[Dict[str, Any]] = []
        self._current_loop_matches = 0
        self._current_loop_attempts = 0

    def start_session(self, current_playback_time: float = 0.0) -> None:
        """Mark practice session commencement."""
        self.session_start_time = current_playback_time

    def record_feedback_event(self, event: PlayerFeedbackEvent) -> None:
        """
        Record a discrete practice event into the bounded ring buffer and incremental accumulators.
        """
        self.recent_events.append(event)
        c_name = event.chord_name or "N"

        # Initialize chord accumulator if new
        if c_name not in self.chord_stats and c_name != "N":
            self.chord_stats[c_name] = {
                "attempts": 0,
                "matches": 0,
                "partials": 0,
                "misses": 0,
                "timing_offsets": [],
                "recalls": [],
                "precisions": [],
                "difficulty": 0.0,
                "simplification_level": 0,
            }

        # Update event-specific counters
        if event.event_type == PlayerFeedbackEventType.CHORD_MATCHED:
            self.chords_attempted += 1
            self.chords_matched += 1
            self._current_loop_attempts += 1
            self._current_loop_matches += 1
            self.timing_offsets.append(event.timing_offset_ms)
            self.note_precisions.append(event.note_precision)
            self.note_recalls.append(event.note_recall)
            self.note_f1s.append(event.note_f1)

            if c_name in self.chord_stats:
                st = self.chord_stats[c_name]
                st["attempts"] += 1
                st["matches"] += 1
                st["timing_offsets"].append(event.timing_offset_ms)
                st["recalls"].append(event.note_recall)
                st["precisions"].append(event.note_precision)

        elif event.event_type == PlayerFeedbackEventType.CHORD_PARTIAL:
            self.chords_attempted += 1
            self.chords_partial += 1
            self._current_loop_attempts += 1
            self.timing_offsets.append(event.timing_offset_ms)
            self.note_precisions.append(event.note_precision)
            self.note_recalls.append(event.note_recall)
            self.note_f1s.append(event.note_f1)

            if c_name in self.chord_stats:
                st = self.chord_stats[c_name]
                st["attempts"] += 1
                st["partials"] += 1
                st["timing_offsets"].append(event.timing_offset_ms)
                st["recalls"].append(event.note_recall)
                st["precisions"].append(event.note_precision)

        elif event.event_type == PlayerFeedbackEventType.CHORD_MISSED:
            self.chords_attempted += 1
            self.chords_missed += 1
            self._current_loop_attempts += 1
            self.note_recalls.append(0.0)

            if c_name in self.chord_stats:
                st = self.chord_stats[c_name]
                st["attempts"] += 1
                st["misses"] += 1
                st["recalls"].append(0.0)

        elif event.event_type == PlayerFeedbackEventType.WRONG_NOTES:
            self.wrong_note_events += 1

        elif event.event_type == PlayerFeedbackEventType.NO_INPUT:
            self.no_input_events += 1

        elif event.event_type == PlayerFeedbackEventType.LOW_CONFIDENCE:
            self.low_confidence_events += 1

    def record_loop_completed(self) -> None:
        """Record completion of one practice loop iteration."""
        self.completed_loops += 1
        loop_match_rate = (self._current_loop_matches / max(1, self._current_loop_attempts))
        self.loop_history.append({
            "loopNumber": self.completed_loops,
            "attempts": self._current_loop_attempts,
            "matches": self._current_loop_matches,
            "matchRate": round(loop_match_rate, 3),
        })
        self._current_loop_matches = 0
        self._current_loop_attempts = 0

    def update_duration(self, current_playback_time: float) -> None:
        """Update active practice duration."""
        if self.session_start_time is not None and current_playback_time >= self.session_start_time:
            self.total_practice_duration_s = current_playback_time - self.session_start_time

    def get_session_summary(self) -> Dict[str, Any]:
        """
        Get objective session statistics without collapsing into a single misleading score.
        """
        avg_offset = float(np.mean(self.timing_offsets)) if self.timing_offsets else 0.0
        med_offset = float(np.median(self.timing_offsets)) if self.timing_offsets else 0.0
        avg_prec = float(np.mean(self.note_precisions)) if self.note_precisions else 0.0
        avg_rec = float(np.mean(self.note_recalls)) if self.note_recalls else 0.0
        avg_f1 = float(np.mean(self.note_f1s)) if self.note_f1s else 0.0

        return {
            "practiceDurationSeconds": round(self.total_practice_duration_s, 1),
            "completedLoops": self.completed_loops,
            "chordsAttempted": self.chords_attempted,
            "chordsMatched": self.chords_matched,
            "chordsPartial": self.chords_partial,
            "chordsMissed": self.chords_missed,
            "wrongNoteEvents": self.wrong_note_events,
            "noInputEvents": self.no_input_events,
            "lowConfidenceEvents": self.low_confidence_events,
            "averageTimingOffsetMs": round(avg_offset, 1),
            "medianTimingOffsetMs": round(med_offset, 1),
            "notePrecision": round(avg_prec, 3),
            "noteRecall": round(avg_rec, 3),
            "noteF1": round(avg_f1, 3),
        }

    def get_chord_mastery_map(self) -> Dict[str, ChordMasteryStats]:
        """
        Return structured mastery statistics for each unique chord.
        """
        res = {}
        for c_name, st in self.chord_stats.items():
            avg_off = float(np.mean(st["timing_offsets"])) if st["timing_offsets"] else 0.0
            avg_rec = float(np.mean(st["recalls"])) if st["recalls"] else 0.0
            avg_prec = float(np.mean(st["precisions"])) if st["precisions"] else 0.0

            res[c_name] = ChordMasteryStats(
                chordName=c_name,
                attempts=st["attempts"],
                matches=st["matches"],
                partials=st["partials"],
                misses=st["misses"],
                avgTimingOffsetMs=round(avg_off, 1),
                avgNoteRecall=round(avg_rec, 3),
                avgNotePrecision=round(avg_prec, 3),
                difficultyScore=round(st["difficulty"], 2),
                simplificationLevel=st["simplification_level"],
            )
        return res

    def get_targeted_recommendations(self) -> List[Dict[str, Any]]:
        """
        Generate deterministic pedagogy recommendations based on measured session metrics.
        """
        recommendations = []

        # 1. Check for specific weak chords (attempts >= 2, recall < 0.60)
        mastery = self.get_chord_mastery_map()
        for c_name, stats in mastery.items():
            if stats.attempts >= 2 and stats.avg_note_recall < 0.60:
                recommendations.append({
                    "type": "CHORD_FOCUS",
                    "chord": c_name,
                    "priority": "HIGH",
                    "message": f"Focus on {c_name}: note recall is {stats.avg_note_recall * 100:.0f}%. Practice individual hand shape.",
                })

        # 2. Check for timing lag
        summary = self.get_session_summary()
        if summary["averageTimingOffsetMs"] > 150.0 and summary["chordsAttempted"] >= 4:
            recommendations.append({
                "type": "TIMING",
                "priority": "MEDIUM",
                "message": f"Late chord transitions observed (avg +{summary['averageTimingOffsetMs']:.0f}ms). Consider slowing tempo to anticipate hand movements.",
            })

        # 3. Check for extra note precision errors
        if summary["notePrecision"] < 0.70 and summary["chordsAttempted"] >= 4:
            recommendations.append({
                "type": "ACCURACY",
                "priority": "MEDIUM",
                "message": "Extra adjacent notes detected. Check finger arch and release adjacent keys cleanly.",
            })

        return recommendations

    def get_adaptive_tempo_recommendation(
        self,
        current_practice_bpm: float,
        original_bpm: float,
    ) -> Dict[str, Any]:
        """
        Conservative adaptive tempo advice. Does NOT force automatic tempo changes.
        """
        current_practice_bpm = float(current_practice_bpm)
        original_bpm = float(original_bpm)

        if len(self.loop_history) < 2:
            return {
                "recommendation": "MAINTAIN",
                "recommendedBpm": current_practice_bpm,
                "reason": "Continue practice at current tempo to build muscle memory.",
            }

        recent_loops = self.loop_history[-2:]
        avg_recent_match = np.mean([lp["matchRate"] for lp in recent_loops])

        if avg_recent_match >= 0.88 and current_practice_bpm < original_bpm:
            # Conservative increase (+2 to +4 BPM)
            step = min(4.0, original_bpm - current_practice_bpm)
            next_bpm = round(current_practice_bpm + step, 1)
            return {
                "recommendation": "INCREASE_TEMPO",
                "recommendedBpm": next_bpm,
                "step": step,
                "reason": f"Excellent mastery across last 2 loops ({avg_recent_match * 100:.0f}% match). Ready to try {next_bpm} BPM.",
            }

        elif avg_recent_match <= 0.45 and current_practice_bpm > 35.0:
            # Conservative decrease (-5 BPM)
            next_bpm = max(30.0, round(current_practice_bpm - 5.0, 1))
            return {
                "recommendation": "DECREASE_TEMPO",
                "recommendedBpm": next_bpm,
                "step": -5.0,
                "reason": f"High error rate across last 2 loops ({avg_recent_match * 100:.0f}% match). Slow down to {next_bpm} BPM for accuracy.",
            }

        return {
            "recommendation": "MAINTAIN",
            "recommendedBpm": current_practice_bpm,
            "reason": "Steady progress. Maintain current tempo.",
        }

    def export_session_report(self) -> Dict[str, Any]:
        """
        Export complete anonymous session report as clean JSON.
        """
        mastery_dict = {k: v.model_dump(by_alias=True) for k, v in self.get_chord_mastery_map().items()}
        return {
            "summary": self.get_session_summary(),
            "chordMastery": mastery_dict,
            "loopHistory": self.loop_history,
            "recommendations": self.get_targeted_recommendations(),
            "recentEventsCount": len(self.recent_events),
        }

    def reset_session(self) -> None:
        """Reset all metrics and accumulators."""
        self.recent_events.clear()
        self.session_start_time = 0.0
        self.total_practice_duration_s = 0.0
        self.completed_loops = 0
        self.chords_attempted = 0
        self.chords_matched = 0
        self.chords_partial = 0
        self.chords_missed = 0
        self.wrong_note_events = 0
        self.no_input_events = 0
        self.low_confidence_events = 0
        self.timing_offsets.clear()
        self.note_precisions.clear()
        self.note_recalls.clear()
        self.note_f1s.clear()
        self.chord_stats.clear()
        self.loop_history.clear()
        self._current_loop_matches = 0
        self._current_loop_attempts = 0
