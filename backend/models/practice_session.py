"""
backend/models/practice_session.py

Deterministic Practice Session State Engine & Real-Time Chord Guidance for HotChords (Phase 10).

Principles:
1. PlaybackClock remains the sole authoritative musical clock.
2. Canonical chord timestamps remain original song time; practice tempo scales playback rate (playbackRate = practiceBpm / originalBpm).
3. Non-destructive: Simplification & transposition compute transient representations without mutating canonical detected data.
4. Explains hold/change intervals, current/next chord preparations, and loop wrapping without ML or duplicate timers.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Dict, Optional, Any, Tuple, TYPE_CHECKING
from pydantic import BaseModel, Field, ConfigDict
import numpy as np

from backend.theory.piano_voicing import (
    parse_chord_components,
    voice_chord,
    voice_chord_progression,
)
from backend.theory.simplification import (
    reduce_chord_harmony,
    evaluate_beginner_difficulty,
    EASY_CHORDS,
)
from backend.theory.transposition import (
    transpose_chord_symbol,
)

if TYPE_CHECKING:
    from backend.theory.beginner_practice import (
        BeginnerPracticePlan,
        PracticeSection,
    )


class PracticeStatus(str, Enum):
    IDLE = "IDLE"
    READY = "READY"
    PLAYING = "PLAYING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    UNAVAILABLE = "UNAVAILABLE"


class PracticeMode(str, Enum):
    ORIGINAL = "ORIGINAL"
    PIANO = "PIANO"


class PracticeChordGuidance(BaseModel):
    """Authoritative real-time guidance for the currently active and upcoming chord."""
    current_chord: str = Field(..., alias="currentChord")
    next_chord: Optional[str] = Field(default=None, alias="nextChord")
    current_chord_start: float = Field(..., alias="currentChordStart")
    current_chord_end: float = Field(..., alias="currentChordEnd")
    progress_within_chord: float = Field(default=0.0, alias="progressWithinChord", description="Normalized progress [0.0, 1.0]")
    time_until_next_chord: float = Field(default=0.0, alias="timeUntilNextChord", description="Remaining seconds in active chord")
    
    # Voicing & Hand assignments for current & next
    current_voicing: Optional[Dict[str, Any]] = Field(default=None, alias="currentVoicing")
    next_voicing: Optional[Dict[str, Any]] = Field(default=None, alias="nextVoicing")
    next_hand_assignment: Optional[Dict[str, Any]] = Field(default=None, alias="nextHandAssignment")
    
    # Difficulty & Simplification
    difficulty_score: float = Field(default=0.0, alias="difficultyScore")
    difficulty_category: str = Field(default="EASY", alias="difficultyCategory")
    suggested_simplification: Optional[str] = Field(default=None, alias="suggestedSimplification")
    transition_distance: Optional[float] = Field(default=None, alias="transitionDistance")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class PracticeNoteFeedbackContract(BaseModel):
    """
    Contract for real-time note & pitch feedback (Phase 10 & 11).
    Authoritative expected harmonic notes derived from PianoVoicingEngine;
    Observed notes and comparison metrics populated when real-time input is active.
    """
    expected_notes: List[str] = Field(default_factory=list, alias="expectedNotes")
    expected_midi: List[int] = Field(default_factory=list, alias="expectedMidi")
    expected_chord: str = Field(..., alias="expectedChord")
    expected_root: str = Field(..., alias="expectedRoot")
    expected_quality: str = Field(..., alias="expectedQuality")
    
    # Phase 11 Real-Time Audio Feedback Fields
    input_status: Optional[str] = Field(default="LISTENING", alias="inputStatus")
    feedback_status: Optional[str] = Field(default="LISTENING", alias="feedbackStatus")
    matching_mode: Optional[str] = Field(default="EXACT_NOTE_MATCH", alias="matchingMode")
    detected_notes: Optional[List[str]] = Field(default=None, alias="detectedNotes")
    detected_midi: Optional[List[int]] = Field(default=None, alias="detectedMidi")
    detected_chord: Optional[str] = Field(default=None, alias="detectedChord")
    correct_notes: Optional[List[Any]] = Field(default=None, alias="correctNotes")
    missing_notes: Optional[List[Any]] = Field(default=None, alias="missingNotes")
    extra_notes: Optional[List[Any]] = Field(default=None, alias="extraNotes")
    note_precision: Optional[float] = Field(default=None, alias="notePrecision")
    note_recall: Optional[float] = Field(default=None, alias="noteRecall")
    note_f1: Optional[float] = Field(default=None, alias="noteF1")
    match_score: Optional[float] = Field(default=None, alias="matchScore")
    timing_offset_ms: Optional[float] = Field(default=None, alias="timingOffsetMs")
    timing_phase: Optional[str] = Field(default=None, alias="timingPhase")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class PracticeSession(BaseModel):
    """
    Canonical Practice Session model.
    Encapsulates all practice state, loop boundaries, tempo scaling, and guidance.
    """
    available: bool = Field(default=True)
    status: PracticeStatus = Field(default=PracticeStatus.READY)
    mode: PracticeMode = Field(default=PracticeMode.PIANO)
    
    # Timeline bounds
    start_time: float = Field(default=0.0, alias="startTime")
    end_time: float = Field(default=0.0, alias="endTime")
    current_time: float = Field(default=0.0, alias="currentTime")
    
    # Tempo & Rate scaling
    original_bpm: float = Field(..., alias="originalBpm")
    practice_bpm: float = Field(..., alias="practiceBpm")
    playback_rate: float = Field(default=1.0, alias="playbackRate")
    
    # Active Chords
    current_chord_index: int = Field(default=0, alias="currentChordIndex")
    current_chord: Optional[str] = Field(default=None, alias="currentChord")
    next_chord: Optional[str] = Field(default=None, alias="nextChord")
    guidance: Optional[PracticeChordGuidance] = None
    
    # Loop Counters
    completed_loops: int = Field(default=0, alias="completedLoops")
    current_loop: int = Field(default=1, alias="currentLoop")
    target_loops: int = Field(default=0, alias="targetLoops", description="0 = Infinite loops")
    
    # Modifiers
    simplified_level: int = Field(default=0, alias="simplifiedLevel", description="0=Original, 1=No Extensions, 2=Basic Triads, 3=Modal Anchors")
    transposition_offset: int = Field(default=0, alias="transpositionOffset", description="Semitone offset [-6, +5]")
    
    # Metadata
    section_label: str = Field(default="Practice Section", alias="sectionLabel")
    reason: Optional[str] = Field(default=None)
    note_feedback: Optional[PracticeNoteFeedbackContract] = Field(default=None, alias="noteFeedback")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


# ==============================================================================
# DETERMINISTIC STATE RESOLUTION HELPERS
# ==============================================================================

def _apply_chord_modifiers(chord_name: str, simplification_level: int, transposition_offset: int) -> str:
    """Applies simplification and transposition to a chord name without mutating source data."""
    if not chord_name or chord_name.upper() in ("N", "NO_CHORD", "NONE", ""):
        return "N"
    
    c = chord_name
    # 1. Transpose if offset != 0
    if transposition_offset != 0:
        c = transpose_chord_symbol(c, transposition_offset)
    
    # 2. Simplify if level > 0
    if simplification_level == 1:
        root, qual, bass = parse_chord_components(c)
        if root:
            is_min = qual in ("min", "m", "min7", "m7", "min9", "m9", "m7b5")
            base = f"{root}m" if is_min else root
            c = f"{base}/{bass}" if bass else base
    elif simplification_level == 2:
        c = reduce_chord_harmony(c)
    elif simplification_level == 3:
        reduced = reduce_chord_harmony(c)
        if reduced in ("Abm", "G#m"):
            c = "Am"
        elif reduced in ("F#", "Gb"):
            c = "F"
        elif reduced in ("B",):
            c = "G"
        else:
            c = reduced

    return c


def create_practice_session(
    chords: List[Dict[str, Any]],
    tempo: float,
    practice_plan: Optional[BeginnerPracticePlan] = None,
    mode: PracticeMode = PracticeMode.PIANO,
    target_loops: int = 0,
    simplification_level: int = 0,
    transposition_offset: int = 0,
    custom_bpm: Optional[float] = None,
) -> PracticeSession:
    """
    Initializes a PracticeSession instance from song data and practice plan.
    """
    from backend.theory.beginner_practice import BeginnerPracticePlan

    safe_original_bpm = max(30.0, float(tempo))
    
    plan_obj: Optional[BeginnerPracticePlan] = None
    if isinstance(practice_plan, dict):
        try:
            plan_obj = BeginnerPracticePlan.model_validate(practice_plan)
        except Exception:
            plan_obj = None
    elif isinstance(practice_plan, BeginnerPracticePlan):
        plan_obj = practice_plan

    if not chords or (plan_obj and not plan_obj.available):
        return PracticeSession(
            available=False,
            status=PracticeStatus.UNAVAILABLE,
            mode=mode,
            originalBpm=safe_original_bpm,
            practiceBpm=safe_original_bpm,
            playbackRate=1.0,
            reason="Practice session unavailable: no valid harmonic timeline."
        )

    # Determine practice section bounds
    start_time = 0.0
    end_time = float(chords[-1].get("end", chords[-1].get("time", 0.0) + 2.0)) if chords else 0.0
    section_label = "Full Song Practice"

    if plan_obj and plan_obj.recommended_section and plan_obj.recommended_section.available:
        sec = plan_obj.recommended_section
        start_time = float(sec.start)
        end_time = float(sec.end)
        section_label = sec.label or "Practice Loop"
    elif plan_obj and plan_obj.practice_loop_start is not None and plan_obj.practice_loop_end is not None:
        start_time = float(plan_obj.practice_loop_start)
        end_time = float(plan_obj.practice_loop_end)
        section_label = "Practice Loop"

    # Determine starting practice tempo
    practice_bpm = safe_original_bpm
    if custom_bpm is not None and custom_bpm > 0:
        practice_bpm = float(custom_bpm)
    elif plan_obj and plan_obj.recommended_tempo:
        practice_bpm = float(plan_obj.recommended_tempo)

    # Enforce minimum safety bounds
    min_bpm = plan_obj.minimum_tempo if plan_obj else max(30.0, safe_original_bpm * 0.45)
    practice_bpm = max(min_bpm, min(240.0, practice_bpm))
    playback_rate = round(practice_bpm / safe_original_bpm, 3)

    session = PracticeSession(
        available=True,
        status=PracticeStatus.READY,
        mode=mode,
        startTime=start_time,
        endTime=end_time,
        currentTime=start_time,
        originalBpm=safe_original_bpm,
        practiceBpm=practice_bpm,
        playbackRate=playback_rate,
        currentChordIndex=0,
        completedLoops=0,
        currentLoop=1,
        targetLoops=target_loops,
        simplifiedLevel=simplification_level,
        transpositionOffset=transposition_offset,
        sectionLabel=section_label,
    )

    # Resolve initial chord guidance at start_time
    return update_practice_session_time(session, start_time, chords)


def update_practice_session_time(
    session: PracticeSession,
    current_time: float,
    chords: List[Dict[str, Any]]
) -> PracticeSession:
    """
    Authoritative state updater. Driven by PlaybackClock current timeline time.
    Calculates:
    - Active chord interval and hold progress
    - Upcoming chord preparation and voicing
    - Loop boundary detection and wrap counts
    - Status transitions (COMPLETED when finite target_loops reached)
    """
    if not session.available or not chords:
        return session

    t = float(current_time)
    start_t = session.start_time
    end_t = session.end_time
    loop_dur = max(0.1, end_t - start_t)

    # 1. Loop Wrapping Computation (using absolute timeline time)
    if end_t > start_t and t >= end_t:
        loops_passed = int((t - start_t) // loop_dur)
        session.completed_loops = max(session.completed_loops, loops_passed)
        session.current_loop = session.completed_loops + 1

        # Check target loop completion
        if session.target_loops > 0 and session.completed_loops >= session.target_loops:
            session.status = PracticeStatus.COMPLETED
            session.current_time = end_t
            return session

        # Position within active loop
        effective_time = start_t + ((t - start_t) % loop_dur)
    else:
        effective_time = max(start_t, t)

    session.current_time = round(effective_time, 3)

    # 2. Locate active chord in timeline
    matching_idx = -1
    for i, c in enumerate(chords):
        c_start = float(c.get("time", c.get("start", 0.0)))
        c_end = float(c.get("end", c_start + 2.0))
        if c_start <= effective_time < c_end:
            matching_idx = i
            break
        elif effective_time < c_start and matching_idx == -1:
            matching_idx = max(0, i - 1)
            break

    if matching_idx == -1:
        matching_idx = len(chords) - 1

    cur_c_data = chords[matching_idx]
    c_start = float(cur_c_data.get("time", cur_c_data.get("start", 0.0)))
    c_end = float(cur_c_data.get("end", c_start + 2.0))
    raw_chord = cur_c_data.get("chord") or cur_c_data.get("chord_name") or "N"

    # Locate next chord (within section or loop wrap)
    next_c_data = None
    if matching_idx + 1 < len(chords):
        candidate_next = chords[matching_idx + 1]
        cand_start = float(candidate_next.get("time", candidate_next.get("start", 0.0)))
        if cand_start <= end_t:
            next_c_data = candidate_next
    
    # If at end of loop, next chord wraps to first chord of section
    if not next_c_data and end_t > start_t:
        for c in chords:
            if float(c.get("time", c.get("start", 0.0))) >= start_t:
                next_c_data = c
                break

    raw_next_chord = (
        next_c_data.get("chord") or next_c_data.get("chord_name") or "N"
    ) if next_c_data else None

    # Apply simplification and transposition modifiers
    cur_chord_name = _apply_chord_modifiers(raw_chord, session.simplified_level, session.transposition_offset)
    next_chord_name = _apply_chord_modifiers(raw_next_chord, session.simplified_level, session.transposition_offset) if raw_next_chord else None

    # Compute progress within active chord
    chord_dur = max(0.01, c_end - c_start)
    chord_elapsed = max(0.0, min(chord_dur, effective_time - c_start))
    progress = round(chord_elapsed / chord_dur, 3)
    time_until_next = round(max(0.0, c_end - effective_time), 3)

    # Voicings & guidance
    from backend.theory.beginner_practice import classify_difficulty_category

    cur_voicing = voice_chord(cur_chord_name) if cur_chord_name != "N" else None
    next_voicing = voice_chord(next_chord_name) if (next_chord_name and next_chord_name != "N") else None
    
    d_score = cur_voicing.get("difficultyScore", 0.0) if cur_voicing else 0.0
    d_cat = classify_difficulty_category(d_score, cur_chord_name)
    simp_sugg = reduce_chord_harmony(cur_chord_name) if cur_chord_name != reduce_chord_harmony(cur_chord_name) else None

    guidance = PracticeChordGuidance(
        currentChord=cur_chord_name,
        nextChord=next_chord_name,
        currentChordStart=round(c_start, 3),
        currentChordEnd=round(c_end, 3),
        progressWithinChord=progress,
        timeUntilNextChord=time_until_next,
        currentVoicing=cur_voicing,
        nextVoicing=next_voicing,
        nextHandAssignment=next_voicing.get("handAssignment") if next_voicing else None,
        difficultyScore=round(d_score, 3),
        difficultyCategory=d_cat,
        suggestedSimplification=simp_sugg,
    )

    # Note feedback contract
    notes = [n["note"] for n in cur_voicing.get("rightHand", [])] if cur_voicing else []
    midi_notes = cur_voicing.get("midiNotes", []) if cur_voicing else []
    root, qual, _ = parse_chord_components(cur_chord_name)

    feedback = PracticeNoteFeedbackContract(
        expectedNotes=notes,
        expectedMidi=midi_notes,
        expectedChord=cur_chord_name,
        expectedRoot=root or cur_chord_name,
        expectedQuality=qual or "maj",
        detectedNotes=None,
        detectedChord=None,
        matchScore=None,
    )

    session.current_chord_index = matching_idx
    session.current_chord = cur_chord_name
    session.next_chord = next_chord_name
    session.guidance = guidance
    session.note_feedback = feedback

    return session


def seek_practice_session(
    session: PracticeSession,
    target_time: float,
    chords: List[Dict[str, Any]]
) -> PracticeSession:
    """Seeks to a target time and refreshes chord guidance immediately."""
    return update_practice_session_time(session, target_time, chords)


def pause_practice_session(session: PracticeSession) -> PracticeSession:
    """Freezes practice session state into PAUSED."""
    if session.status == PracticeStatus.PLAYING:
        session.status = PracticeStatus.PAUSED
    return session


def resume_practice_session(session: PracticeSession) -> PracticeSession:
    """Resumes practice session state into PLAYING."""
    if session.status in (PracticeStatus.PAUSED, PracticeStatus.READY):
        session.status = PracticeStatus.PLAYING
    return session


def reset_practice_session(
    session: PracticeSession,
    chords: List[Dict[str, Any]]
) -> PracticeSession:
    """Resets practice session to loop start with completed_loops = 0."""
    session.completed_loops = 0
    session.current_loop = 1
    session.status = PracticeStatus.READY
    return update_practice_session_time(session, session.start_time, chords)


def set_practice_tempo(
    session: PracticeSession,
    target_bpm: float
) -> PracticeSession:
    """Safely updates practice tempo and recomputes playbackRate."""
    min_safe = max(20.0, session.original_bpm * 0.30)
    session.practice_bpm = max(min_safe, min(240.0, float(target_bpm)))
    session.playback_rate = round(session.practice_bpm / session.original_bpm, 3)
    return session


def set_practice_simplification(
    session: PracticeSession,
    level: int,
    chords: List[Dict[str, Any]]
) -> PracticeSession:
    """Sets simplification level (0 to 3) and refreshes active chord state."""
    session.simplified_level = max(0, min(3, int(level)))
    return update_practice_session_time(session, session.current_time, chords)


def set_practice_transposition(
    session: PracticeSession,
    semitone_offset: int,
    chords: List[Dict[str, Any]]
) -> PracticeSession:
    """Sets global transposition offset (-6 to +5) and refreshes active chord state."""
    session.transposition_offset = max(-6, min(5, int(semitone_offset)))
    return update_practice_session_time(session, session.current_time, chords)
