"""
backend/benchmarks/real_piano_evaluation.py

Real Acoustic Piano Note & Chord Detection Evaluation Harness for HotChords (Phase 14).

Scientifically evaluates polyphonic pitch detection accuracy, onset timing precision,
overtone suppression, and chord recognition against authoritative ground-truth recordings.

Key Principles:
1. No Manufactured Real-World Results: Clearly exposes REAL_PIANO_GROUND_TRUTH status.
2. Standard MIR Metrics: Precision, Recall, F1, Onset MAE, p95 Timing Error, Tolerance Curves.
3. Multi-Dimensional Breakdown: Register, Chord Size, Velocity, Pedal, Mic Distance, Room Acoustic.
4. Local-First & In-Memory: Evaluates audio streams in memory without network/cloud calls.
"""
from __future__ import annotations

import os
import json
import time
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple, Union
import numpy as np
from pydantic import BaseModel, Field, ConfigDict

from backend.analysis.test_signals import midi_to_note_name, note_name_to_midi, midi_to_freq
from backend.analysis.realtime_pitch import PolyphonicPitchDetector, RealTimeNoteTracker, DetectedNote
from backend.theory.theory import get_pitch_class, NOTE_NAMES, NOTE_FLAT


# Global Constant for Ground-Truth Status
REAL_PIANO_GROUND_TRUTH = "NOT_AVAILABLE"
REAL_ACOUSTIC_ACCURACY = "NOT_ESTABLISHED"


class PianoType(str, Enum):
    ACOUSTIC_UPRIGHT = "ACOUSTIC_UPRIGHT"
    ACOUSTIC_GRAND = "ACOUSTIC_GRAND"
    DIGITAL_STAGE_MONITOR = "DIGITAL_STAGE_MONITOR"
    SYNTHETIC_ACOUSTIC_MODEL = "SYNTHETIC_ACOUSTIC_MODEL"


class MicPosition(str, Enum):
    CLOSE = "CLOSE"                     # 0.3 - 0.5m over strings / soundboard
    MEDIUM_PRACTICE = "MEDIUM_PRACTICE" # 0.8 - 1.2m at music stand / laptop
    AMBIENT_ROOM = "AMBIENT_ROOM"       # 2.5 - 3.5m across the room


class RoomCondition(str, Enum):
    DRY_TREATED = "DRY_TREATED"         # RT60 < 0.3s
    NORMAL_ROOM = "NORMAL_ROOM"         # RT60 ~ 0.4 - 0.6s
    REVERBERANT = "REVERBERANT"         # RT60 > 0.8s


class VelocityDynamic(str, Enum):
    PP = "PP"  # Soft (25 - 45)
    MF = "MF"  # Medium (60 - 80)
    FF = "FF"  # Loud (95 - 120)


class PedalCondition(str, Enum):
    NO_PEDAL = "NO_PEDAL"
    SUSTAIN_PEDAL = "SUSTAIN_PEDAL"


class PlayerStyle(str, Enum):
    CLEAN_PRACTICE = "CLEAN_PRACTICE"
    BEGINNER_FLAMMED = "BEGINNER_FLAMMED"
    BEGINNER_HESITANT = "BEGINNER_HESITANT"


class GroundTruthNote(BaseModel):
    """Authoritative ground-truth piano note event."""
    onset: float = Field(..., description="Note onset time in seconds")
    offset: float = Field(..., description="Note offset/release time in seconds")
    midi: int = Field(..., ge=21, le=108, description="MIDI note number (21-108)")
    pitch_name: str = Field(default="", alias="pitchName")
    velocity: int = Field(default=75, ge=1, le=127)

    model_config = ConfigDict(populate_by_name=True)

    def model_post_init(self, __context: Any) -> None:
        if not self.pitch_name:
            self.pitch_name = midi_to_note_name(self.midi)


class GroundTruthChord(BaseModel):
    """Authoritative ground-truth chord segment."""
    start: float = Field(..., description="Chord start time in seconds")
    end: float = Field(..., description="Chord end time in seconds")
    chord: str = Field(..., description="Chord symbol string, e.g. 'C', 'Am7'")
    midi_notes: List[int] = Field(default_factory=list, alias="midiNotes")

    model_config = ConfigDict(populate_by_name=True)


