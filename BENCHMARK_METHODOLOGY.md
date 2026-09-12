# HotChords MIR Benchmark Methodology & Evaluation Framework

## 1. Overview
The HotChords MIR Benchmark Framework establishes objective, repeatable, and mathematically rigorous evaluation of chord recognition, source stem routing, structural recurrence segmentation, confidence calibration, and 4-chord loop detection without fabricating performance metrics or relying on superficial test assertions.

---

## 2. Evaluation Metrics

### 2.1 Weighted Chord Overlap Ratio (WCOR)
Continuous frame-by-frame integration at $100\text{ Hz}$ resolution ($10\text{ ms}$ bins):

$$\text{WCOR} = \frac{1}{T} \int_{0}^{T} \mathbb{I}(\text{match}(\hat{c}(t), c^*(t))) \, dt$$

We evaluate three hierarchical standard MIR accuracy levels:
1. **Root Accuracy ($\text{WCOR}_{\text{Root}}$)**:
   $$\text{match}_{\text{Root}}(\hat{c}, c^*) = \begin{cases} 1 & \text{if } \text{PitchClass}(\hat{c}) = \text{PitchClass}(c^*) \\ 1 & \text{if } \hat{c} = N \text{ and } c^* = N \\ 0 & \text{otherwise} \end{cases}$$
2. **Major/Minor Accuracy ($\text{WCOR}_{\text{MajMin}}$)**:
   Evaluates root equality and binary harmonic quality class ($\text{Major}$ vs. $\text{Minor}$).
3. **Full Chord Accuracy ($\text{WCOR}_{\text{Full}}$)**:
   Evaluates exact root, harmonic quality (triad, 7th, maj7, min7, dim, aug, sus), and inversion match.

### 2.2 Boundary Alignment Error
- Precision, Recall, and F1-score of chord transition boundaries within a musical tolerance window ($\tau = 250\text{ ms}$ / $\approx 0.5$ beat at $120\text{ BPM}$).
- Mean boundary onset error in milliseconds ($\text{ms}$).

### 2.3 No-Chord ($N$) Precision, Recall & F1
Evaluates the detector's ability to cleanly detect silence, non-harmonic speech, and noise without hallucinating spurious chords:

$$\text{Precision}_N = \frac{\text{TP}_N}{\text{TP}_N + \text{FP}_N}, \quad \text{Recall}_N = \frac{\text{TP}_N}{\text{TP}_N + \text{FN}_N}, \quad F1_N = \frac{2 \cdot \text{Precision}_N \cdot \text{Recall}_N}{\text{Precision}_N + \text{Recall}_N}$$

### 2.4 Four-Chord Loop Evaluation
Evaluates detected 4-chord loops against reference ground truth:
1. **Loop Availability Correctness**: True positive loop discovery and strict rejection of through-composed music, silence, noise, and sustained chords ($C|C|C|C$).
2. **Chords & Sequence Order**: Exact sequence match or circular phase rotation (e.g. $C \to G \to \text{Am} \to F$ starting on $\text{Am}$).
3. **Transposition Invariance**: Evaluates relative root delta cycles modulo 12:
   $$\Delta r_k = (r_{k+1} - r_k) \pmod{12}$$

---

## 3. Benchmark Dataset Splits

| Split | Description | Purpose |
|---|---|---|
| **Development (`dev`)** | Standard Pop, Minor Pop, Synth Vamps, Extended 7th Chords | Diagnostic verification of harmonic representations and engine inference. |
| **Validation (`val`)** | Alternating 4-event loops ($C \to G \to C \to F$), Slash/Inversion chords, Multi-section Verse/Chorus songs | Verification of structural routing, bass inversion fusion, and multi-section progression ranking. |
| **Holdout (`holdout`)** | Sustained single chords (16s $C$), Through-composed non-repeating songs, Silent audio | Negative safety tests: Ensures rejection of fake loops, fake choruses, and ungrounded chord fabrication. |
| **Real Song (`real_song`)** | Commercial multi-track recordings (acoustic, pop ballad, rock, rap) | Empirical auditing of source selection, acoustic distortion handling, and engine disagreement. |

