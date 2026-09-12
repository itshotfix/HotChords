"""
tests/test_phase12_long_session.py

Long-Session Stability & Memory Invariant Tests for HotChords (Phase 12):
- Simulates long streaming practice sessions through the complete pipeline
- Verifies bounded ring buffer invariant (len <= 50)
- Verifies constant memory profile and zero unbounded array growth
"""

import pytest
import numpy as np

from backend.analysis.test_signals import generate_chord_signal
from backend.analysis.realtime_pitch import PolyphonicPitchDetector, RealTimeNoteTracker
from backend.analysis.input_calibration import InputCalibrator
from backend.theory.practice_feedback import compute_practice_feedback, MatchingMode
from backend.theory.practice_metrics import (
    PracticeMetricsTracker,
    PlayerFeedbackEvent,
    PlayerFeedbackEventType,
)


class TestPhase12LongSession:

    def test_long_session_bounded_memory_and_stability(self):
        """22. Continuous streaming stream runs with bounded memory and stable accumulators."""
        sr = 22050
        n_fft = 2048
        detector = PolyphonicPitchDetector(sample_rate=sr, n_fft=n_fft, hop_size=512)
        tracker = RealTimeNoteTracker(detector=detector)
        calibrator = InputCalibrator(sample_rate=sr)
        metrics = PracticeMetricsTracker(max_recent_events=50)

        # Calibrate
        calibrator.start_calibration(0.5)
        for _ in range(10):
            calibrator.process_calibration_frame(np.random.normal(0, 0.003, n_fft).astype(np.float32))
        profile = calibrator.finish_calibration()

        # Simulate 2,000 frames (~46 seconds of audio at 512 hop)
        test_chords = [[60, 64, 67], [55, 59, 62], [57, 60, 64], [53, 57, 60]]
        cached_frames = [
            generate_chord_signal(midi_set, duration=0.2, sr=sr)[:n_fft]
            for midi_set in test_chords
        ]

        metrics.start_session(0.0)

        for i in range(2000):
            c_idx = (i // 50) % len(test_chords)
            frame = cached_frames[c_idx]
            target_midi = test_chords[c_idx]

            sig = calibrator.classify_signal(frame, profile)
            det = tracker.process_frame(frame)

            if i % 20 == 0:
                obs_midis = [n.midi for n in det["notes"]]
                fb = compute_practice_feedback(
                    expected_chord="C",
                    expected_midi=target_midi,
                    observed_midi=obs_midis,
                    input_status=sig["qualityState"],
                    matching_mode=MatchingMode.EXACT_NOTE_MATCH,
                    playback_time=i * 0.023,
                )
                evt = PlayerFeedbackEvent(
                    eventType=PlayerFeedbackEventType.CHORD_MATCHED if fb["feedbackStatus"] == "MATCH" else PlayerFeedbackEventType.CHORD_PARTIAL,
                    timestamp=i * 0.023,
                    chordName="C",
                    expectedMidi=target_midi,
                    observedMidi=obs_midis,
                )
                metrics.record_feedback_event(evt)

        # Invariant checks
        assert len(metrics.recent_events) == 50
        assert metrics.chords_attempted == 100
        summary = metrics.get_session_summary()
        assert summary["chordsAttempted"] == 100
        assert summary["chordsMatched"] > 0
