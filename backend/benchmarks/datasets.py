"""
backend/benchmarks/datasets.py

Standardized Benchmark Dataset Specifications for HotChords MIR Evaluation.
Organizes test items into:
- Development Suite (Controlled diagnostic test cases)
- Validation Suite (Complex structures, modulations, inversions)
- Holdout / Regression Suite (Edge cases, NO_LOOP, silence, noise)
"""

from typing import List, Dict, Any, Optional
from backend.benchmarks.synthetic_generator import generate_synthetic_song, save_synthetic_test_wav


class BenchmarkCase:
    """Represents a single benchmark evaluation item with explicit provenance categorization."""
    def __init__(
        self,
        name: str,
        category: str,
        description: str,
        progression_spec: List[tuple],
        instrument: str = "piano",
        repetition_count: int = 1,
        expected_loop: Optional[List[str]] = None,
        expected_sections: Optional[int] = None,
        split: str = "dev",
        dataset_type: str = "SYNTHETIC"  # "SYNTHETIC", "CONTROLLED_AUDIO", "REAL_WORLD"
    ):
        self.name = name
        self.category = category
        self.description = description
        self.progression_spec = progression_spec
        self.instrument = instrument
        self.repetition_count = repetition_count
        self.expected_loop = expected_loop
        self.expected_sections = expected_sections
        self.split = split
        self.dataset_type = dataset_type

    def generate_audio_and_ground_truth(self) -> tuple:
        audio, gt_timeline, duration = generate_synthetic_song(
            progression=self.progression_spec,
            instrument=self.instrument,
            repetition_count=self.repetition_count
        )
        wav_path = save_synthetic_test_wav(audio, prefix=f"bench_{self.name}")
        return wav_path, audio, gt_timeline, duration


