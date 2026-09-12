"""
tests/test_phase11_practice_feedback.py

Unit Tests for Real-Time Practice Feedback & Matching Engine (Phase 11):
- Exact note vs Pitch-class matching
- Missing, extra, and correct notes
- Precision, recall, and F1 calculations
- Feedback statuses (MATCH, PARTIAL, WRONG_NOTES, NO_INPUT, LOW_CONFIDENCE)
- Chord transition grace windows (PREPARING, ACTIVE, TRANSITION)
- Sustain decay hysteresis
- PlaybackClock temporal authority & timeline immutability
- Permission / Hardware failure states
- Backward compatibility
"""

import pytest
from backend.theory.practice_feedback import (
    evaluate_note_matching,
    compute_practice_feedback,
    MatchingMode,
    FeedbackStatus,
    TimingPhase,
)
from backend.models.practice_session import (
    PracticeSession,
    PracticeNoteFeedbackContract,
    create_practice_session,
    update_practice_session_time,
)
from backend.models.timeline import SongTimeline, ChordEvent, SongMetadata


class TestPhase11PracticeFeedback:

    def test_exact_chord_match(self):
        """3. Exact C Major chord match (C4, E4, G4 = 60, 64, 67)."""
        expected = [60, 64, 67]
        observed = [60, 64, 67]

        res = compute_practice_feedback(
            expected_chord="C",
            expected_midi=expected,
            observed_midi=observed,
            observed_confidence=0.95,
            input_status="DETECTED",
            matching_mode=MatchingMode.EXACT_NOTE_MATCH,
        )

        assert res["feedbackStatus"] == "MATCH"
        assert res["comparison"]["notePrecision"] == 1.0
        assert res["comparison"]["noteRecall"] == 1.0
        assert res["comparison"]["noteF1"] == 1.0
        assert res["comparison"]["correctNotes"] == [60, 64, 67]
        assert len(res["comparison"]["missingNotes"]) == 0
        assert len(res["comparison"]["extraNotes"]) == 0

    def test_octave_shifted_chord_matching(self):
        """10. Octave shifted chord: C3, E3, G3 (48, 52, 55) vs expected C4, E4, G4 (60, 64, 67)."""
        expected = [60, 64, 67]
        observed = [48, 52, 55]  # One octave lower

        # Under EXACT_NOTE_MATCH: Mismatch (different MIDI octaves)
        exact_res = compute_practice_feedback(
            expected_chord="C",
            expected_midi=expected,
            observed_midi=observed,
            matching_mode=MatchingMode.EXACT_NOTE_MATCH,
        )
        assert exact_res["feedbackStatus"] == "WRONG_NOTES"
        assert exact_res["comparison"]["noteRecall"] == 0.0

        # Under PITCH_CLASS_MATCH: Exact Match! (C=0, E=4, G=7)
        pc_res = compute_practice_feedback(
            expected_chord="C",
            expected_midi=expected,
            observed_midi=observed,
            matching_mode=MatchingMode.PITCH_CLASS_MATCH,
        )
        assert pc_res["feedbackStatus"] == "MATCH"
        assert pc_res["comparison"]["noteRecall"] == 1.0
        assert pc_res["comparison"]["notePrecision"] == 1.0
        assert pc_res["comparison"]["correctNotes"] == ["C", "E", "G"]

    def test_missing_note_partial_match(self):
        """11. Missing G4 in C Major triad -> PARTIAL feedback."""
        expected = [60, 64, 67]  # C4, E4, G4
        observed = [60, 64]      # C4, E4

        res = compute_practice_feedback(
            expected_chord="C",
            expected_midi=expected,
            observed_midi=observed,
            matching_mode=MatchingMode.EXACT_NOTE_MATCH,
        )

        assert res["feedbackStatus"] == "PARTIAL"
        assert res["comparison"]["correctNotes"] == [60, 64]
        assert res["comparison"]["missingNotes"] == [67]
        assert len(res["comparison"]["extraNotes"]) == 0
        assert res["comparison"]["notePrecision"] == 1.0
        assert abs(res["comparison"]["noteRecall"] - 0.667) < 0.01

    def test_extra_note_detection(self):
        """12. Extra note D4 (62) played during C Major triad."""
        expected = [60, 64, 67]      # C4, E4, G4
        observed = [60, 62, 64, 67]  # C4, D4, E4, G4

        res = compute_practice_feedback(
            expected_chord="C",
            expected_midi=expected,
            observed_midi=observed,
            matching_mode=MatchingMode.EXACT_NOTE_MATCH,
        )

        assert res["comparison"]["correctNotes"] == [60, 64, 67]
        assert res["comparison"]["extraNotes"] == [62]
        assert res["comparison"]["missingNotes"] == []
        assert res["comparison"]["noteRecall"] == 1.0
        assert res["comparison"]["notePrecision"] == 0.75

    def test_wrong_chord_detection(self):
        """13. Playing D minor (D4, F4, A4 = 62, 65, 69) when C major expected -> WRONG_NOTES."""
        expected = [60, 64, 67]
        observed = [62, 65, 69]

        res = compute_practice_feedback(
            expected_chord="C",
            expected_midi=expected,
            observed_midi=observed,
            matching_mode=MatchingMode.EXACT_NOTE_MATCH,
        )

        assert res["feedbackStatus"] == "WRONG_NOTES"
        assert res["comparison"]["noteRecall"] == 0.0
        assert len(res["comparison"]["correctNotes"]) == 0
        assert res["comparison"]["missingNotes"] == [60, 64, 67]

    def test_silence_no_input(self):
        """14. Silence / zero notes -> NO_INPUT feedback."""
        res = compute_practice_feedback(
            expected_chord="C",
            expected_midi=[60, 64, 67],
            observed_midi=[],
            input_status="NO_INPUT",
        )
        assert res["feedbackStatus"] == "NO_INPUT"

    def test_low_confidence_feedback(self):
        """20. Low confidence observed audio -> LOW_CONFIDENCE status."""
        res = compute_practice_feedback(
            expected_chord="C",
            expected_midi=[60, 64, 67],
            observed_midi=[60, 64],
            observed_confidence=0.25,
            input_status="DETECTED",
        )
        assert res["feedbackStatus"] == "LOW_CONFIDENCE"

    def test_permission_and_hardware_failure(self):
        """27. Input permission denied or hardware unavailable returns safe error statuses."""
        res_perm = compute_practice_feedback(
            expected_chord="C",
            expected_midi=[60, 64, 67],
            observed_midi=[],
            input_status="INPUT_PERMISSION_DENIED",
        )
        assert res_perm["feedbackStatus"] == "INPUT_PERMISSION_DENIED"

        res_unavail = compute_practice_feedback(
            expected_chord="C",
            expected_midi=[60, 64, 67],
            observed_midi=[],
            input_status="INPUT_UNAVAILABLE",
        )
        assert res_unavail["feedbackStatus"] == "INPUT_UNAVAILABLE"

    def test_chord_transition_grace_and_sustain(self):
        """19 & 20. Chord transition grace window & previous chord sustain decay tolerance."""
        # Transition from C major [60, 64, 67] to G major [55, 59, 62] at t = 2.0s
        # At t = 2.05s (inside grace window 0.25s), user plays G major [55, 59, 62], while G4 (67) is still ringing
        expected_g = [55, 59, 62]
        observed = [55, 59, 62, 67]  # G major + ringing G4 from previous C major
        prev_c = [60, 64, 67]

        # In transition with previous chord context: 67 is not penalized as an extra note
        res = compute_practice_feedback(
            expected_chord="G",
            expected_midi=expected_g,
            observed_midi=observed,
            playback_time=2.05,
            chord_start=2.0,
            chord_end=4.0,
            grace_window_seconds=0.25,
            previous_chord_midi=prev_c,
        )

        assert res["timing"]["isTransition"] is True
        assert res["timing"]["phase"] == "TRANSITION"
        # 67 was filtered by sustain decay tolerance
        assert 67 not in res["comparison"]["extraNotes"]
        assert res["comparison"]["notePrecision"] == 1.0
        assert res["feedbackStatus"] == "MATCH"

    def test_playback_clock_authority_and_timeline_immutability(self):
        """21 & 22. Microphone observation NEVER mutates SongTimeline or PlaybackClock."""
        timeline = SongTimeline(
            duration=10.0,
            metadata=SongMetadata(
                title="Test Song",
                tempo=120.0,
                key="C",
                scale="major",
                duration=10.0,
            ),
            original_chords=[
                ChordEvent(startTime=0.0, endTime=2.0, chordName="C"),
                ChordEvent(startTime=2.0, endTime=4.0, chordName="G"),
            ],
            confidence=0.95,
        )

        session = create_practice_session(
            chords=[
                {"name": "C", "start": 0.0, "end": 2.0},
                {"name": "G", "start": 2.0, "end": 4.0},
            ],
            tempo=120.0,
        )
        orig_chord_name = session.current_chord
        orig_rate = session.playback_rate

        # Simulate observed microphone wrong notes
        feedback = compute_practice_feedback(
            expected_chord=session.current_chord,
            expected_midi=[60, 64, 67],
            observed_midi=[61, 65, 68],  # Completely wrong notes (C# major)
            input_status="DETECTED",
        )

        assert feedback["feedbackStatus"] == "WRONG_NOTES"

        # Invariant: session and timeline state remain completely unmodified
        assert session.current_chord == orig_chord_name
        assert session.playback_rate == orig_rate
        assert timeline.original_chords[0].chord_name == "C"
        assert timeline.original_chords[1].chord_name == "G"

    def test_backward_compatibility_practice_note_feedback_contract(self):
        """25. Backward compatibility of PracticeNoteFeedbackContract."""
        contract = PracticeNoteFeedbackContract(
            expectedChord="C",
            expectedRoot="C",
            expectedQuality="maj",
            expectedNotes=["C4", "E4", "G4"],
            expectedMidi=[60, 64, 67],
            inputStatus="DETECTED",
            feedbackStatus="MATCH",
            detectedNotes=["C4", "E4", "G4"],
            detectedMidi=[60, 64, 67],
            correctNotes=[60, 64, 67],
            notePrecision=1.0,
            noteRecall=1.0,
            noteF1=1.0,
        )

        dump = contract.model_dump(by_alias=True)
        assert dump["expectedChord"] == "C"
        assert dump["feedbackStatus"] == "MATCH"
        assert dump["notePrecision"] == 1.0
        assert dump["expectedMidi"] == [60, 64, 67]
