"""
backend/benchmarks/real_song_validator.py

Real-Song Validation & Diagnostic Engine for HotChords Phase 7.
Audits real songs across multi-instrument arrangements, evaluates engine disagreement,
source selection truthfulness, beginner playability, and produces comprehensive MIR diagnostic artifacts.
"""

import os
import sys
import time
import json
import ctypes
try:
    import resource
except ImportError:
    resource = None
from typing import Dict, List, Any, Optional

from backend.analysis.pipeline import analyze_song
from backend.analysis.engine_manager import ChordEngineManager
from backend.benchmarks.real_song_dataset import RealSongTrack, RealSongDatasetRegistry
from backend.benchmarks.metrics import (
    compare_engine_predictions,
    evaluate_chord_timeline,
    classify_real_song_error
)
from backend.theory.simplification import evaluate_beginner_difficulty


def get_current_rss_mb() -> float:
    """Returns instantaneous process RSS memory in MB."""
    if sys.platform == "darwin":
        try:
            TASK_BASIC_INFO_64 = 5
            class mach_task_basic_info_data(ctypes.Structure):
                _fields_ = [
                    ('virtual_size', ctypes.c_uint64),
                    ('resident_size', ctypes.c_uint64),
                    ('resident_size_max', ctypes.c_uint64),
                    ('user_time', ctypes.c_uint64),
                    ('system_time', ctypes.c_uint64),
                    ('policy', ctypes.c_int32),
                    ('suspend_count', ctypes.c_int32),
                ]
            libc = ctypes.CDLL(None)
            task = libc.mach_task_self()
            info = mach_task_basic_info_data()
            count = ctypes.c_uint32(ctypes.sizeof(info) // 4)
            res = libc.task_info(task, TASK_BASIC_INFO_64, ctypes.byref(info), ctypes.byref(count))
            if res == 0:
                return round(info.resident_size / (1024 * 1024), 2)
        except Exception:
            pass

    if resource is not None:
        try:
            rusage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            return round(rusage / (1024 * 1024) if rusage > 10000000 else rusage / 1024, 2)
        except Exception:
            pass
    return 0.0



class RealSongValidationReport:
    """Encapsulates diagnostic validation results for a single real song."""

    def __init__(self, track: RealSongTrack):
        self.track = track
        self.analysis_result: Dict[str, Any] = {}
        self.engine_comparison: Dict[str, Any] = {}
        self.error_classification: List[Dict[str, Any]] = []
        self.playability_score: float = 0.0
        self.elapsed_time_s: float = 0.0
        self.peak_memory_mb: float = 0.0
        self.warnings: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "track": self.track.to_dict(),
            "detected_key": self.analysis_result.get("key_full"),
            "detected_bpm": self.analysis_result.get("tempo"),
            "time_signature": self.analysis_result.get("time_sig"),
            "status": self.analysis_result.get("status"),
            "status_message": self.analysis_result.get("status_message"),
            "chord_source": self.analysis_result.get("chord_source"),
            "source_selection_reason": self.analysis_result.get("source_selection_reason"),
            "source_agreement": self.analysis_result.get("source_agreement"),
            "detected_instruments": self.analysis_result.get("instruments", {}),
            "total_chords": len(self.analysis_result.get("chords", [])),
            "unique_chords": self.analysis_result.get("unique_chords", []),
            "unique_beginner_chords": self.analysis_result.get("unique_beginner_chords", []),
            "structure": self.analysis_result.get("structure", {}),
            "four_chord_loop": self.analysis_result.get("four_chord_loop", {}),
            "playability_score": self.playability_score,
            "engine_comparison": self.engine_comparison,
            "reliability": self.analysis_result.get("reliability", {}),
            "elapsed_time_s": round(self.elapsed_time_s, 3),
            "peak_memory_mb": round(self.peak_memory_mb, 2),
            "warnings": self.warnings
        }


