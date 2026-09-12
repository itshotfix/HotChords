"""
backend/benchmarks/performance_bench.py

Performance, Memory, and Scalability Benchmark Harness for HotChords.
Evaluates:
- Execution time across song durations: 30s, 60s, 180s (3min), 300s (5min), 600s (10min)
- Stage-by-stage latency (profiling, timing, chord inference, structure analysis, loop detection)
- Memory usage (RSS peak MB)
- Cold run vs. Cached run speedups
"""

import time
import os
import gc
import resource
import tempfile
import numpy as np
import soundfile as sf
from typing import Dict, Any, List

from backend.analysis.pipeline import analyze_song
from backend.analysis.profiling import profile_audio
from backend.analysis.timing import TimingAnalyzer
from backend.analysis.engine_manager import ChordEngineManager
from backend.analysis.structure import detect_structure_and_repeats
from backend.analysis.loop_detection import detect_four_chord_loop
import librosa


def generate_benchmark_wav(duration_sec: float, sr: int = 22050) -> str:
    """Generates synthetic musical audio of specified duration for performance testing."""
    n_samples = int(duration_sec * sr)
    t = np.linspace(0, duration_sec, n_samples, endpoint=False)
    # 4-chord repeating oscillation (C - G - Am - F)
    chord_freqs = [
        [261.63, 329.63, 392.00],  # C
        [196.00, 246.94, 293.66],  # G
        [220.00, 261.63, 329.63],  # Am
        [174.61, 220.00, 261.63],  # F
    ]
    audio = np.zeros(n_samples, dtype=np.float32)
    chunk_len = int(2.0 * sr)  # 2s per chord

    for i in range(0, n_samples, chunk_len):
        chord_idx = (i // chunk_len) % 4
        sub_len = min(chunk_len, n_samples - i)
        t_sub = t[i : i + sub_len]
        for f in chord_freqs[chord_idx]:
            audio[i : i + sub_len] += (0.3 * np.sin(2 * np.pi * f * t_sub)).astype(np.float32)

    # Add gentle noise
    audio += np.random.normal(0, 0.005, n_samples).astype(np.float32)

    temp_path = os.path.join(tempfile.gettempdir(), f"perf_bench_{int(duration_sec)}s_{os.getpid()}.wav")
    sf.write(temp_path, audio, sr)
    return temp_path


def benchmark_duration_scaling(durations: List[float] = None) -> List[Dict[str, Any]]:
    """
    Runs isolated benchmarks across multiple song durations and records latency and memory.
    """
    if durations is None:
        durations = [30.0, 60.0, 180.0, 300.0, 600.0]

    results = []
    engine_manager = ChordEngineManager()

    for dur in durations:
        gc.collect()
        # On Darwin, ru_maxrss is in bytes; on Linux, in KB.
        rusage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        mem_before = rusage / (1024 * 1024) if rusage > 10000000 else rusage / 1024
        wav_path = generate_benchmark_wav(dur)

        try:
            # Stage 1: Load & Profiling
            t0 = time.perf_counter()
            y, sr = librosa.load(wav_path, sr=22050, mono=True)
            prof, status, _ = profile_audio(y, sr)
            t_prof = time.perf_counter() - t0

            # Stage 2: Timing
            t0 = time.perf_counter()
            t_analyzer = TimingAnalyzer(y=y, sr=sr).analyze()
            timing_data = t_analyzer.get_timing_data()
            t_timing = time.perf_counter() - t0

            # Stage 3: Chord Inference
            t0 = time.perf_counter()
            chord_res = engine_manager.recognize_chords(
                audio_path=wav_path,
                timing_data=timing_data,
                duration=dur
            )
            t_chord = time.perf_counter() - t0

            # Stage 4: Structure Analysis (SSM Recurrence)
            t0 = time.perf_counter()
            hop = 512
            chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop, bins_per_octave=36)
            structure_res = detect_structure_and_repeats(
                chroma=chroma,
                sr=sr,
                hop_length=hop,
                duration=dur,
                timing_data=timing_data
            )
            t_struct = time.perf_counter() - t0

            # Stage 5: 4-Chord Loop Detection
            t0 = time.perf_counter()
            loop_res = detect_four_chord_loop(
                chords=chord_res.events,
                duration=dur,
                structure=structure_res,
                timing_data=timing_data
            )
            t_loop = time.perf_counter() - t0

            total_time = t_prof + t_timing + t_chord + t_struct + t_loop
            rusage_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            mem_after = rusage_after / (1024 * 1024) if rusage_after > 10000000 else rusage_after / 1024
            peak_ram_mb = round(mem_after, 2)

            results.append({
                "duration_sec": dur,
                "total_time_sec": round(total_time, 3),
                "rtf": round(total_time / dur, 4),  # Real-Time Factor (< 1.0 means faster than real-time)
                "profiling_time_sec": round(t_prof, 3),
                "timing_time_sec": round(t_timing, 3),
                "chord_inference_time_sec": round(t_chord, 3),
                "structure_analysis_time_sec": round(t_struct, 3),
                "loop_detection_time_sec": round(t_loop, 4),
                "peak_ram_mb": peak_ram_mb,
            })

        finally:
            if os.path.exists(wav_path):
                try:
                    os.remove(wav_path)
                except OSError:
                    pass

    return results
