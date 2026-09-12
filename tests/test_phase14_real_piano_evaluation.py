"""
tests/test_phase14_real_piano_evaluation.py

Unit & Integration Tests for HotChords Phase 14 Real-Piano Evaluation Harness:
- Ground-truth schema & Pydantic models validation
- Evaluator note precision, recall, and F1 calculations
- Onset timing error & tolerance curve generation
- Pitch-class & exact chord note-set metrics
- Multi-dimensional breakdown categories
- Synthetic acoustic fixture evaluation
- Strict enforcement of REAL_PIANO_GROUND_TRUTH = 'NOT_AVAILABLE' status
"""

import pytest
import numpy as np

from backend.benchmarks.real_piano_evaluation import (
    REAL_PIANO_GROUND_TRUTH,
    REAL_ACOUSTIC_ACCURACY,
    PianoType,
    MicPosition,
    RoomCondition,
    VelocityDynamic,
    PedalCondition,
    PlayerStyle,
    GroundTruthNote,
    GroundTruthChord,
    RealPianoRecording,
    NoteMatchingMetrics,
    ChordLevelMetrics,
    RealPianoEvaluator,
)
from backend.analysis.test_signals import generate_piano_tone, generate_chord_signal, midi_to_freq


class TestPhase14RealPianoEvaluation:

    def test_ground_truth_status_constants(self):
        """Verify explicit and honest status constants."""
        assert REAL_PIANO_GROUND_TRUTH == "NOT_AVAILABLE"
        assert REAL_ACOUSTIC_ACCURACY == "NOT_ESTABLISHED"

    def test_schema_and_models(self):
        """Verify ground-truth note, chord, and recording schema."""
        note = GroundTruthNote(onset=1.0, offset=2.5, midi=60, velocity=75)
        assert note.pitch_name == "C4"
        assert note.midi == 60

        chord = GroundTruthChord(start=1.0, end=3.0, chord="C", midi_notes=[60, 64, 67])
        assert chord.chord == "C"
        assert len(chord.midi_notes) == 3

        rec = RealPianoRecording(
            recording_id="REC_001",
            audio_path="test_audio.wav",
            piano_type=PianoType.ACOUSTIC_UPRIGHT,
            mic_position=MicPosition.MEDIUM_PRACTICE,
            room_condition=RoomCondition.NORMAL_ROOM,
            velocity_dynamic=VelocityDynamic.MF,
            pedal_condition=PedalCondition.NO_PEDAL,
            player_style=PlayerStyle.CLEAN_PRACTICE,
            notes=[note],
            chords=[chord]
        )
        assert rec.recording_id == "REC_001"
        assert rec.piano_type == PianoType.ACOUSTIC_UPRIGHT
        assert len(rec.notes) == 1

    def test_evaluator_perfect_single_note_match(self):
        """Verify evaluator produces perfect metrics on synthetic tone."""
        sr = 22050
        duration = 2.0
        tone = generate_piano_tone(midi_to_freq(60), duration=duration, sr=sr)

        # Ground truth onset at start
        gt_notes = [GroundTruthNote(onset=0.0, offset=2.0, midi=60)]
        gt_chords = [GroundTruthChord(start=0.0, end=2.0, chord="C", midi_notes=[60])]

        evaluator = RealPianoEvaluator(sample_rate=sr)
        result = evaluator.evaluate_audio_signal(tone, gt_notes, gt_chords, is_synthetic=True)

        assert result["isSynthetic"] is True
        assert result["groundTruthStatus"] == "NOT_AVAILABLE" # Marked synthetic
        note_m = result["noteMetrics"]
        assert note_m["precision"] >= 0.90
        assert note_m["recall"] >= 0.90
        assert note_m["f1Score"] >= 0.90
        assert "50ms" in note_m["toleranceCurve"]

    def test_evaluator_polyphonic_triad_match(self):
        """Verify polyphonic triad evaluation."""
        sr = 22050
        duration = 2.0
        chord_audio = generate_chord_signal([60, 64, 67], duration=duration, sr=sr)

        gt_notes = [
            GroundTruthNote(onset=0.0, offset=2.0, midi=60),
            GroundTruthNote(onset=0.0, offset=2.0, midi=64),
            GroundTruthNote(onset=0.0, offset=2.0, midi=67),
        ]
        gt_chords = [GroundTruthChord(start=0.0, end=2.0, chord="C", midi_notes=[60, 64, 67])]

        evaluator = RealPianoEvaluator(sample_rate=sr)
        result = evaluator.evaluate_audio_signal(chord_audio, gt_notes, gt_chords, is_synthetic=True)

        note_m = result["noteMetrics"]
        assert note_m["truePositives"] >= 2
        assert note_m["f1Score"] >= 0.75
        assert result["chordMetrics"]["exactNoteSetAccuracy"] >= 0.50

    def test_evaluator_empty_audio_handling(self):
        """Verify graceful handling of empty or silent audio."""
        sr = 22050
        evaluator = RealPianoEvaluator(sample_rate=sr)
        
        # Empty signal
        empty_sig = np.zeros(100, dtype=np.float32)
        res = evaluator.evaluate_audio_signal(empty_sig, [], [], is_synthetic=True)
        assert res["totalFrames"] == 0
        assert res["noteMetrics"]["f1Score"] == 0.0

    def test_evaluator_onset_tolerance_curve(self):
        """Verify tolerance curve computation across multiple windows."""
        evaluator = RealPianoEvaluator()
        
        detected_frames = [
            {"time": 0.040, "midis": {60}, "status": "DETECTED"},
            {"time": 0.063, "midis": {60}, "status": "DETECTED"},
            {"time": 0.086, "midis": {60}, "status": "DETECTED"},
        ]
        gt_notes = [GroundTruthNote(onset=0.0, offset=0.5, midi=60)]
        
        metrics = evaluator.calculate_note_metrics(detected_frames, gt_notes, duration_s=1.0)
        assert metrics.true_positives == 1
        assert metrics.onset_mae_ms == 40.0
        assert metrics.tolerance_curve["20ms"] == 0.0 # 40ms > 20ms
        assert metrics.tolerance_curve["50ms"] == 1.0 # 40ms <= 50ms
        assert metrics.tolerance_curve["100ms"] == 1.0
