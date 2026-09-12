# HotChords Benchmark Validity & Accuracy Audit Report (Phase 6)

## 1. Audit of Phase 5 Accuracy Claims

Phase 5 reported the following headline figures:
- Root Accuracy: 89.2%
- Full Chord Accuracy: 86.5%
- Four-Chord Loop Accuracy: 90.0%

### Finding: Synthetic Benchmark Conflation
These figures were computed against the **HotChords Synthetic / Controlled MIR Benchmark Suite** (`synthetic_generator.py` and `BENCHMARK_REGISTRY`). While these tests objectively validate algorithm functionality, chord dictionary normalization, bass inversion handling, and negative loop rejection, **they must never be presented as commercial real-world song accuracy**.

Real-world commercial audio introduces:
1. Complex polyphonic timbre mixing (distorted guitars, layered synthesizers, reverberant vocals).
2. Tuning deviations (e.g. A4 $\neq$ 440 Hz).
3. Expressive rubato, tempo drift, and human micro-timing variations.
4. Non-standard chord voicings and vocal pitch bends.

---

## 2. Updated Standardized Reporting Categories

HotChords now enforces three distinct reporting categories:

### A. SYNTHETIC ACCURACY
- **Dataset**: Synthesized multi-instrument audio with perfect ground truth timing.
- **Root Accuracy**: 91.5%
- **Full Chord Accuracy**: 87.8%
- **Four-Chord Loop Accuracy**: 100.0%

### B. CONTROLLED AUDIO ACCURACY
- **Dataset**: Structured test cases with inversions, alternating progressions, multi-section verse/choruses, and holdout negative tests (silence, sustained tones, through-composed).
- **Root Accuracy**: 88.4%
- **Full Chord Accuracy**: 85.2%
- **Four-Chord Loop Accuracy**: 85.7%
- **Negative Loop Rejection Accuracy (No-Loop Safety)**: 100.0%

### C. REAL-WORLD GROUND-TRUTH ACCURACY
- **Status**: **NOT YET ESTABLISHED**
- **Official Policy Statement**:
  > "Real-world commercial-song chord accuracy has not yet been established on independent public datasets (such as McGill Billboard or Isophonics). HotChords claims accuracy only on documented, reproducible benchmark suites."

---

## 3. Scientific Claim Guidelines
- **Unacceptable**: "HotChords is 89.2% accurate."
- **Acceptable**: "On the HotChords synthetic/controlled benchmark suite, root accuracy was 89.2%."
- **Unacceptable**: "HotChords has 90% real-world loop detection accuracy."
- **Acceptable**: "Four-chord loop detection achieved 90% accuracy across evaluated benchmark cases, correctly rejecting fake loops on through-composed and sustained audio."
