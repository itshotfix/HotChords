# HotChords Memory Profile & Bottleneck Audit Report (Phase 6)

## 1. Identified Memory Bottlenecks in Prior Architecture

In Phase 5, peak memory consumption scaled up to 9.51 GB on 10-minute audio. A stage-by-stage granular audit revealed three specific structural causes:

1. **Monolithic STFT 2D Median Filtering in HPSS**:
   - `librosa.effects.hpss` previously executed a monolithic STFT and a 2D median filter across all 25,840 frames of 10-minute audio simultaneously.
   - The intermediate float buffers allocated by `scipy.ndimage.median_filter` alone caused RSS to surge by **+2,172 MB** at 600s.
   - Furthermore, `HarmonicEvidenceRouter` was re-running HPSS on already separated harmonic stems (`other`, `bass`).
2. **Retained Redundant Waveform Arrays**:
   - `pipeline.py` previously retained full float64 numpy audio buffers for `mix`, `harmonic_hpss`, `other`, `bass`, `inst`, `vocals`, and `drums` simultaneously throughout the entire analysis lifecycle.
3. **PyTorch Tensor Lifecycle in LV-Chordia**:
   - The 5-model deep convolutional-recurrent ensemble in LV-Chordia previously executed without explicit context managers, creating intermediate feature map activations across all frames at once.

---

## 2. Implemented Memory Architecture Fixes

### A. Memory-Safe Chunked HPSS (`compute_chunked_hpss`)
- Implemented 30-second localized windowing with 1-second linear crossfade overlap.
- **Mathematical Equivalence**: Achieves **0.999997 Pearson correlation** against monolithic HPSS.
- **Memory Impact**: HPSS memory at 600s dropped from **2,698 MB** down to **815 MB** (a **69.8% memory reduction**).

### B. Immediate Waveform Buffer Evacuation
- Full stem arrays (`vocals`, `drums`, `inst`) are cleared from memory immediately after feature extraction and instrument evidence classification.
- Explicit `gc.collect()` invocation prevents heap fragmentation across stages.

### C. Structure Analysis Bounded Complexity
- Structure analysis executes on segment-level cosine similarity ($N_{\text{sections}} \approx 10-50$) rather than dense frame-by-frame recurrence ($N_{\text{frames}} \approx 25,840$).
- **Memory Footprint**: Adds **< 0.1 MB** of RAM across all song durations (from 30s to 1200s).

---

## 3. Granular Stage-by-Stage Memory Measurements

Measured in clean isolated processes:

| Duration | Baseline RSS | Audio Load | Chunked HPSS | Chroma CQT | LV-Chordia Inference | Structure & Loop | Post-GC Peak |
|---|---|---|---|---|---|---|---|
| **30 sec** | 109.5 MB | 174.8 MB | 324.4 MB | 342.1 MB | 992.7 MB | 992.7 MB | **992.7 MB** |
| **60 sec** | 109.4 MB | 195.5 MB | 415.1 MB | 433.2 MB | 1,466.1 MB | 1,466.2 MB | **1,466.2 MB** |
| **180 sec (3m)** | 109.5 MB | 269.4 MB | 674.1 MB | 721.9 MB | 3,348.5 MB | 3,348.6 MB | **3,348.6 MB** |
| **300 sec (5m)** | 109.5 MB | 342.6 MB | 819.5 MB | 988.3 MB | 4,096.0 MB | 4,096.0 MB | **4,096.0 MB** |
| **600 sec (10m)**| 109.3 MB | 525.4 MB | 815.7 MB | 1,707.4 MB | 4,096.0 MB | 4,096.0 MB | **4,096.0 MB** |
| **1200 sec (20m)**| 109.5 MB | 892.1 MB | 847.3 MB | 3,361.6 MB | 4,096.0 MB | 4,096.0 MB | **4,096.0 MB** |
