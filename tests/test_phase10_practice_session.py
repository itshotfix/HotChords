"""
tests/test_phase10_practice_session.py

Phase 10 Test Suite: Interactive Beginner Practice Mode & Real-Time Chord Guidance.
Tests all 23 core scenarios:
1. C -> G -> Am -> F (Pop Axis)
2. Am -> F -> C -> G (Minor Axis)
3. Practice tempo slower than original
4. Canonical timestamps unchanged when tempo changes
5. Current chord selection
6. Next chord selection
7. Chord boundary behavior
8. Pause/resume state transitions
9. Loop wrap behavior
10. Multiple loop completion counts
11. Reset behavior
12. Simplified practice (Levels 1-3)
13. Transposed practice (Offsets)
14. Slash chords (C/E, G/B, D/F#)
15. N / no-chord handling
16. One-chord vamp handling (practiceSection=True, fourChordLoop=False)
17. No reliable practice section handling
18. Through-composed progression handling
19. Empty audio result handling
20. Low-confidence result handling
21. Playback mode compatibility (ORIGINAL vs PIANO)
22. Backward compatibility of SongTimeline and API contracts
23. Single authoritative clock guarantee
"""

import pytest
from backend.models.practice_session import (
    PracticeStatus,
    PracticeMode,
    PracticeSession,
    PracticeChordGuidance,
    PracticeNoteFeedbackContract,
    create_practice_session,
    update_practice_session_time,
    seek_practice_session,
    pause_practice_session,
    resume_practice_session,
    reset_practice_session,
    set_practice_tempo,
    set_practice_simplification,
    set_practice_transposition,
)
from backend.theory.beginner_practice import (
    BeginnerPracticePlan,
    generate_beginner_practice_plan,
)
from backend.models.timeline import SongTimeline
from backend.models.analysis_types import (
    FourChordLoopResult,
    StructureAnalysisResult,
    AudioStatus,
    DetectionReliability,
)


