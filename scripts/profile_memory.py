"""
scripts/profile_memory.py

Detailed Stage-by-Stage Memory Profiler for HotChords Analysis Pipeline.
Measures true Resident Set Size (RSS) in MB across granular pipeline stages:
1. Baseline
2. Audio Load
3. Audio Profiling & QC
4. Memory-Safe Chunked HPSS
5. Timing & Beat Analysis
6. Chroma CQT Extraction
7. LV-Chordia Chord Inference
8. Structure Analysis (Recurrence SSM)
9. 4-Chord Loop Detection
10. Final Cleanup & Post-GC
"""

import sys
import os
import gc
import time
import json
import ctypes
try:
    import resource
except ImportError:
    resource = None
import tempfile
import multiprocessing as mp
import numpy as np
import soundfile as sf
import librosa

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def get_current_rss_mb() -> float:
    """Returns current process instantaneous RSS memory in MB."""
    # Try Darwin mach task_info for microsecond-accurate RSS without lifetime highwater mark
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

    # Fallback to getrusage
    if resource is not None:
        try:
            rusage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            return round(rusage / (1024 * 1024) if rusage > 10000000 else rusage / 1024, 2)
        except Exception:
            pass
    return 0.0


def run_stage_profile_worker(duration_sec: float, return_dict: dict):
    """Worker process for measuring memory of a single duration cleanly in isolation."""
    from backend.analysis.pipeline import analyze_song
    from backend.analysis.profiling import profile_audio, compute_chunked_hpss
    from backend.analysis.timing import TimingAnalyzer
    from backend.analysis.engine_manager import ChordEngineManager
    from backend.analysis.structure import detect_structure_and_repeats
    from backend.analysis.loop_detection import detect_four_chord_loop
    from backend.benchmarks.performance_bench import generate_benchmark_wav

    gc.collect()
    rss_start = get_current_rss_mb()
    wav_path = generate_benchmark_wav(duration_sec)

    stage_memory = {
        "duration_sec": duration_sec,
        "baseline_rss_mb": rss_start
    }

    try:
        # Stage 1: Load audio
        t0 = time.perf_counter()
        y, sr = librosa.load(wav_path, sr=22050, mono=True)
        dur = float(librosa.get_duration(y=y, sr=sr))
        stage_memory["after_load_rss_mb"] = get_current_rss_mb()
        stage_memory["load_time_sec"] = round(time.perf_counter() - t0, 3)

        # Stage 2: Profiling
        t0 = time.perf_counter()
        profile, status, msg = profile_audio(y, sr)
        stage_memory["after_profiling_rss_mb"] = get_current_rss_mb()
        stage_memory["profiling_time_sec"] = round(time.perf_counter() - t0, 3)

        # Stage 3: Chunked HPSS Harmonic Component
        t0 = time.perf_counter()
        y_harm, _ = compute_chunked_hpss(y, sr=sr, margin=3.0, chunk_sec=30.0)
        stage_memory["after_hpss_rss_mb"] = get_current_rss_mb()
        stage_memory["hpss_time_sec"] = round(time.perf_counter() - t0, 3)

        # Stage 4: Timing Analysis
        t0 = time.perf_counter()
        timing_analyzer = TimingAnalyzer(y=y, sr=sr).analyze()
        timing_data = timing_analyzer.get_timing_data()
        stage_memory["after_timing_rss_mb"] = get_current_rss_mb()
        stage_memory["timing_time_sec"] = round(time.perf_counter() - t0, 3)

        # Stage 5: Chroma CQT
        t0 = time.perf_counter()
        hop = 512
        chroma = librosa.feature.chroma_cqt(y=y_harm, sr=sr, hop_length=hop, bins_per_octave=36)
        stage_memory["after_chroma_cqt_rss_mb"] = get_current_rss_mb()
        stage_memory["chroma_time_sec"] = round(time.perf_counter() - t0, 3)
        stage_memory["chroma_shape"] = list(chroma.shape)
        stage_memory["chroma_nbytes_mb"] = round(chroma.nbytes / (1024 * 1024), 3)

        # Stage 6: Chord Inference
        t0 = time.perf_counter()
        engine_mgr = ChordEngineManager()
        chord_res = engine_mgr.recognize_chords(audio_path=wav_path, timing_data=timing_data, duration=dur)
        stage_memory["after_chord_inference_rss_mb"] = get_current_rss_mb()
        stage_memory["chord_inference_time_sec"] = round(time.perf_counter() - t0, 3)

        # Stage 7: Structure Analysis (Recurrence SSM)
        t0 = time.perf_counter()
        structure_res = detect_structure_and_repeats(
            chroma=chroma, sr=sr, hop_length=hop, duration=dur, timing_data=timing_data
        )
        stage_memory["after_structure_rss_mb"] = get_current_rss_mb()
        stage_memory["structure_time_sec"] = round(time.perf_counter() - t0, 3)

        # Stage 8: 4-Chord Loop Detection
        t0 = time.perf_counter()
        loop_res = detect_four_chord_loop(
            chords=chord_res.events, duration=dur, structure=structure_res, timing_data=timing_data
        )
        stage_memory["after_loop_rss_mb"] = get_current_rss_mb()
        stage_memory["loop_time_sec"] = round(time.perf_counter() - t0, 3)

        # Stage 9: Post Cleanup & GC
        del y, y_harm, chroma, timing_analyzer
        gc.collect()
        stage_memory["after_gc_rss_mb"] = get_current_rss_mb()
        stage_memory["peak_rss_mb"] = max(
            stage_memory["after_load_rss_mb"],
            stage_memory["after_profiling_rss_mb"],
            stage_memory["after_hpss_rss_mb"],
            stage_memory["after_timing_rss_mb"],
            stage_memory["after_chroma_cqt_rss_mb"],
            stage_memory["after_chord_inference_rss_mb"],
            stage_memory["after_structure_rss_mb"],
            stage_memory["after_loop_rss_mb"]
        )

        return_dict.update(stage_memory)

    finally:
        if os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except OSError:
                pass


