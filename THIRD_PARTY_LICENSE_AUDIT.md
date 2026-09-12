# Third-Party Dependency and License Audit

## Overview
HotChords is an open-source, local-first music pedagogy and chord analysis application licensed under the **MIT License**. To ensure legal compliance, sustainability, and potential commercial distribution readiness, all third-party code libraries, models, and pretrained weights must be strictly audited and cataloged.

---

## License Summary Table

| Dependency | Version | Purpose | Source Code License | Model / Checkpoint License | Commercial Redistribution Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **librosa** | >= 0.11.0 | Audio analysis, CQT, onset strength, HPSS, chroma extraction | ISC License | N/A (Algorithmic / DSP) | **Permitted** (Commercial use allowed) | Pure DSP / MIR algorithms, no neural network checkpoints. |
| **soundfile** | >= 0.12.0 | Audio file I/O (libsndfile wrapper) | BSD 3-Clause | N/A | **Permitted** (Commercial use allowed) | Wraps libsndfile (LGPL 2.1+). Binary distribution dynamically links to libsndfile. |
| **numpy** | >= 2.0.0 | Numerical arrays and linear algebra operations | BSD 3-Clause | N/A | **Permitted** (Commercial use allowed) | Fundamental numeric computing library. |
| **scipy** | >= 1.13.0 | Signal processing, filtering, statistical calculations | BSD 3-Clause | N/A | **Permitted** (Commercial use allowed) | Standard scientific computation library. |
| **PyTorch (torch)** | >= 2.0.0 | Deep learning runtime engine | Modified BSD-style | N/A | **Permitted** (Commercial use allowed) | Runtime framework for model execution. |
| **Demucs** | >= 4.0.0 | AI Music Source Separation (vocals/drums/bass/other) | MIT License | **CC-BY-NC 4.0 (for default `htdemucs` pretrained weights)** / Non-Commercial | **Restricted / Requires Permission or Alternative Weights for Commercial Use** | While the Demucs Python source code is MIT licensed, the official pretrained models (`htdemucs`, `mdx_extra`) were trained on datasets including MusDB-HQ / internal datasets with Non-Commercial restrictions. For commercial distribution, either train custom models or operate Demucs as an optional, user-downloaded component. |
| **lv-chordia** | >= 1.1.0 | Deep Large-Vocabulary Automatic Chord Recognition | MIT License | **MIT License (5 bundled checkpoints ~28MB)** | **Permitted** (Commercial use allowed) | Pre-trained deep ensemble checkpoints are bundled directly in the package under MIT License. No external network downloads required. |
| **audioop-lts** | >= 0.2.2 | Compatibility library for Python 3.13+ audioop | PSF-2.0 / MIT | N/A | **Permitted** (Commercial use allowed) | Re-provides standard library audioop functionality for modern Python runtimes. |
| **imageio-ffmpeg** | >= 0.4.9 | Bundled FFmpeg binaries for audio decoding | BSD 2-Clause (wrapper) | N/A | **Permitted** (under LGPL/GPL terms of bundled FFmpeg binary) | Uses FFmpeg binaries built under LGPL 2.1 / GPL 3.0. |
| **FastAPI** | >= 0.111.0 | Backend ASGI Web framework | MIT License | N/A | **Permitted** (Commercial use allowed) | Asynchronous API routing. |
| **uvicorn** | >= 0.30.0 | ASGI web server | BSD 3-Clause | N/A | **Permitted** (Commercial use allowed) | Lightweight high-performance server. |
| **pydantic** | >= 2.7.0 | Data validation and canonical schema serialization | MIT License | N/A | **Permitted** (Commercial use allowed) | Schema definitions for SongTimeline & API models. |
| **python-multipart**| >= 0.0.9 | Form / file upload parsing for FastAPI | Apache 2.0 | N/A | **Permitted** (Commercial use allowed) | Multipart form data support. |
| **Tone.js** | ^14.8.49 | Client-side Web Audio synthesis and piano sampler | MIT License | N/A | **Permitted** (Commercial use allowed) | Frontend synthesized piano playback. |

---

## Detailed Model & Dataset Licensing Notes

### Demucs Pretrained Checkpoints (`htdemucs`)
- **Repository Source Code**: MIT License ([facebookresearch/demucs](https://github.com/facebookresearch/demucs))
- **Pretrained Checkpoint Weights**: Released by Meta AI under Creative Commons Attribution-NonCommercial 4.0 International (CC-BY-NC 4.0).
- **Compliance Policy for HotChords**:
  - HotChords separates stems via Demucs only if requested / installed.
  - The core harmonic pipeline operates autonomously using classical DSP (Harmonic-Percussive Source Separation via `librosa.effects.harmonic` and CQT chroma template correlation), providing complete commercial viability out-of-the-box without requiring proprietary or non-commercial model weights.
  - If HotChords is distributed commercially in the future, Demucs weights must either be substituted with commercially trained weights or downloaded directly by end users under their own personal license.

### Phase 4 Structure Analysis & Four-Chord Loop Engines
- **Implementation**: `backend/analysis/structure.py` and `backend/analysis/loop_detection.py`
- **Algorithm Foundation**: Chroma Self-Similarity Recurrence Matrices (SSM), Novelty Curve boundary peak-picking, and Transposition-Invariant Relative Root Modulo-12 Delta Cycles.
- **Dependencies**: Built on `numpy` (BSD 3-Clause), `scipy` (BSD 3-Clause), and `librosa` (ISC License).
- **Licensing Status**: **100% Permissive (MIT / BSD / ISC)**. No neural network checkpoints or restricted datasets are required. Fully compliant with open-source and commercial distribution.

### Phase 11 Real-Time DSP Pitch Detection & Practice Feedback Engine
- **Implementation**: `backend/analysis/realtime_pitch.py`, `backend/theory/practice_feedback.py`, `frontend/js/audio/realtimePitchDetector.js`, `frontend/js/audio/realtimeInputService.js`, `frontend/js/audio/practiceFeedbackBridge.js`.
- **Algorithm Foundation**: Real-time spectral peak interpolation, harmonic comb salience scoring, Wiener entropy inharmonic noise gating, and integer overtone cancellation ($2f_0, 3f_0, 4f_0, 5f_0$).
- **Dependencies**: Pure native Web Audio API (client-side) and `numpy` / `scipy` (BSD 3-Clause). Zero external cloud transcription APIs, zero neural network checkpoints, zero commercial/GPL dependencies.
- **Licensing Status**: **100% Permissive (MIT / BSD)**. Fully compliant with local-first, offline open-source and commercial distribution.

### Phase 12 Input Calibration, Signal Quality & Practice Metrics Engine
- **Implementation**: `backend/analysis/input_calibration.py`, `backend/theory/practice_metrics.py`, `frontend/js/audio/inputCalibrationService.js`, `frontend/js/audio/practiceMetricsTracker.js`.
- **Algorithm Foundation**: Ambient noise floor estimation, dynamic noise gate derivation, Wiener entropy inharmonic gating, bounded event ring buffers ($N=50$), and deterministic chord mastery heuristics.
- **Dependencies**: Built purely on Python standard library, `pydantic` (MIT), `numpy` / `scipy` (BSD 3-Clause), and standard Web Audio API. Zero external cloud dependencies, zero persistent audio recordings.
- **Licensing Status**: **100% Permissive (MIT / BSD)**. Fully compliant with open-source and commercial distribution.