class TestPhase10PracticeSession:

    def test_01_pop_axis_practice(self):
        """1. C -> G -> Am -> F progression practice."""
        chords = [
            {"chord": "C", "time": 0.0, "end": 2.0},
            {"chord": "G", "time": 2.0, "end": 4.0},
            {"chord": "Am", "time": 4.0, "end": 6.0},
            {"chord": "F", "time": 6.0, "end": 8.0},
        ]
        plan = generate_beginner_practice_plan(chords, tempo=120.0, duration=8.0)
        session = create_practice_session(chords, tempo=120.0, practice_plan=plan)

        assert session.available is True
        assert session.status == PracticeStatus.READY
        assert session.current_chord == "C"
        assert session.next_chord == "G"
        assert session.start_time == 0.0

    def test_02_minor_axis_practice(self):
        """2. Am -> F -> C -> G minor axis progression practice."""
        chords = [
            {"chord": "Am", "time": 0.0, "end": 2.0},
            {"chord": "F", "time": 2.0, "end": 4.0},
            {"chord": "C", "time": 4.0, "end": 6.0},
            {"chord": "G", "time": 6.0, "end": 8.0},
        ]
        plan = generate_beginner_practice_plan(chords, tempo=100.0, duration=8.0)
        session = create_practice_session(chords, tempo=100.0, practice_plan=plan)

        assert session.available is True
        assert session.current_chord == "Am"
        assert session.next_chord == "F"

    def test_03_practice_tempo_slower_than_original(self):
        """3. Practice tempo is scaled slower than original BPM."""
        chords = [
            {"chord": "C#m7", "time": 0.0, "end": 2.0},
            {"chord": "Abm", "time": 2.0, "end": 4.0},
            {"chord": "A", "time": 4.0, "end": 6.0},
            {"chord": "B", "time": 6.0, "end": 8.0},
        ]
        plan = generate_beginner_practice_plan(chords, tempo=120.0, duration=8.0)
        session = create_practice_session(chords, tempo=120.0, practice_plan=plan)

        assert session.practice_bpm < session.original_bpm
        assert session.playback_rate < 1.0
        assert session.playback_rate == pytest.approx(session.practice_bpm / session.original_bpm, rel=1e-2)

    def test_04_canonical_timestamps_unchanged_on_tempo_change(self):
        """4. Canonical timestamps remain in original song time domain when tempo changes."""
        chords = [
            {"chord": "C", "time": 10.5, "end": 14.5},
            {"chord": "G", "time": 14.5, "end": 18.5},
        ]
        session = create_practice_session(chords, tempo=120.0)
        set_practice_tempo(session, target_bpm=60.0)

        # Timestamps in guidance must match canonical time, not scaled time
        update_practice_session_time(session, current_time=12.0, chords=chords)
        assert session.guidance.current_chord_start == 10.5
        assert session.guidance.current_chord_end == 14.5
        assert session.guidance.progress_within_chord == pytest.approx(0.375, abs=0.01)

    def test_05_current_chord_selection(self):
        """5. Current chord matches timeline time."""
        chords = [
            {"chord": "C", "time": 0.0, "end": 2.0},
            {"chord": "G", "time": 2.0, "end": 4.0},
            {"chord": "Am", "time": 4.0, "end": 6.0},
        ]
        session = create_practice_session(chords, tempo=100.0)

        update_practice_session_time(session, current_time=3.1, chords=chords)
        assert session.current_chord == "G"
        assert session.current_chord_index == 1

    def test_06_next_chord_selection(self):
        """6. Next chord is identified with upcoming voicing and hand assignments."""
        chords = [
            {"chord": "C", "time": 0.0, "end": 2.0},
            {"chord": "G", "time": 2.0, "end": 4.0},
            {"chord": "Am", "time": 4.0, "end": 6.0},
        ]
        session = create_practice_session(chords, tempo=100.0)

        update_practice_session_time(session, current_time=1.0, chords=chords)
        assert session.next_chord == "G"
        assert session.guidance.next_voicing is not None
        assert "rightHand" in session.guidance.next_voicing

    def test_07_chord_boundary_behavior(self):
        """7. Boundary conditions at exact start, middle, and end of chord interval."""
        chords = [
            {"chord": "Dm", "time": 10.0, "end": 14.0},
            {"chord": "G7", "time": 14.0, "end": 18.0},
        ]
        session = create_practice_session(chords, tempo=100.0)

        # Exact start
        update_practice_session_time(session, 10.0, chords)
        assert session.current_chord == "Dm"
        assert session.guidance.progress_within_chord == 0.0

        # Exact middle
        update_practice_session_time(session, 12.0, chords)
        assert session.current_chord == "Dm"
        assert session.guidance.progress_within_chord == 0.5
        assert session.guidance.time_until_next_chord == 2.0

        # Exact transition point (14.0 -> G7)
        update_practice_session_time(session, 14.0, chords)
        assert session.current_chord == "G7"

    def test_08_pause_resume_state_transitions(self):
        """8. Pause freezes state; resume continues playback."""
        session = create_practice_session([{"chord": "C", "time": 0.0, "end": 4.0}], tempo=100.0)
        resume_practice_session(session)
        assert session.status == PracticeStatus.PLAYING

        pause_practice_session(session)
        assert session.status == PracticeStatus.PAUSED

        resume_practice_session(session)
        assert session.status == PracticeStatus.PLAYING

    def test_09_loop_wrap_behavior(self):
        """9. Looping from practiceLoop.end wraps back to start without drift."""
        chords = [
            {"chord": "C", "time": 0.0, "end": 2.0},
            {"chord": "G", "time": 2.0, "end": 4.0},
        ]
        session = create_practice_session(chords, tempo=100.0)
        session.start_time = 0.0
        session.end_time = 4.0

        # Past loop boundary (time = 5.0 -> wraps to 1.0)
        update_practice_session_time(session, current_time=5.0, chords=chords)
        assert session.completed_loops == 1
        assert session.current_time == 1.0
        assert session.current_chord == "C"

    def test_10_multiple_loop_completion_counts(self):
        """10. Loop counts accumulate accurately across multiple iterations."""
        chords = [{"chord": "C", "time": 0.0, "end": 4.0}]
        session = create_practice_session(chords, tempo=100.0, target_loops=3)
        session.start_time = 0.0
        session.end_time = 4.0

        # Loop 1
        update_practice_session_time(session, 4.5, chords)
        assert session.completed_loops == 1
        assert session.status == PracticeStatus.READY

        # Loop 3 completion
        update_practice_session_time(session, 12.0, chords)
        assert session.completed_loops == 3
        assert session.status == PracticeStatus.COMPLETED

    def test_11_reset_behavior(self):
        """11. Reset clears completed loops and restores start time without mutating timeline."""
        chords = [{"chord": "C", "time": 0.0, "end": 4.0}]
        session = create_practice_session(chords, tempo=100.0)
        update_practice_session_time(session, 10.0, chords)
        assert session.completed_loops > 0

        reset_practice_session(session, chords)
        assert session.completed_loops == 0
        assert session.current_loop == 1
        assert session.current_time == session.start_time
        assert session.status == PracticeStatus.READY

    def test_12_simplified_practice_levels(self):
        """12. Simplification levels 1-3 provide simplified chord guidance non-destructively."""
        chords = [{"chord": "C:maj7", "time": 0.0, "end": 4.0}]
        session = create_practice_session(chords, tempo=100.0)

        # Level 0 (Original)
        assert session.current_chord == "C:maj7"

        # Level 1 (Extension removal)
        set_practice_simplification(session, level=1, chords=chords)
        assert session.current_chord == "C"

        # Minor chords must never become major
        chords_min = [{"chord": "Am7", "time": 0.0, "end": 4.0}]
        session_min = create_practice_session(chords_min, tempo=100.0)
        set_practice_simplification(session_min, level=1, chords=chords_min)
        assert session_min.current_chord == "Am"

    def test_13_transposed_practice(self):
        """13. Global semitone transposition shifts roots & voicings without re-running MIR."""
        chords = [
            {"chord": "C", "time": 0.0, "end": 2.0},
            {"chord": "Am", "time": 2.0, "end": 4.0},
        ]
        session = create_practice_session(chords, tempo=100.0)
        set_practice_transposition(session, semitone_offset=2, chords=chords)

        assert session.current_chord == "D"
        assert session.next_chord == "Bm"

    def test_14_slash_chords(self):
        """14. Inverted slash chords (C/E, G/B, D/F#) preserved in guidance and transposition."""
        chords = [{"chord": "C/E", "time": 0.0, "end": 2.0}]
        session = create_practice_session(chords, tempo=100.0)
        assert session.current_chord == "C/E"

        # Transpose +2 -> D/F#
        set_practice_transposition(session, semitone_offset=2, chords=chords)
        assert session.current_chord == "D/F#"

    def test_15_no_chord_handling(self):
        """15. N / NO_CHORD symbols handled cleanly without fabricating chords."""
        chords = [
            {"chord": "N", "time": 0.0, "end": 2.0},
            {"chord": "C", "time": 2.0, "end": 4.0},
        ]
        session = create_practice_session(chords, tempo=100.0)
        assert session.current_chord == "N"
        assert session.guidance.current_voicing is None
        assert session.next_chord == "C"

    def test_16_one_chord_vamp_handling(self):
        """16. One-chord vamp provides practiceSection=True while fourChordLoop=False."""
        chords = [{"chord": "Gm", "time": 0.0, "end": 10.0}]
        plan = generate_beginner_practice_plan(chords, tempo=140.0, duration=10.0)

        assert plan.available is True
        assert plan.four_chord_loop_available is False
        assert plan.practice_section_available is True
        assert plan.recommended_section.reason == "ONE_CHORD_VAMP"

        session = create_practice_session(chords, tempo=140.0, practice_plan=plan)
        assert session.available is True
        assert session.current_chord == "Gm"

    def test_17_no_reliable_practice_section(self):
        """17. No fabricated loops when progression lacks structure or repetition."""
        chords = [
            {"chord": "C", "time": 0.0, "end": 2.0},
            {"chord": "D", "time": 2.0, "end": 4.0},
            {"chord": "E", "time": 4.0, "end": 6.0},
            {"chord": "F", "time": 6.0, "end": 8.0},
            {"chord": "G", "time": 8.0, "end": 10.0},
            {"chord": "A", "time": 10.0, "end": 12.0},
        ]
        # With no four_chord_loop and no repeating section
        plan = generate_beginner_practice_plan(chords, tempo=100.0, duration=12.0)
        assert plan.four_chord_loop_available is False
        assert plan.practice_section_available is False
        assert plan.recommended_section.reason == "NO_RELIABLE_PRACTICE_SECTION"

    def test_18_through_composed_progression(self):
        """18. Through-composed music does not fabricate fake repeating 4-chord loop."""
        chords = [
            {"chord": "F#m", "time": 0.0, "end": 2.0},
            {"chord": "B", "time": 2.0, "end": 4.0},
            {"chord": "E", "time": 4.0, "end": 6.0},
            {"chord": "A", "time": 6.0, "end": 8.0},
            {"chord": "D", "time": 8.0, "end": 10.0},
        ]
        plan = generate_beginner_practice_plan(chords, tempo=100.0, duration=10.0)
        assert plan.four_chord_loop_available is False

    def test_19_empty_audio_result_handling(self):
        """19. Empty or zero duration audio safely disables practice session."""
        session = create_practice_session([], tempo=120.0)
        assert session.available is False
        assert session.status == PracticeStatus.UNAVAILABLE

    def test_20_low_confidence_result_handling(self):
        """20. Low confidence audio throttles practice tempo with cautionary notes."""
        chords = [{"chord": "C", "time": 0.0, "end": 4.0}]
        rel = DetectionReliability(overall=0.35, harmonic=0.30, timing=0.40, sourceAgreement=0.30)
        plan = generate_beginner_practice_plan(chords, tempo=120.0, duration=4.0, reliability=rel)

        assert plan.tempo_reduction_factor <= 0.60
        assert plan.recommended_tempo <= 72.0

    def test_21_playback_mode_compatibility(self):
        """21. ORIGINAL and PIANO modes both supported with identical state resolution."""
        chords = [{"chord": "C", "time": 0.0, "end": 4.0}]
        orig_session = create_practice_session(chords, tempo=120.0, mode=PracticeMode.ORIGINAL)
        piano_session = create_practice_session(chords, tempo=120.0, mode=PracticeMode.PIANO)

        assert orig_session.mode == PracticeMode.ORIGINAL
        assert piano_session.mode == PracticeMode.PIANO
        assert orig_session.current_chord == piano_session.current_chord

    def test_22_backward_compatibility_timeline_and_api(self):
        """22. SongTimeline.create_practice_session preserves existing API contract."""
        analysis_dict = {
            "duration": 8.0,
            "tempo": 120.0,
            "key": "C",
            "scale": "Major",
            "chords": [
                {"time": 0.0, "end": 4.0, "chord": "C", "root": "C", "quality": "maj"},
                {"time": 4.0, "end": 8.0, "chord": "G", "root": "G", "quality": "maj"},
            ],
            "practice": {
                "available": True,
                "originalTempo": 120.0,
                "recommendedTempo": 102.0,
                "minimumTempo": 50.0,
                "tempoReductionFactor": 0.85,
                "uniqueChords": ["C", "G"],
            }
        }
        timeline = SongTimeline.from_analysis_dict(analysis_dict)
        session = timeline.create_practice_session()

        assert session.available is True
        assert session.practice_bpm == 102.0
        assert session.current_chord == "C"

    def test_23_single_authoritative_clock_guarantee(self):
        """23. Practice session updates deterministically from a single external timeline timestamp."""
        chords = [{"chord": "C", "time": 0.0, "end": 4.0}]
        session = create_practice_session(chords, tempo=100.0)

        # Calling update repeatedly with same timestamp yields deterministic identical state
        s1 = update_practice_session_time(session, 2.0, chords)
        p1 = s1.guidance.progress_within_chord
        s2 = update_practice_session_time(session, 2.0, chords)
        p2 = s2.guidance.progress_within_chord

        assert p1 == p2 == 0.5