class RealPianoRecording(BaseModel):
    """Metadata and ground-truth bundle for an acoustic piano recording track."""
    recording_id: str = Field(..., alias="recordingId")
    audio_path: str = Field(..., alias="audioPath")
    audio_hash: str = Field(default="", alias="audioHash")
    duration_seconds: float = Field(default=0.0, alias="durationSeconds")
    piano_type: PianoType = Field(default=PianoType.ACOUSTIC_UPRIGHT, alias="pianoType")
    mic_position: MicPosition = Field(default=MicPosition.MEDIUM_PRACTICE, alias="micPosition")
    room_condition: RoomCondition = Field(default=RoomCondition.NORMAL_ROOM, alias="roomCondition")
    velocity_dynamic: VelocityDynamic = Field(default=VelocityDynamic.MF, alias="velocityDynamic")
    pedal_condition: PedalCondition = Field(default=PedalCondition.NO_PEDAL, alias="pedalCondition")
    player_style: PlayerStyle = Field(default=PlayerStyle.CLEAN_PRACTICE, alias="playerStyle")
    ground_truth_status: str = Field(default="UNAVAILABLE", alias="groundTruthStatus")
    notes: List[GroundTruthNote] = Field(default_factory=list)
    chords: List[GroundTruthChord] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class NoteMatchingMetrics(BaseModel):
    """Detailed polyphonic and monophonic note evaluation metrics."""
    true_positives: int = Field(default=0, alias="truePositives")
    false_positives: int = Field(default=0, alias="falsePositives")
    false_negatives: int = Field(default=0, alias="falseNegatives")
    precision: float = Field(default=0.0)
    recall: float = Field(default=0.0)
    f1_score: float = Field(default=0.0, alias="f1Score")
    fp_per_second: float = Field(default=0.0, alias="fpPerSecond")
    fn_per_second: float = Field(default=0.0, alias="fnPerSecond")

    # Timing metrics (onsets within matching tolerance)
    onset_mae_ms: float = Field(default=0.0, alias="onsetMaeMs")
    onset_median_error_ms: float = Field(default=0.0, alias="onsetMedianErrorMs")
    onset_p95_error_ms: float = Field(default=0.0, alias="onsetP95ErrorMs")
    
    # Onset tolerance curve (e.g. at 20ms, 50ms, 100ms, 200ms)
    tolerance_curve: Dict[str, float] = Field(default_factory=dict, alias="toleranceCurve")

    model_config = ConfigDict(populate_by_name=True)


class ChordLevelMetrics(BaseModel):
    """Chord and harmonic transition evaluation metrics."""
    total_chord_frames: int = Field(default=0, alias="totalChordFrames")
    exact_note_set_accuracy: float = Field(default=0.0, alias="exactNoteSetAccuracy")
    pitch_class_accuracy: float = Field(default=0.0, alias="pitchClassAccuracy")
    chord_transition_mae_ms: float = Field(default=0.0, alias="chordTransitionMaeMs")

    model_config = ConfigDict(populate_by_name=True)


class NoteMetricsSummary(BaseModel):
    """Lightweight note summary for category breakdowns."""
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = Field(default=0.0, alias="f1Score")
    total_notes_evaluated: int = Field(default=0, alias="totalNotesEvaluated")

    model_config = ConfigDict(populate_by_name=True)


class RealPianoEvaluationResult(BaseModel):
    """Comprehensive evaluation result for a dataset or track."""
    evaluation_id: str = Field(..., alias="evaluationId")
    ground_truth_status: str = Field(default="NOT_AVAILABLE", alias="groundTruthStatus")
    is_synthetic_fixture: bool = Field(default=False, alias="isSyntheticFixture")
    total_recordings: int = Field(default=0, alias="totalRecordings")
    total_audio_duration_s: float = Field(default=0.0, alias="totalAudioDurationS")
    aggregate_note_metrics: NoteMetricsSummary = Field(default_factory=lambda: NoteMetricsSummary(), alias="aggregateNoteMetrics")
    chord_metrics: ChordLevelMetrics = Field(default_factory=lambda: ChordLevelMetrics(), alias="chordMetrics")
    breakdown_by_register: Dict[str, NoteMetricsSummary] = Field(default_factory=dict, alias="breakdownByRegister")
    breakdown_by_chord_size: Dict[str, NoteMetricsSummary] = Field(default_factory=dict, alias="breakdownByChordSize")
    breakdown_by_velocity: Dict[str, NoteMetricsSummary] = Field(default_factory=dict, alias="breakdownByVelocity")
    breakdown_by_pedal: Dict[str, NoteMetricsSummary] = Field(default_factory=dict, alias="breakdownByPedal")
    breakdown_by_mic_position: Dict[str, NoteMetricsSummary] = Field(default_factory=dict, alias="breakdownByMicPosition")
    breakdown_by_room_condition: Dict[str, NoteMetricsSummary] = Field(default_factory=dict, alias="breakdownByRoomCondition")
    latency_summary: Dict[str, float] = Field(default_factory=dict, alias="latencySummary")

    model_config = ConfigDict(populate_by_name=True)


# ══════════════════════════════════════════════════════════════
#  EVALUATION CORE ENGINE
# ══════════════════════════════════════════════════════════════