BENCHMARK_REGISTRY: List[BenchmarkCase] = [
    # ══════════════════════════════════════════════════════════════
    #  SYNTHETIC DEVELOPMENT SUITE (Controlled Diagnostic Tests)
    # ══════════════════════════════════════════════════════════════
    BenchmarkCase(
        name="dev_pop_piano_cg_am_f",
        category="standard_pop",
        description="Standard 4-chord pop progression on piano (C-G-Am-F, 3 repetitions)",
        progression_spec=[("C", 2.0), ("G", 2.0), ("Am", 2.0), ("F", 2.0)],
        instrument="piano",
        repetition_count=3,
        expected_loop=["C", "G", "Am", "F"],
        split="dev",
        dataset_type="SYNTHETIC"
    ),
    BenchmarkCase(
        name="dev_pop_guitar_am_f_c_g",
        category="guitar_led",
        description="Guitar-led minor pop progression (Am-F-C-G, 3 repetitions)",
        progression_spec=[("Am", 2.0), ("F", 2.0), ("C", 2.0), ("G", 2.0)],
        instrument="guitar",
        repetition_count=3,
        expected_loop=["Am", "F", "C", "G"],
        split="dev",
        dataset_type="SYNTHETIC"
    ),
    BenchmarkCase(
        name="dev_vamp_synth_c_g",
        category="vamp_2chord",
        description="2-chord electronic synth vamp (C-G-C-G, 4 repetitions)",
        progression_spec=[("C", 2.0), ("G", 2.0), ("C", 2.0), ("G", 2.0)],
        instrument="synth",
        repetition_count=4,
        expected_loop=["C", "G", "C", "G"],
        split="dev",
        dataset_type="SYNTHETIC"
    ),
    BenchmarkCase(
        name="dev_extended_chords_cmaj7_am7_dm7_g7",
        category="extended_harmony",
        description="Extended 7th chords on piano (Cmaj7-Am7-Dm7-G7, 2 repetitions)",
        progression_spec=[("Cmaj7", 2.5), ("Am7", 2.5), ("Dm7", 2.5), ("G7", 2.5)],
        instrument="piano",
        repetition_count=2,
        expected_loop=["C", "Am", "Dm", "G"],  # Beginner simplified expectation
        split="dev",
        dataset_type="SYNTHETIC"
    ),

    # ══════════════════════════════════════════════════════════════
    #  CONTROLLED AUDIO VALIDATION SUITE (Complex Progressions & Structures)
    # ══════════════════════════════════════════════════════════════
    BenchmarkCase(
        name="val_alternating_4event_c_g_c_f",
        category="alternating_loop",
        description="Alternating 4-event progression with repeated C (C-G-C-F, 3 repetitions)",
        progression_spec=[("C", 2.0), ("G", 2.0), ("C", 2.0), ("F", 2.0)],
        instrument="piano",
        repetition_count=3,
        expected_loop=["C", "G", "C", "F"],
        split="val",
        dataset_type="CONTROLLED_AUDIO"
    ),
    BenchmarkCase(
        name="val_slash_chords_inversions",
        category="slash_chords",
        description="Inverted bass progression (C - C/E - F - G/B, 2 repetitions)",
        progression_spec=[("C", 2.0), ("C/E", 2.0), ("F", 2.0), ("G/B", 2.0)],
        instrument="piano",
        repetition_count=2,
        expected_loop=["C", "C", "F", "G"],  # Or inverted C - C/E - F - G/B
        split="val",
        dataset_type="CONTROLLED_AUDIO"
    ),
    BenchmarkCase(
        name="val_multi_section_verse_chorus",
        category="multi_section",
        description="Song with distinct Verse (Dm-Bb-F-C) and Chorus (F-C-Dm-Bb, 2x)",
        progression_spec=[
            ("Dm", 2.0), ("Bb", 2.0), ("F", 2.0), ("C", 2.0),  # Verse 1
            ("F", 2.0), ("C", 2.0), ("Dm", 2.0), ("Bb", 2.0),  # Chorus 1
            ("Dm", 2.0), ("Bb", 2.0), ("F", 2.0), ("C", 2.0),  # Verse 2
            ("F", 2.0), ("C", 2.0), ("Dm", 2.0), ("Bb", 2.0),  # Chorus 2
        ],
        instrument="guitar",
        repetition_count=1,
        expected_loop=["F", "C", "Dm", "Bb"],  # Chorus progression expected as top loop
        split="val",
        dataset_type="CONTROLLED_AUDIO"
    ),

    # ══════════════════════════════════════════════════════════════
    #  HOLDOUT / NEGATIVE TEST SUITE (Safety against False Confidence)
    # ══════════════════════════════════════════════════════════════
    BenchmarkCase(
        name="holdout_sustained_single_chord",
        category="no_loop_sustained",
        description="Sustained single C chord over 16 seconds (Must NOT yield fake C-C-C-C loop)",
        progression_spec=[("C", 16.0)],
        instrument="piano",
        repetition_count=1,
        expected_loop=None,  # Must reject fake loop
        split="holdout",
        dataset_type="CONTROLLED_AUDIO"
    ),
    BenchmarkCase(
        name="holdout_through_composed_no_repeat",
        category="no_loop_through_composed",
        description="Through-composed 8-chord progression without 4-chord repetition",
        progression_spec=[
            ("C", 2.0), ("Em", 2.0), ("Am", 2.0), ("Dm", 2.0),
            ("G", 2.0), ("Bdim", 2.0), ("F", 2.0), ("Ab", 2.0)
        ],
        instrument="piano",
        repetition_count=1,
        expected_loop=None,
        split="holdout",
        dataset_type="CONTROLLED_AUDIO"
    ),
    BenchmarkCase(
        name="holdout_silent_audio",
        category="no_chord_silence",
        description="Pure silent audio (Must refuse to fabricate chords)",
        progression_spec=[("N", 12.0)],
        instrument="piano",
        repetition_count=1,
        expected_loop=None,
        split="holdout",
        dataset_type="CONTROLLED_AUDIO"
    ),
]


def get_benchmark_cases(split: Optional[str] = None, dataset_type: Optional[str] = None) -> List[BenchmarkCase]:
    """Returns benchmark cases filtered by split ('dev', 'val', 'holdout') and/or dataset_type."""
    cases = BENCHMARK_REGISTRY
    if split is not None:
        cases = [c for c in cases if c.split == split]
    if dataset_type is not None:
        cases = [c for c in cases if c.dataset_type == dataset_type]
    return cases