---

## 4. Phase 7: Real-Song Engine Disagreement & Playability Metrics

### 4.1 Cross-Engine Disagreement Taxonomy
Frame-by-frame comparison between primary neural engine (LV-Chordia) and baseline fallback (Legacy CQT Template Matcher):
- `AGREE`: Identical chord or both predicting silence/no-chord.
- `ROOT_AGREE_QUALITY_DISAGREE`: Identical root pitch class, differing harmonic quality.
- `ROOT_DISAGREE`: Different root pitch classes.
- `NO_CHORD_DISAGREEMENT`: One engine predicts chord, the other predicts no-chord.

### 4.2 Beginner Playability Scoring
Evaluates the physical accessibility of detected four-chord loops for novice piano students:

$$P = 0.70 \times S_{\text{simplicity}} + 0.30 \times V_{\text{variety}}$$

Where $S_{\text{simplicity}}$ assigns $1.0$ to white-key naturals, $0.7$ to single accidentals, and $0.3$ to complex clusters, and $V_{\text{variety}}$ rewards balanced 3–4 chord progressions.

---

## 5. Confidence Calibration Framework

Model-reported confidence $p \in [0.0, 1.0]$ is partitioned into 6 standard probability bins:
- $[0.00, 0.49]$
- $[0.50, 0.59]$
- $[0.60, 0.69]$
- $[0.70, 0.79]$
- $[0.80, 0.89]$
- $[0.90, 1.00]$

We measure:
1. **Expected Calibration Error (ECE)**:
   $$\text{ECE} = \sum_{m=1}^{M} \frac{|B_m|}{N} \left| \text{acc}(B_m) - \text{conf}(B_m) \right|$$
2. **Maximum Calibration Error (MCE)**:
   $$\text{MCE} = \max_{m} \left| \text{acc}(B_m) - \text{conf}(B_m) \right|$$
3. **Brier Score**:
   $$\text{Brier} = \frac{1}{N} \sum_{i=1}^{N} (p_i - y_i)^2$$

---

## 6. Performance & Scalability Methodology
We isolate and profile execution time, Real-Time Factor ($\text{RTF} = \frac{T_{\text{analysis}}}{T_{\text{audio}}}$), and Resident Set Size peak memory ($\text{MB}$) across standardized duration increments from 30s to 20m.

To avoid lifetime highwater mark pollution from `resource.getrusage`, benchmarks execute in isolated worker subprocesses and measure instantaneous resident memory via macOS Darwin `task_info` (`mach_task_basic_info_data`).

---

## 7. Provenance Disambiguation & Scientific Honesty Rules

1. **Strict Provenance Partitioning**:
   - `SYNTHETIC`: Generated audio with exact timing ground truth.
   - `CONTROLLED_AUDIO`: Structured multi-section, inverted, and negative edge test cases.
   - `REAL_WORLD`: Commercial recordings under Fair Use analysis.
2. **Prohibition of Misleading Generalization**:
   Synthetic benchmark accuracy must **never** be cited as "real-world commercial accuracy".
   If independent public real-world datasets are not bundled, the system explicitly reports:
   `"Real-world chord accuracy has not yet been established on independent public datasets."`
3. **No Calibration Without Sufficient Data**:
   If sample size is under 1,000 independent multi-track instances, calibration status is set to `INSUFFICIENT_GROUND_TRUTH`. Isotonic regression or temperature scaling must not be fabricated on synthetic test sets.
4. **Source Attribution Rule**:
   Never claim "Chords were detected from guitar" unless an isolated and verified guitar channel exists; harmonic stem extractions must be labeled as `MIXED_HARMONIC_EVIDENCE` or `ORIGINAL_MIX`.
