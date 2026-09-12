# HotChords Confidence Calibration & Semantics Audit Report (Phase 6)

## 1. Audit of Phase 5 Calibration Discrepancy

Phase 5 reported the following metrics:
- $\text{ECE} = 0.1045$
- $\text{MCE} = 0.8500$
- $\text{Brier Score} = 0.0142$
- Distribution:
  - `[0.80 - 0.89]`: Count = 3, Accuracy = 0%
  - `[0.90 - 1.00]`: Count = 500, Accuracy = 100%

### Root Cause Analysis
An independent code audit of `lv_chordia_engine.py` revealed that chord events were previously assigned a hardcoded heuristic confidence value:
```python
conf = 0.50 if ev.get('is_no_chord') else 0.90
```

1. **Why almost all predictions were in [0.90, 1.00]**:
   Every non-silent chord was assigned an arbitrary baseline confidence of `0.90`.
2. **Why MCE was 0.8500 with 0% accuracy in [0.80 - 0.89]**:
   On synthetic test samples, exactly 3 transition/boundary frames had minor timing shifts that received heuristic adjustments into the `0.85` range and were scored as incorrect.
   The calibration gap for that single bin was $|0.0 - 0.85| = 0.8500$.
3. **Mathematical Derivation of ECE**:
   $$\text{ECE} = \sum_{m=1}^M \frac{|B_m|}{N} \left| \text{acc}(B_m) - \text{conf}(B_m) \right| = \left( \frac{3}{503} \times |0.0 - 0.85| \right) + \left( \frac{500}{503} \times |1.0 - 0.90| \right) = 0.00507 + 0.09940 = 0.1045$$
   The resulting ECE was purely an artifact of hardcoded heuristic confidence and did NOT reflect statistical probability calibration.

---

## 2. Policy Decision: No Calibration Without Independent Ground Truth

In accordance with MIR best practices:
- **No Fabricated Isotonic Regression / Temperature Scaling**: We do NOT fit calibration models on small synthetic test cases.
- **Internal Status Declaration**:
  ```python
  confidence_calibration_status = "INSUFFICIENT_GROUND_TRUTH"
  ```
- **Transparent Semantics**: User-facing "Chord Confidence" is explicitly documented as a **composite heuristic reliability indicator** and not a frequentist/Bayesian probability.

---

## 3. Disambiguated Reliability Semantics Architecture

To prevent conflation, HotChords maintains explicit independent fields:

1. `model_confidence`: Duration-weighted local stability score from the recognition engine.
2. `harmonic_strength`: Physical tonality estimate ($1 - \text{spectral\_flatness}$, chroma entropy, HPSS ratio).
3. `temporal_stability`: Chord duration consistency metric (penalizes high-frequency flickering/jitter).
4. `beat_alignment`: Temporal boundary proximity to detected downbeat/beat onsets.
5. `source_agreement`: Musical chord overlap across separated stems.
6. `overall_reliability`: Multi-dimensional synthesized reliability metric ($[0.0, 1.0]$).
