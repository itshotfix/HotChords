# HotChords v0.3 — Codebase Changes & Engineering Summary

> **Summary Document for ChatGPT / AI Context**
> **Project:** HotChords v0.3 (Interactive Desktop Piano Workstation)
> **Platform:** Vanilla JavaScript, CSS3, SVG, Python/FastAPI Backend, Web Animations API (WAAPI).

---

## 1. Overview of Changes

We completed a comprehensive 4-phase UI/UX and animation re-engineering initiative for **HotChords v0.3**. The goal was to establish deterministic synchronization between the playback clock, 3-chord timeline, hand diagrams, and docked 61-key piano without layout shifts, visual clipping, or animation drift.

---

## 2. Summary of Modified Code Files

### A. [`frontend/js/ui/workspaceChordTimeline.js`](file:///Volumes/TIKDI/APP%20Development/HotChords%20App/frontend/js/ui/workspaceChordTimeline.js)
* **Purpose:** High-performance 3-chord physical sliding carousel (`PREVIOUS ← CURRENT HERO → NEXT`).
* **Key Code Modifications:**
  - **Stationary Structural Anchor Alignment:** Aligned horizontal lane displacement $D = \text{viewportWidth} \times 0.375$ with the fixed $25\% / 50\% / 25\%$ column labels (`PREVIOUS`, `CURRENT CHORD`, `NEXT`).
  - **4-Lane Hardware-Accelerated WAAPI Transitions:**
    - Old Previous: $-1D \to -2D$ (scale $0.65 \to 0.38$, opacity $0.40 \to 0$).
    - Current: $0 \to -1D$ (scale $1.15 \to 0.65$, opacity $1.0 \to 0.40$).
    - Next: $+1D \to 0$ (scale $0.65 \to 1.15$, opacity $0.45 \to 1.0$, hero glow).
    - Incoming Next: $+2D \to +1D$ (scale $0.38 \to 0.65$, opacity $0 \to 0.45$).
  - **Seeking Lifecycle:** Any seek immediately cancels in-flight WAAPI animation objects, removes transient DOM elements, and snaps cleanly to the target resting state.
  - **Pause/Resume & Resize:** Pausing preserves visual progress; resuming continues seamlessly; `ResizeObserver` recalculates card resting positions on any window resize.

---