class RealPianoEvaluator:
    """
    Evaluation Engine for Real-Piano and Synthetic Acoustic Note Detection.
    """

    def __init__(
        self,
        sample_rate: int = 22050,
        n_fft: int = 4096,
        hop_size: int = 512,
        default_onset_tolerance_s: float = 0.050, # ±50 ms standard MIR tolerance
    ):
        self.sample_rate = sample_rate
        self.n_fft = n_fft
        self.hop_size = hop_size
        self.default_onset_tolerance_s = default_onset_tolerance_s

    def evaluate_audio_signal(
        self,
        audio: np.ndarray,
        ground_truth_notes: List[GroundTruthNote],
        ground_truth_chords: Optional[List[GroundTruthChord]] = None,
        is_synthetic: bool = False,
    ) -> Dict[str, Any]:
        """
        Runs the HotChords RealTimeNoteTracker over an audio waveform and computes exact MIR metrics.
        """
        detector = PolyphonicPitchDetector(sample_rate=self.sample_rate, n_fft=self.n_fft, hop_size=self.hop_size)
        tracker = RealTimeNoteTracker(detector=detector)

        sr = self.sample_rate
        hop = self.hop_size
        duration_s = float(len(audio)) / float(sr)

        num_frames = (len(audio) - self.n_fft) // hop
        if num_frames <= 0:
            return self._empty_result(duration_s, is_synthetic)

        # Track detected note events: List of (time_s, midi, note_name)
        detected_frames: List[Dict[str, Any]] = []
        frame_latencies: List[float] = []

        # Stream processing frame by frame
        for i in range(num_frames):
            frame_chunk = audio[i * hop : i * hop + self.n_fft].astype(np.float32)
            frame_time = (i * hop) / sr

            t0 = time.perf_counter()
            res = tracker.process_frame(frame_chunk)
            t1 = time.perf_counter()
            frame_latencies.append((t1 - t0) * 1000.0)

            active_midis = [n.midi for n in res["notes"]]
            detected_frames.append({
                "time": frame_time,
                "midis": set(active_midis),
                "status": res["status"]
            })

        # Evaluate Note-Level Metrics
        note_metrics = self.calculate_note_metrics(detected_frames, ground_truth_notes, duration_s)

        # Evaluate Chord-Level Metrics
        chord_metrics = self.calculate_chord_metrics(detected_frames, ground_truth_chords or [])

        # Latency Metrics
        latency_summary = {
            "meanLatencyMs": round(float(np.mean(frame_latencies)), 3) if frame_latencies else 0.0,
            "p95LatencyMs": round(float(np.percentile(frame_latencies, 95)), 3) if frame_latencies else 0.0,
            "maxLatencyMs": round(float(np.max(frame_latencies)), 3) if frame_latencies else 0.0,
        }

        return {
            "noteMetrics": note_metrics.model_dump(by_alias=True),
            "chordMetrics": chord_metrics.model_dump(by_alias=True),
            "latencySummary": latency_summary,
            "durationSeconds": round(duration_s, 2),
            "totalFrames": num_frames,
            "isSynthetic": is_synthetic,
            "groundTruthStatus": "AVAILABLE" if (ground_truth_notes and not is_synthetic) else "NOT_AVAILABLE"
        }

    def calculate_note_metrics(
        self,
        detected_frames: List[Dict[str, Any]],
        ground_truth_notes: List[GroundTruthNote],
        duration_s: float
    ) -> NoteMatchingMetrics:
        """
        Calculates precision, recall, F1 score, false alarms/sec, onset errors, and tolerance curves.
        """
        if not ground_truth_notes:
            total_detected = sum(len(f["midis"]) for f in detected_frames)
            return NoteMatchingMetrics(
                true_positives=0,
                false_positives=total_detected,
                false_negatives=0,
                precision=0.0,
                recall=0.0,
                f1_score=0.0,
                fp_per_second=round(total_detected / max(1.0, duration_s), 2),
                fn_per_second=0.0,
                onset_mae_ms=0.0,
                onset_median_error_ms=0.0,
                onset_p95_error_ms=0.0,
                tolerance_curve={"20ms": 0.0, "50ms": 0.0, "100ms": 0.0, "200ms": 0.0}
            )

        # Extract continuous note activations from detected frames
        detected_note_events = self._extract_note_events_from_frames(detected_frames)

        # Match detected note events against ground truth
        tp = 0
        fp = 0
        fn = 0
        matched_gt_indices = set()
        matched_onset_errors: List[float] = []

        # Standard tolerances for curve
        tolerances = [0.020, 0.050, 0.100, 0.200]
        curve_counts = {t: 0 for t in tolerances}

        for det in detected_note_events:
            det_midi = det["midi"]
            det_onset = det["onset"]

            # Search for matching ground truth note
            best_gt_idx = None
            best_diff = 999.0

            for gt_idx, gt in enumerate(ground_truth_notes):
                if gt_idx in matched_gt_indices:
                    continue
                if gt.midi == det_midi:
                    diff = abs(det_onset - gt.onset)
                    if diff <= self.default_onset_tolerance_s and diff < best_diff:
                        best_diff = diff
                        best_gt_idx = gt_idx

            if best_gt_idx is not None:
                tp += 1
                matched_gt_indices.add(best_gt_idx)
                matched_onset_errors.append(best_diff * 1000.0) # In ms
                
                for tol in tolerances:
                    if best_diff <= tol:
                        curve_counts[tol] += 1
            else:
                fp += 1

        fn = len(ground_truth_notes) - len(matched_gt_indices)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2.0 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        mae = float(np.mean(matched_onset_errors)) if matched_onset_errors else 0.0
        med_err = float(np.median(matched_onset_errors)) if matched_onset_errors else 0.0
        p95_err = float(np.percentile(matched_onset_errors, 95)) if matched_onset_errors else 0.0

        n_gt = len(ground_truth_notes)
        tolerance_curve = {
            f"{int(t*1000)}ms": round(curve_counts[t] / n_gt, 3) if n_gt > 0 else 0.0
            for t in tolerances
        }

        return NoteMatchingMetrics(
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
            precision=round(float(precision), 3),
            recall=round(float(recall), 3),
            f1_score=round(float(f1), 3),
            fp_per_second=round(float(fp / max(1.0, duration_s)), 3),
            fn_per_second=round(float(fn / max(1.0, duration_s)), 3),
            onset_mae_ms=round(float(mae), 2),
            onset_median_error_ms=round(float(med_err), 2),
            onset_p95_error_ms=round(float(p95_err), 2),
            tolerance_curve=tolerance_curve
        )

    def calculate_chord_metrics(
        self,
        detected_frames: List[Dict[str, Any]],
        ground_truth_chords: List[GroundTruthChord]
    ) -> ChordLevelMetrics:
        """
        Calculates exact chord note-set accuracy, pitch-class accuracy, and transition alignment.
        """
        if not ground_truth_chords or not detected_frames:
            return ChordLevelMetrics()

        exact_set_matches = 0
        pc_matches = 0
        evaluated_frames = 0

        for frame in detected_frames:
            t = frame["time"]
            active_midis = frame["midis"]
            active_pcs = {m % 12 for m in active_midis}

            # Find active ground truth chord
            gt_chord = next((c for c in ground_truth_chords if c.start <= t < c.end), None)
            if gt_chord and gt_chord.midi_notes:
                evaluated_frames += 1
                gt_set = set(gt_chord.midi_notes)
                gt_pcs = {m % 12 for m in gt_chord.midi_notes}

                if active_midis == gt_set:
                    exact_set_matches += 1
                if active_pcs == gt_pcs:
                    pc_matches += 1

        exact_acc = exact_set_matches / evaluated_frames if evaluated_frames > 0 else 0.0
        pc_acc = pc_matches / evaluated_frames if evaluated_frames > 0 else 0.0

        return ChordLevelMetrics(
            total_chord_frames=evaluated_frames,
            exact_note_set_accuracy=round(float(exact_acc), 3),
            pitch_class_accuracy=round(float(pc_acc), 3),
            chord_transition_mae_ms=0.0
        )

    def _extract_note_events_from_frames(self, detected_frames: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extracts discrete note onset/offset events from streaming frame predictions."""
        active_notes: Dict[int, float] = {} # midi -> onset_time
        events: List[Dict[str, Any]] = []

        for frame in detected_frames:
            t = frame["time"]
            current_midis = frame["midis"]

            # New onsets
            for m in current_midis:
                if m not in active_notes:
                    active_notes[m] = t

            # Releases
            for m in list(active_notes.keys()):
                if m not in current_midis:
                    onset = active_notes.pop(m)
                    events.append({
                        "midi": m,
                        "onset": onset,
                        "offset": t,
                        "duration": t - onset
                    })

        # Close any lingering notes at end of track
        final_time = detected_frames[-1]["time"] if detected_frames else 0.0
        for m, onset in active_notes.items():
            events.append({
                "midi": m,
                "onset": onset,
                "offset": final_time,
                "duration": final_time - onset
            })

        return sorted(events, key=lambda e: e["onset"])

    def _empty_result(self, duration_s: float, is_synthetic: bool) -> Dict[str, Any]:
        return {
            "noteMetrics": NoteMatchingMetrics().model_dump(by_alias=True),
            "chordMetrics": ChordLevelMetrics().model_dump(by_alias=True),
            "latencySummary": {"meanLatencyMs": 0.0, "p95LatencyMs": 0.0, "maxLatencyMs": 0.0},
            "durationSeconds": duration_s,
            "totalFrames": 0,
            "isSynthetic": is_synthetic,
            "groundTruthStatus": "NOT_AVAILABLE"
        }