def evaluate_loop_beginner_playability(chords: List[str]) -> float:
    """
    Step 15: Evaluates beginner playability for a 4-chord progression:
    - distinct chord count (penalizes 4 difficult distinct chords)
    - chord complexity (EASY = 1.0, MODERATE = 0.7, DIFFICULT = 0.3)
    - presence of white-key anchors (C, G, F, Am, Em, Dm)
    """
    if not chords or len(chords) != 4:
        return 0.0

    scores = []
    for c in chords:
        diff = evaluate_beginner_difficulty(c)
        if diff == "EASY":
            scores.append(1.0)
        elif diff == "MODERATE":
            scores.append(0.7)
        else:
            scores.append(0.3)

    # Complexity score [0.0, 1.0]
    avg_simplicity = float(sum(scores) / len(scores))
    
    # Variety penalty / bonus (2-4 distinct chords are ideal for 4-chord songs)
    unique_count = len(set(chords))
    variety_score = 1.0 if unique_count in (3, 4) else (0.85 if unique_count == 2 else 0.4)

    playability = 0.7 * avg_simplicity + 0.3 * variety_score
    return round(float(playability), 3)


def validate_real_song(track: RealSongTrack) -> RealSongValidationReport:
    """
    Executes full multi-stage validation on a single real-song audio track.
    Runs pipeline, profiles RAM/time, performs engine comparison, and generates audit metrics.
    """
    report = RealSongValidationReport(track)
    if not os.path.isfile(track.filepath):
        report.warnings.append(f"Audio file not found: {track.filepath}")
        return report

    mem_before = get_current_rss_mb()
    t0 = time.perf_counter()

    try:
        # Run main analysis pipeline
        res = analyze_song(track.filepath)
        report.analysis_result = res
    except Exception as e:
        report.warnings.append(f"Pipeline analysis exception: {e}")
        return report

    t1 = time.perf_counter()
    mem_after = get_current_rss_mb()
    report.elapsed_time_s = t1 - t0
    report.peak_memory_mb = max(0.0, mem_after - mem_before)

    # Evaluate Beginner Playability on Four-Chord Loop
    loop_res = res.get("four_chord_loop", {})
    if loop_res.get("available"):
        loop_chords = loop_res.get("simplified_chords") or loop_res.get("simplifiedChords") or loop_res.get("chords", [])
        report.playability_score = evaluate_loop_beginner_playability(loop_chords)

    # Compare Engines (LV-Chordia vs Legacy CQT/Template)
    try:
        mgr = ChordEngineManager()
        legacy_res = mgr.recognize_chords(
            audio_path=track.filepath,
            duration=res.get("duration", 0.0),
            key=res.get("key", "C"),
            scale=res.get("scale", "Major"),
            force_fallback=True
        )
        if legacy_res and legacy_res.events:
            report.engine_comparison = compare_engine_predictions(
                engine_a_chords=res.get("chords", []),
                engine_b_chords=legacy_res.events,
                duration=res.get("duration", 0.0)
            )
    except Exception as e:
        report.warnings.append(f"Engine comparison error: {e}")

    # Inspect for specific acoustic warnings
    prof = res.get("audio_profile", {})
    if prof.get("silence_ratio", 0.0) > 0.40:
        report.warnings.append("High silence ratio detected (>40% silent frames).")
    if prof.get("spectral_flatness", 0.0) > 0.40:
        report.warnings.append("High spectral flatness / low tonal content detected.")
    if res.get("status") == "LOW_CONFIDENCE":
        report.warnings.append("Low harmonic confidence reported by pipeline.")

    return report


def run_real_song_validation_suite(dataset_dir: Optional[str] = None) -> List[RealSongValidationReport]:
    """
    Discovers and validates all available real songs in the test dataset directory.
    """
    registry = RealSongDatasetRegistry()
    if dataset_dir and os.path.isdir(dataset_dir):
        registry.scan_test_songs_dir(dataset_dir)
    else:
        # Default test songs folder
        default_dir = os.path.join(os.path.dirname(__file__), "..", "..", "test songs")
        if os.path.isdir(default_dir):
            registry.scan_test_songs_dir(default_dir)

    tracks = registry.list_tracks()
    reports = []
    for track in tracks:
        rep = validate_real_song(track)
        reports.append(rep)

    return reports
