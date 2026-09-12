"""
scripts/run_phase7_validation.py

Executes Phase 7 Real-Song Validation Suite, benchmarks engine disagreement,
evaluates source selection and beginner playability, and dumps empirical diagnostic data.
"""

import os
import sys
import json

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.benchmarks.real_song_validator import run_real_song_validation_suite
from backend.benchmarks.real_song_dataset import RealSongDatasetRegistry


def main():
    print("==================================================")
    print("HOTCHORDS PHASE 7: REAL-SONG VALIDATION SUITE")
    print("==================================================")

    test_songs_dir = os.path.join(os.path.dirname(__file__), "..", "test songs")
    registry = RealSongDatasetRegistry()
    count = registry.scan_test_songs_dir(test_songs_dir)
    print(f"Discovered {count} test songs in '{test_songs_dir}'")

    reports = run_real_song_validation_suite(test_songs_dir)

    out_data = []
    for rep in reports:
        d = rep.to_dict()
        out_data.append(d)
        print(f"\n--- Track: {d['track']['track_id']} ---")
        print(f"Duration: {d['track']['duration']}s | Audio Hash: {d['track']['audio_hash']}")
        print(f"Detected Key: {d['detected_key']} | BPM: {d['detected_bpm']} | Time Sig: {d['time_signature']}")
        print(f"Status: {d['status']} | Chord Source: {d['chord_source']}")
        print(f"Reason: {d['source_selection_reason']}")
        print(f"Unique Chords ({len(d['unique_chords'])}): {d['unique_chords'][:8]}")
        print(f"Beginner Chords ({len(d['unique_beginner_chords'])}): {d['unique_beginner_chords'][:8]}")
        print(f"Four-Chord Loop: {d['four_chord_loop'].get('chords')} (Playability: {d['playability_score']})")
        print(f"Engine Disagreement: {d['engine_comparison'].get('category_percentages', {})}")
        print(f"Elapsed Time: {d['elapsed_time_s']}s | RAM Delta: {d['peak_memory_mb']} MB")
        if d['warnings']:
            print(f"Warnings: {d['warnings']}")

    out_path = os.path.join(os.path.dirname(__file__), "..", "phase7_validation_results.json")
    with open(out_path, "w") as f:
        json.dump(out_data, f, indent=2)

    print(f"\n[OK] Validation results written to {out_path}")


if __name__ == "__main__":
    main()