### B. [`frontend/js/ui/handDiagrams.js`](file:///Volumes/TIKDI/APP%20Development/HotChords%20App/frontend/js/ui/handDiagrams.js)
* **Purpose:** Generates anatomically proportional SVG vector markup for Left and Right hands.
* **Key Code Modifications:**
  - **Anatomical Proportions:** Widened finger silhouettes ($24$–$28\text{px}$ width) in a $200 \times 230$ coordinate viewBox.
  - **Protrusion Fix:** Reduced finger dot badges ($r=9.5$–$10\text{px}$, diameter $19$–$20\text{px}$) with $2$–$4\text{px}$ margin inside finger boundaries—completely preventing badges from sticking out.
  - **Upright Left Hand Typography:** Rendered direct mirrored coordinates for the Left Hand ($x' = 200 - x$) rather than reverse SVG transforms, ensuring finger numbers $1$–$5$ remain upright and crisp across all browsers.

---

### C. [`frontend/js/ui/workspaceHandController.js`](file:///Volumes/TIKDI/APP%20Development/HotChords%20App/frontend/js/ui/workspaceHandController.js)
* **Purpose:** Coordinates real-time hand guidance, active finger state, downward compression, and note chips.
* **Key Code Modifications:**
  - **Downward Keybed Compression:** When chords activate, relevant fingers descend $6\text{px}$ (`translate3d(0, 6px, 0)`) over $130\text{ms}$ with `cubic-bezier(0.22, 1, 0.36, 1)` and illuminate with the 5-color pedagogical palette (Thumb: Red, Index: Orange, Middle: Green, Ring: Teal, Pinky: Blue).
  - **Repeated Finger Strike Detection:** Tracks active finger history between consecutive chords. When the same finger is required in consecutive chords, it executes a distinct physical re-strike pulse ($6\text{px} \to 1\text{px} \to 7\text{px} \to 6\text{px}$) over $140\text{ms}$ so the user sees clear tactile feedback.
  - **Zero Timer Overhead:** Synchronized directly with `PlaybackClock` and `CurrentChordEngine`. Zero independent timers or `setInterval` calls.

---

### D. [`frontend/css/piano.css`](file:///Volumes/TIKDI/APP%20Development/HotChords%20App/frontend/css/piano.css)
* **Purpose:** Primary stylesheet for the single-workspace desktop workstation.
* **Key Code Modifications:**
  - **Structural Labels Row (`.ws-fixed-labels-row`):** Placed completely outside the animated viewport; constrained to `max-width: clamp(480px, 70vw, 860px)`.
  - **Chord Viewport (`.ws-chord-viewport`):** Aligned with the header labels row to ensure zero geometric drift.
  - **Hero Current Chord (`.chord-card-name--hero`):** Refined dominant typography (`clamp(3.4rem, 7.8vw, 5.8rem)`), resting scale $1.15$, opacity $1.0$, and multi-layered blue glow.
  - **Hand Column Proportions (`.ws-hand-svg`):** Sized to `clamp(140px, 17vw, 210px)` width and `clamp(145px, 18vw, 220px)` height to eliminate vertical dead space while maintaining balance with note chips.

---

## 3. New Engineering & Documentation Files Created

1. [`.agents/skills/hotchords-ui-ux/SKILL.md`](file:///Volumes/TIKDI/APP%20Development/HotChords%20App/.agents/skills/hotchords-ui-ux/SKILL.md)
   - Project-specific UI/UX standards: strict single workspace, fluid non-brittle layout, zero viewport-specific hacks, visual dominance rules.
2. [`.agents/skills/hotchords-animation/SKILL.md`](file:///Volumes/TIKDI/APP%20Development/HotChords%20App/.agents/skills/hotchords-animation/SKILL.md)
   - Animation engineering standards: `PlaybackClock` as single clock authority, WAAPI / Motion for JS, composite properties (`transform`, `opacity`), repeated finger strike principles.
3. [`docs/UI_UX_BUG_SPECIFICATION.md`](file:///Volumes/TIKDI/APP%20Development/HotChords%20App/docs/UI_UX_BUG_SPECIFICATION.md)
   - Technical bug specification and source-of-truth mapping for all 6 known issues and 9 core subsystems.
4. [`scripts/phase4_qa_validation.js`](file:///Volumes/TIKDI/APP%20Development/HotChords%20App/scripts/phase4_qa_validation.js)
   - Automated browser QA script validating 4 real songs, 8 viewports, and generating high-resolution verification screenshots.

---

---

## 5. Phase 1–4 Audio Intelligence & MIR Foundation Upgrade

In addition to the UI/UX synchronization, we completed the 4-phase core Audio / Music Information Retrieval (MIR) architecture upgrade:

### Phase 1 — Audio Profiling, QC & Reliability Metadata
- **Objective Acoustic Profiler** ([backend/analysis/profiling.py](file:///Volumes/TIKDI/APP%20Development/HotChords%20App/backend/analysis/profiling.py)): Computes objective SNR, dynamic range, spectral centroid, spectral rolloff, clipping ratio, and silent region detection.
- **Timing Grid Abstraction** ([backend/analysis/timing.py](file:///Volumes/TIKDI/APP%20Development/HotChords%20App/backend/analysis/timing.py)): Delivers beat/downbeat grids, tempo estimation, and subdivision alignment without brittle hardcoding.
- **Quality Control Gating & AudioStatus**: Transparently handles silent, clipped, or corrupted audio with explicit status reasons without crashing or inventing fake chords.

### Phase 2 — Modern Automatic Chord Recognition & Normalization
- **Large-Vocabulary Chord Engine** ([backend/analysis/lv_chordia_engine.py](file:///Volumes/TIKDI/APP%20Development/HotChords%20App/backend/analysis/lv_chordia_engine.py)): Deep ensemble chord transcription powered by bundled `lv-chordia` with fallback to Classical CQT Chroma correlation (`legacy_engine.py`).
- **Standardized Chord Normalization** ([backend/theory/normalization.py](file:///Volumes/TIKDI/APP%20Development/HotChords%20App/backend/theory/normalization.py)): Normalizes raw MIR symbols into standard root/quality and beginner-friendly representations.
- **Temporal Smoothing Post-Processing** ([backend/analysis/temporal_postprocessing.py](file:///Volumes/TIKDI/APP%20Development/HotChords%20App/backend/analysis/temporal_postprocessing.py)): Beat snapping, transient spike removal ($<100\text{ms}$), and adjacent identical chord merging.

### Phase 3 — Multi-Source Harmonic Analysis & Evidence Routing
- **Instrument Evidence Scoring** ([backend/analysis/instrument_evidence.py](file:///Volumes/TIKDI/APP%20Development/HotChords%20App/backend/analysis/instrument_evidence.py)): Evaluates harmonic energy, spectral flatness, and chord consistency across separated stems (`piano`, `guitar`, `other`, `bass`).
- **Harmonic Evidence Router** ([backend/analysis/harmonic_evidence.py](file:///Volumes/TIKDI/APP%20Development/HotChords%20App/backend/analysis/harmonic_evidence.py)): Dynamically routes harmony analysis to the strongest harmonic carrier while strictly excluding non-harmonic sources (`drums`, `vocals`).
- **Bass Fusion & Source Agreement** ([backend/analysis/source_agreement.py](file:///Volumes/TIKDI/APP%20Development/HotChords%20App/backend/analysis/source_agreement.py)): Detects slash chords / inversions from the bass register ($C/E$, $G/B$) and applies agreement confidence boosts when multiple stems concur.

### Phase 4 — Song Structure, Repeating Sections, 4-Chord Loop & Playback Sync
- **Musical Structure Analysis** ([backend/analysis/structure.py](file:///Volumes/TIKDI/APP%20Development/HotChords%20App/backend/analysis/structure.py)): Computes chroma self-similarity recurrence matrices (SSM) and novelty boundary peaks to identify objective structural blocks without fabricating labels.
- **Four-Chord Loop Detection** ([backend/analysis/loop_detection.py](file:///Volumes/TIKDI/APP%20Development/HotChords%20App/backend/analysis/loop_detection.py)): Extracts 4-chord sliding progression windows, verifies recurrence under modulo-12 transposition-invariant delta cycles, rejects sustained single chords ($C|C|C|C$), and scores candidates objectively.
- **Authoritative Clock Synchronization** ([frontend/js/audio/playbackClock.js](file:///Volumes/TIKDI/APP%20Development/HotChords%20App/frontend/js/audio/playbackClock.js)): Implemented seamless dual-playback (`PIANO` and `ORIGINAL`), position preservation on mode switch, and zero-drift loop boundary wrapping (`seek(loop.start)`).

---

## 6. Full Test Suite Validation

- **Python Pytest Suite:** **97 / 97 PASSED** (`tests/test_*.py`).
- **Node.js Playback & Clock Suite:** **9 / 9 PASSED** (`tests/test_phase4_playback_sync.js`).
- **Regressions / Test Failures:** **0**.
