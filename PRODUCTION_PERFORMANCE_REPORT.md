# HotChords Production Performance Report (Phase 6)

## Executive Summary
This report presents the empirical performance, memory consumption, latency, and scalability characteristics of the HotChords MIR audio intelligence pipeline following Phase 6 production hardening.

## 1. Benchmarked Duration Scaling
Measurements conducted under clean isolated processes with Darwin `task_info` instantaneous Resident Set Size (RSS) monitoring:

| Audio Duration | Load Time | HPSS Time | Chroma CQT | Chord Inference | Structure Time | Loop Detection | Total Time | RTF (Speed) | Peak RSS |
|---|---|---|---|---|---|---|---|---|---|
| **30s (0.5m)** | 0.27s | 1.49s | 0.11s | 2.48s | 0.001s | 0.000s | 4.35s | 0.145x | **992.7 MB** |
| **60s (1.0m)** | 0.28s | 3.10s | 0.20s | 3.37s | 0.001s | 0.000s | 6.95s | 0.116x | **1,466.2 MB** |
| **180s (3.0m)** | 0.29s | 9.27s | 0.58s | 6.85s | 0.003s | 0.001s | 17.00s | 0.094x | **3,348.6 MB** |
| **300s (5.0m)** | 0.30s | 15.47s | 0.97s | 10.48s | 0.006s | 0.002s | 27.23s | 0.091x | **4,096.0 MB** |
| **600s (10.0m)** | 0.33s | 30.85s | 1.94s | 25.02s | 0.020s | 0.003s | 58.16s | 0.097x | **4,096.0 MB** |
| **1200s (20.0m)** | 0.45s | 61.87s | 4.08s | 57.48s | 0.064s | 0.009s | 123.95s | 0.103x | **4,096.0 MB** |

> **Real-Time Factor (RTF)**: Across all song durations, the analysis pipeline operates at **0.09x - 0.14x RTF** (over **7x - 10x faster than real time**).

---

## 2. Cold vs. Cached Run Latency
- **Cold Run (including initial model compilation & import)**: ~5.8s for 30s audio.
- **Warm Run**: ~2.5s for 30s audio.
- **Cached Stem Run (reusing separated tracks)**: ~1.2s for 30s audio (79% speedup).

---

## 3. Hardware & Environment Specifications
- **Host OS**: macOS Darwin 24.6.0 (Apple Silicon)
- **Python Runtime**: Python 3.14.6
- **Deep Learning Engine**: PyTorch 2.10.0 with inference-mode execution
- **Audio Processing**: Librosa 0.11.0 / SoundFile / Scipy
