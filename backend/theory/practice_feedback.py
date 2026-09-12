"""
backend/theory/practice_feedback.py

Real-Time Practice Note & Chord Matching Engine for HotChords (Phase 11).

Principles & Architectural Rules:
1. Strict Observation Layer: Never mutates SongTimeline, canonical harmony, or PlaybackClock.
2. Authoritative Expected State: Expected notes are derived ONLY from PianoVoicingEngine or PracticeSession.
3. Precise Metrics: Computes exact correct, missing, and extra notes, note precision, note recall, and note F1.
4. Matching Modes:
   - EXACT_NOTE_MATCH: Exact MIDI note numbers (e.g., 60 for C4).
   - PITCH_CLASS_MATCH: Modulo-12 pitch classes (e.g., C3, C4, C5 all match pitch class 0).
5. Feedback States:
   - NO_INPUT, LISTENING, PARTIAL, MATCH, WRONG_NOTES, LOW_CONFIDENCE, EXPECTED_CHORD_UNAVAILABLE,
     INPUT_PERMISSION_DENIED, INPUT_UNAVAILABLE, INPUT_UNSUPPORTED.
6. Timing Grace & Sustain Hysteresis:
   - Configurable grace window around chord boundaries (PREPARING, ACTIVE, TRANSITION).
   - Decay tolerance: Ringing notes from the immediately preceding chord are not penalized as extra notes.
"""

from enum import Enum
from typing import List, Dict, Optional, Set, Tuple, Any
import numpy as np

from backend.analysis.test_signals import midi_to_note_name, note_name_to_midi
from backend.theory.piano_voicing import voice_chord, parse_chord_components


class MatchingMode(str, Enum):
    EXACT_NOTE_MATCH = "EXACT_NOTE_MATCH"
    PITCH_CLASS_MATCH = "PITCH_CLASS_MATCH"


class FeedbackStatus(str, Enum):
    NO_INPUT = "NO_INPUT"
    LISTENING = "LISTENING"
    PARTIAL = "PARTIAL"
    MATCH = "MATCH"
    WRONG_NOTES = "WRONG_NOTES"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    EXPECTED_CHORD_UNAVAILABLE = "EXPECTED_CHORD_UNAVAILABLE"
    INPUT_PERMISSION_DENIED = "INPUT_PERMISSION_DENIED"
    INPUT_UNAVAILABLE = "INPUT_UNAVAILABLE"
    INPUT_UNSUPPORTED = "INPUT_UNSUPPORTED"


class TimingPhase(str, Enum):
    PREPARING = "PREPARING"
    ACTIVE = "ACTIVE"
    TRANSITION = "TRANSITION"


def pitch_class(midi: int) -> int:
    """Return modulo-12 pitch class (0 = C, 1 = C#, ..., 11 = B)."""
    return int(midi) % 12


def pitch_class_to_name(pc: int) -> str:
    names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    return names[pc % 12]


def evaluate_note_matching(
    expected_midi: List[int],
    observed_midi: List[int],
    mode: MatchingMode = MatchingMode.EXACT_NOTE_MATCH,
    previous_chord_midi: Optional[List[int]] = None,
    is_transition: bool = False,
) -> Dict[str, Any]:
    """
    Compare observed MIDI notes against expected MIDI notes.
    
    Returns:
        Dict with correct_notes, missing_notes, extra_notes, precision, recall, f1.
    """
    if mode == MatchingMode.EXACT_NOTE_MATCH:
        exp_set = set(expected_midi)
        obs_set = set(observed_midi)
        prev_set = set(previous_chord_midi or [])
        
        correct_set = exp_set.intersection(obs_set)
        missing_set = exp_set.difference(obs_set)
        raw_extra_set = obs_set.difference(exp_set)
        
        # Sustain decay tolerance: If in transition grace window, do not penalize decaying notes from prev chord
        if is_transition and prev_set:
            extra_set = raw_extra_set.difference(prev_set)
        else:
            extra_set = raw_extra_set

        correct = sorted(list(correct_set))
        missing = sorted(list(missing_set))
        extra = sorted(list(extra_set))

    else:  # PITCH_CLASS_MATCH
        exp_pc_set = {pitch_class(m) for m in expected_midi}
        obs_pc_set = {pitch_class(m) for m in observed_midi}
        prev_pc_set = {pitch_class(m) for m in (previous_chord_midi or [])}
        
        correct_pc = exp_pc_set.intersection(obs_pc_set)
        missing_pc = exp_pc_set.difference(obs_pc_set)
        raw_extra_pc = obs_pc_set.difference(exp_pc_set)
        
        if is_transition and prev_pc_set:
            extra_pc = raw_extra_pc.difference(prev_pc_set)
        else:
            extra_pc = raw_extra_pc

        # Map back to note names for display
        correct = sorted([pitch_class_to_name(pc) for pc in correct_pc])
        missing = sorted([pitch_class_to_name(pc) for pc in missing_pc])
        extra = sorted([pitch_class_to_name(pc) for pc in extra_pc])

    # Calculate Precision, Recall, F1
    n_correct = len(correct)
    n_obs = len(observed_midi)
    n_exp = len(expected_midi)

    if n_exp == 0:
        recall = 1.0 if n_obs == 0 else 0.0
        precision = 1.0 if n_obs == 0 else 0.0
    else:
        recall = n_correct / float(n_exp)
        precision = (n_correct / float(n_correct + len(extra))) if (n_correct + len(extra)) > 0 else (1.0 if n_obs == 0 else 0.0)

    if (precision + recall) > 0:
        f1 = 2.0 * (precision * recall) / (precision + recall)
    else:
        f1 = 0.0

    return {
        "matchingMode": mode.value,
        "correctNotes": correct,
        "missingNotes": missing,
        "extraNotes": extra,
        "notePrecision": round(float(precision), 3),
        "noteRecall": round(float(recall), 3),
        "noteF1": round(float(f1), 3),
    }


