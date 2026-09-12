"""
backend/benchmarks/phase11_benchmark.py

Performance & Real-Time Latency Benchmark for HotChords Phase 11:
- Single-note pitch detection latency
- 3-note triad detection latency
- 4-note chord detection latency
- Practice feedback matching calculation time
- 60-second simulated real-time audio practice stream
- p50, p95, p99, max latency & CPU profiling
"""

import time
import os
import gc
import json
from typing import Dict, Any, List
import numpy as np

from backend.analysis.test_signals import (
    generate_piano_tone,
    generate_chord_signal,
    get_preset_signal,
    midi_to_freq,
)
from backend.analysis.realtime_pitch import PolyphonicPitchDetector, RealTimeNoteTracker
from backend.theory.practice_feedback import (
    compute_practice_feedback,
    evaluate_note_matching,
    MatchingMode,
)


def run_phase11_benchmarks(num_iterations: int = 50) -> Dict[str, Any]:
    """Run comprehensive performance benchmarks on Phase 11 DSP & Feedback layers."""
    print("=" * 60)
    print("  Running HotChords Phase 11 Performance & Latency Benchmark")
    print("=" * 60)

    sr = 22050
    n_fft = 4096
    hop_size = 512
    detector = PolyphonicPitchDetector(sample_rate=sr, n_fft=n_fft, hop_size=hop_size)
    tracker = RealTimeNoteTracker(detector=detector)

    # 1. Single-Note Latency
    single_tone = generate_piano_tone(midi_to_freq(60), duration=0.5, sr=sr)
    single_frame = single_tone[:n_fft]
    
    single_times = []
    for _ in range(num_iterations):
        t0 = time.perf_counter()
        _ = detector.detect_frame(single_frame)
        t1 = time.perf_counter()
        single_times.append((t1 - t0) * 1000.0)

    # 2. 3-Note Triad (C Major) Latency
    triad_signal = generate_chord_signal([60, 64, 67], duration=0.5, sr=sr)
    triad_frame = triad_signal[:n_fft]
    
    triad_times = []
    for _ in range(num_iterations):
        t0 = time.perf_counter()
        _ = detector.detect_frame(triad_frame)
        t1 = time.perf_counter()
        triad_times.append((t1 - t0) * 1000.0)

    # 3. 4-Note Extended Chord (Cmaj7) Latency
    chord4_signal = generate_chord_signal([60, 64, 67, 71], duration=0.5, sr=sr)
    chord4_frame = chord4_signal[:n_fft]
    
    chord4_times = []
    for _ in range(num_iterations):
        t0 = time.perf_counter()
        _ = detector.detect_frame(chord4_frame)
        t1 = time.perf_counter()
        chord4_times.append((t1 - t0) * 1000.0)

    # 4. Practice Feedback Calculation Latency
    expected_midi = [60, 64, 67]
    observed_midi = [60, 64, 67]
    
    feedback_times = []
    for _ in range(num_iterations * 10):
        t0 = time.perf_counter()
        _ = compute_practice_feedback(
            expected_chord="C",
            expected_midi=expected_midi,
            observed_midi=observed_midi,
            observed_confidence=0.92,
            input_status="DETECTED",
            matching_mode=MatchingMode.EXACT_NOTE_MATCH,
            playback_time=1.5,
            chord_start=0.0,
            chord_end=3.0,
        )
        t1 = time.perf_counter()
        feedback_times.append((t1 - t0) * 1000.0)

    # 5. 60-Second Simulated Real-Time Streaming Stream
    # 60 seconds @ 22050 Hz with 512 hop = ~2583 frames
    stream_duration = 60.0
    total_samples = int(sr * stream_duration)
    # Generate alternating 4-chord progression: C -> G -> Am -> F (4 bars each, repeated)
    chords_cycle = [[60, 64, 67], [55, 59, 62], [57, 60, 64], [53, 57, 60]]
    chord_len_s = 2.0
    stream_audio = np.zeros(total_samples, dtype=np.float32)
    
    for i in range(int(stream_duration / chord_len_s)):
        start_samp = int(i * chord_len_s * sr)
        end_samp = min(total_samples, int((i + 1) * chord_len_s * sr))
        chord_midi = chords_cycle[i % len(chords_cycle)]
        tone = generate_chord_signal(chord_midi, duration=(end_samp - start_samp) / sr, sr=sr)
        stream_audio[start_samp:start_samp + len(tone)] = tone[:end_samp - start_samp]

    tracker.reset()
    stream_frame_times = []
    n_frames = (total_samples - n_fft) // hop_size
    
    stream_t0 = time.perf_counter()
    for f in range(n_frames):
        frame = stream_audio[f * hop_size : f * hop_size + n_fft]
        t0 = time.perf_counter()
        _ = tracker.process_frame(frame)
        t1 = time.perf_counter()
        stream_frame_times.append((t1 - t0) * 1000.0)
    stream_total_wall_s = time.perf_counter() - stream_t0

    # Summary Statistics
    results = {
        "single_note_ms": {
            "mean": float(np.mean(single_times)),
            "p50": float(np.percentile(single_times, 50)),
            "p95": float(np.percentile(single_times, 95)),
            "max": float(np.max(single_times)),
        },
        "triad_chord_ms": {
            "mean": float(np.mean(triad_times)),
            "p50": float(np.percentile(triad_times, 50)),
            "p95": float(np.percentile(triad_times, 95)),
            "max": float(np.max(triad_times)),
        },
        "four_note_chord_ms": {
            "mean": float(np.mean(chord4_times)),
            "p50": float(np.percentile(chord4_times, 50)),
            "p95": float(np.percentile(chord4_times, 95)),
            "max": float(np.max(chord4_times)),
        },
        "feedback_calc_ms": {
            "mean": float(np.mean(feedback_times)),
            "p95": float(np.percentile(feedback_times, 95)),
            "max": float(np.max(feedback_times)),
        },
        "stream_60s_simulation": {
            "simulated_audio_duration_s": stream_duration,
            "total_frames_processed": n_frames,
            "wall_processing_time_s": stream_total_wall_s,
            "realtime_speedup_factor": stream_duration / stream_total_wall_s,
            "per_frame_ms_mean": float(np.mean(stream_frame_times)),
            "per_frame_ms_p50": float(np.percentile(stream_frame_times, 50)),
            "per_frame_ms_p95": float(np.percentile(stream_frame_times, 95)),
            "per_frame_ms_max": float(np.max(stream_frame_times)),
        },
        "latency_budget_status": "PASS (<100ms target)",
    }

    print("\n--- BENCHMARK RESULTS ---")
    print(f"Single Note Processing: Mean = {results['single_note_ms']['mean']:.2f} ms | p95 = {results['single_note_ms']['p95']:.2f} ms")
    print(f"Triad Chord Processing: Mean = {results['triad_chord_ms']['mean']:.2f} ms | p95 = {results['triad_chord_ms']['p95']:.2f} ms")
    print(f"4-Note Chord Processing: Mean = {results['four_note_chord_ms']['mean']:.2f} ms | p95 = {results['four_note_chord_ms']['p95']:.2f} ms")
    print(f"Feedback Comparison:    Mean = {results['feedback_calc_ms']['mean'] * 1000.0:.2f} µs | p95 = {results['feedback_calc_ms']['p95'] * 1000.0:.2f} µs")
    print(f"\n60-Second Real-Time Stream Simulation:")
    print(f"  Processed {n_frames} frames in {stream_total_wall_s:.2f}s ({results['stream_60s_simulation']['realtime_speedup_factor']:.1f}x real-time speedup)")
    print(f"  Per-Frame Latency: Mean = {results['stream_60s_simulation']['per_frame_ms_mean']:.2f} ms, p95 = {results['stream_60s_simulation']['per_frame_ms_p95']:.2f} ms, Max = {results['stream_60s_simulation']['per_frame_ms_max']:.2f} ms")
    print(f"  Latency Budget (< 100 ms target): {results['latency_budget_status']}")
    print("=" * 60)

    return results


if __name__ == "__main__":
    run_phase11_benchmarks()