def profile_pipeline_stages(duration_sec: float) -> dict:
    """Executes a profile run in a clean worker process."""
    manager = mp.Manager()
    return_dict = manager.dict()
    p = mp.Process(target=run_stage_profile_worker, args=(duration_sec, return_dict))
    p.start()
    p.join(timeout=600)
    if p.is_alive():
        p.terminate()
        return {"duration_sec": duration_sec, "error": "timeout"}
    return dict(return_dict)


def main():
    print("=" * 75)
    print(" HOTCHORDS ISOLATED STAGE-BY-STAGE MEMORY PROFILER")
    print("=" * 75)

    durations = [30.0, 60.0, 180.0, 300.0, 600.0, 1200.0]
    results = []

    for dur in durations:
        print(f"\nProfiling {int(dur)}s ({dur/60:.1f} min) audio in isolated process...")
        res = profile_pipeline_stages(dur)
        results.append(res)
        if "error" in res:
            print(f"  FAILED: {res['error']}")
            continue
        print(f"  • Baseline RSS:     {res['baseline_rss_mb']} MB")
        print(f"  • After Load:       {res['after_load_rss_mb']} MB (Time: {res.get('load_time_sec')}s)")
        print(f"  • After HPSS:       {res['after_hpss_rss_mb']} MB (Time: {res.get('hpss_time_sec')}s)")
        print(f"  • After Chroma CQT: {res['after_chroma_cqt_rss_mb']} MB (Shape: {res.get('chroma_shape')}, {res.get('chroma_nbytes_mb')} MB, Time: {res.get('chroma_time_sec')}s)")
        print(f"  • After Chord Inf:  {res['after_chord_inference_rss_mb']} MB (Time: {res.get('chord_inference_time_sec')}s)")
        print(f"  • After Structure:  {res['after_structure_rss_mb']} MB (Time: {res.get('structure_time_sec')}s)")
        print(f"  • After Loop Det:   {res['after_loop_rss_mb']} MB (Time: {res.get('loop_time_sec')}s)")
        print(f"  • Peak RSS:         {res['peak_rss_mb']} MB")
        print(f"  • Post-GC RSS:      {res['after_gc_rss_mb']} MB")

    print("\n" + "=" * 90)
    print(" DETAILED STAGE SUMMARY TABLE (ISOLATED PROCESSES)")
    print("=" * 90)
    print(f"{'Duration':<10} | {'Load (MB)':<10} | {'HPSS (MB)':<10} | {'CQT (MB)':<10} | {'Chord Inf':<12} | {'Struct (MB)':<12} | {'Peak RSS':<10}")
    print("-" * 90)
    for r in results:
        if "error" in r:
            continue
        dur_str = f"{int(r['duration_sec'])}s ({r['duration_sec']/60:.1f}m)"
        print(f"{dur_str:<10} | {r['after_load_rss_mb']:<10.1f} | {r['after_hpss_rss_mb']:<10.1f} | {r['after_chroma_cqt_rss_mb']:<10.1f} | {r['after_chord_inference_rss_mb']:<12.1f} | {r['after_structure_rss_mb']:<12.1f} | {r['peak_rss_mb']:<10.1f}")


if __name__ == "__main__":
    main()