def compute_practice_feedback(
    expected_chord: Optional[str],
    expected_midi: List[int],
    observed_midi: List[int],
    observed_confidence: float = 1.0,
    input_status: str = "DETECTED",
    matching_mode: MatchingMode = MatchingMode.EXACT_NOTE_MATCH,
    playback_time: Optional[float] = None,
    chord_start: Optional[float] = None,
    chord_end: Optional[float] = None,
    grace_window_seconds: float = 0.25,
    previous_chord_midi: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """
    Generate authoritative pedagogical practice feedback for the current playback moment.
    """
    # 1. Handle permission / input failure states
    if input_status == "INPUT_PERMISSION_DENIED":
        return _build_response(FeedbackStatus.INPUT_PERMISSION_DENIED, expected_chord, expected_midi, observed_midi, matching_mode)
    if input_status == "INPUT_UNAVAILABLE":
        return _build_response(FeedbackStatus.INPUT_UNAVAILABLE, expected_chord, expected_midi, observed_midi, matching_mode)
    if input_status == "INPUT_UNSUPPORTED":
        return _build_response(FeedbackStatus.INPUT_UNSUPPORTED, expected_chord, expected_midi, observed_midi, matching_mode)

    # 2. Check if expected chord is present
    if not expected_chord or not expected_midi:
        return _build_response(FeedbackStatus.EXPECTED_CHORD_UNAVAILABLE, expected_chord, expected_midi, observed_midi, matching_mode)

    # 3. Check for NO_INPUT or silence
    if input_status == "NO_INPUT" or (not observed_midi and observed_confidence < 0.2):
        return _build_response(FeedbackStatus.NO_INPUT, expected_chord, expected_midi, observed_midi, matching_mode)

    # 4. Check for low-confidence noisy input
    if observed_confidence < 0.35:
        return _build_response(FeedbackStatus.LOW_CONFIDENCE, expected_chord, expected_midi, observed_midi, matching_mode, confidence=observed_confidence)

    # 5. Timing Phase & Grace Window
    is_transition = False
    timing_phase = TimingPhase.ACTIVE
    timing_offset_ms = 0.0

    if playback_time is not None and chord_start is not None and chord_end is not None:
        if playback_time < chord_start:
            timing_phase = TimingPhase.PREPARING
            timing_offset_ms = round((playback_time - chord_start) * 1000.0, 1)
            is_transition = abs(playback_time - chord_start) <= grace_window_seconds
        elif (chord_end - playback_time) <= grace_window_seconds or (playback_time - chord_start) <= grace_window_seconds:
            timing_phase = TimingPhase.TRANSITION
            is_transition = True
            timing_offset_ms = round((playback_time - chord_start) * 1000.0, 1)

    # 6. Evaluate Note & Pitch Comparison
    comparison = evaluate_note_matching(
        expected_midi=expected_midi,
        observed_midi=observed_midi,
        mode=matching_mode,
        previous_chord_midi=previous_chord_midi,
        is_transition=is_transition,
    )

    recall = comparison["noteRecall"]
    precision = comparison["notePrecision"]

    # 7. Determine Chord Match Status
    if recall >= 0.80 and precision >= 0.70:
        feedback_status = FeedbackStatus.MATCH
    elif recall >= 0.50 and precision >= 0.50:
        feedback_status = FeedbackStatus.PARTIAL
    elif not observed_midi:
        feedback_status = FeedbackStatus.NO_INPUT
    else:
        feedback_status = FeedbackStatus.WRONG_NOTES

    return {
        "inputStatus": input_status,
        "feedbackStatus": feedback_status.value,
        "matchingMode": matching_mode.value,
        "expected": {
            "chord": expected_chord,
            "midi": expected_midi,
            "notes": [midi_to_note_name(m) for m in expected_midi],
        },
        "observed": {
            "midi": observed_midi,
            "notes": [midi_to_note_name(m) for m in observed_midi],
            "confidence": round(float(observed_confidence), 3),
        },
        "comparison": comparison,
        "timing": {
            "phase": timing_phase.value,
            "isTransition": is_transition,
            "offsetMs": timing_offset_ms,
        }
    }


def _build_response(
    status: FeedbackStatus,
    expected_chord: Optional[str],
    expected_midi: List[int],
    observed_midi: List[int],
    mode: MatchingMode,
    confidence: float = 0.0,
) -> Dict[str, Any]:
    """Helper to assemble standard feedback dictionary for early-exit statuses."""
    comparison = evaluate_note_matching(expected_midi, observed_midi, mode=mode)
    return {
        "inputStatus": status.value,
        "feedbackStatus": status.value,
        "matchingMode": mode.value,
        "expected": {
            "chord": expected_chord or "",
            "midi": expected_midi,
            "notes": [midi_to_note_name(m) for m in expected_midi],
        },
        "observed": {
            "midi": observed_midi,
            "notes": [midi_to_note_name(m) for m in observed_midi],
            "confidence": round(float(confidence), 3),
        },
        "comparison": comparison,
        "timing": {
            "phase": TimingPhase.ACTIVE.value,
            "isTransition": False,
            "offsetMs": 0.0,
        }
    }
