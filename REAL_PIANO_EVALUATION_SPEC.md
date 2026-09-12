# HotChords Real-Piano Evaluation & Acoustic Validation Specification

---

## 1. Ground-Truth Status Declaration

```python
REAL_PIANO_GROUND_TRUTH = "NOT_AVAILABLE"
```

### 1.1 Status & Scientific Integrity
HotChords does not bundle an authoritative, multi-microphone acoustic dataset of real acoustic piano performances with certified, frame-by-frame note and chord ground truth.

In adherence to strict scientific and engineering rigor:
- **HotChords does NOT manufacture or simulate fake real-piano accuracy percentages.**
- All accuracy metrics reported in regression benchmarks are clearly demarcated as **Synthetic Acoustic DSP Benchmarks** or **Heuristic Feature Consistency Scores**.
- Real-world acoustic recordings present in the workspace (`test songs/`) are user-provided mixed commercial tracks without isolated piano stems or public ground-truth annotations, marked strictly as `ground_truth_status = UNAVAILABLE`.

---

## 2. Evaluation Infrastructure Architecture

HotChords maintains a two-tier evaluation infrastructure:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   HOTCHORDS EVALUATION INFRASTRUCTURE                   │
├──────────────────────────────────┬─────────────────────────────────────┤
│   TIER 1: SYNTHETIC EVALUATION   │     TIER 2: REAL-WORLD PROTOCOL     │
│   (Automated Regression Suite)   │   (Future Multi-Acoustic Trials)    │
├──────────────────────────────────┼─────────────────────────────────────┤
│ • Deterministic Signal Synthesizer│ • Upright vs Grand Piano Trials    │
│ • Exponential Decay & Overtones  │ • Multi-Mic Transducer Profiles     │
│ • Detuning & Inharmonicity Models│ • Ambient Room Acoustics & Reverberation│
│ • Additive White/Pink Noise Tests│ • Physical Key Strike Velocities    │
│ • Automated WCOR & F1 Metrics    │ • Human-in-the-Loop Ground Truth    │
└──────────────────────────────────┴─────────────────────────────────────┘
```

---

## 3. Tier 1: Synthetic Evaluation Harness

### 3.1 Acoustic Synthesis Physics Model
The synthetic test harness in [`backend/analysis/test_signals.py`](file:///Volumes/TIKDI/APP%20Development/HotChords%20App/backend/analysis/test_signals.py) synthesizes piano-like acoustic signals:
- **Decay Envelope**: Fast percussive attack ($5\text{ ms}$) followed by exponential decay $\exp(-\lambda t)$ where $\lambda \in [1.5, 3.5]$.
- **Harmonic Series**: 6 discrete overtones with decay rate proportional to harmonic index:
  $$s(t) = \sum_{h=1}^{H} \frac{1}{h^{1.2}} \sin(2\pi h f_0 t) \exp\left(-\lambda (1 + 0.35(h-1)) t\right)$$
- **Inharmonicity / Detune**: Detuning offsets $\delta \in [-50, +50]\text{ cents}$.
- **Signal-to-Noise Ratio (SNR)**: Additive Gaussian white noise and $1/f$ pink noise at $-20\text{ dB}$ to $+30\text{ dB}$ SNR.

### 3.2 Evaluation Metrics
- **Weighted Chromagram / Note Accuracy (WCOR)**:
  $$\text{WCOR} = \frac{\sum_t \mathbf{C}_{\text{pred}}(t) \cdot \mathbf{C}_{\text{true}}(t)}{\sum_t \|\mathbf{C}_{\text{true}}(t)\|}$$
- **Polyphonic Precision, Recall, and F1-Score**:
  $$\text{Precision} = \frac{|P \cap T|}{|P|}, \quad \text{Recall} = \frac{|P \cap T|}{|T|}, \quad F_1 = \frac{2 \cdot P \cdot R}{P + R}$$
- **Boundary Jitter Error**: Mean absolute deviation (in milliseconds) between true chord transition boundaries and detected segment boundaries.

---

## 4. Tier 2: Real-Piano Recording & Validation Protocol

When real-piano recording sessions are conducted in future trials, the following formal protocol MUST be followed:

### 4.1 Acoustic Environment Matrix
| Dimension | Minimum Target | Description |
|---|---|---|
| **Piano Types** | Upright & Grand | Minimum 1 acoustic upright (e.g. Yamaha U1/U3) and 1 grand piano (e.g. Yamaha C3/Steinway B). |
| **Microphone Setup** | 3 Configurations | 1. Built-in Laptop Mic ($0.5\text{m}$ distance)<br>2. USB Condenser Mic ($1.0\text{m}$ distance)<br>3. Stereo Pair over soundboard ($0.3\text{m}$ distance) |
| **Dynamic Range** | $pp$ to $ff$ | Soft practice dynamics ($40\text{ dB SPL}$) to vigorous fortissimo ($85\text{ dB SPL}$). |
| **Acoustic Rooms** | Dry & Live | Dry bedroom/studio ($RT_{60} \approx 0.25\text{s}$) and live living room ($RT_{60} \approx 0.65\text{s}$). |

### 4.2 Annotation & Provenance Standard
- Every recording must be paired with an authoritative MIDI ground-truth log recorded synchronously via MIDI optical sensors or verified manual note-by-note annotation.
- Formatted as `JSON` with millisecond-exact `note_on`, `note_off`, `midi_number`, `velocity`, and `pitch_name`.
- Files must be hashed with SHA-256 and registered via `RealSongTrack` in `backend/benchmarks/real_song_dataset.py` with `ground_truth_status = "AVAILABLE"`.

---

## 5. Summary
The separation between synthetic unit/regression testing and real-world acoustic validation guarantees honest, uninflated accuracy metrics while establishing a clean, rigorous pathway for physical acoustic benchmarking.
