# HotChords Phase 6-0: Pre-Phase Architecture Audit

This architectural audit evaluates the HotChords codebase in preparation for **Phase 6: Beginner Learning Experience**.

---

## 1. Current Architecture Overview

HotChords follows a strictly decoupled, domain-bounded architecture where data models, audio engines, synchronization clocks, and user interface components operate independently:

```
                            SONG AUDIO / FILE
                                    │
                                    ▼
                         Audio Analysis Pipeline
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
            Demucs Separation               Chord Analysis
            & Silero VAD / ASR              (HPSS, CQT, HMM)
                    │                               │
                    ▼                               ▼
            Precise Lyrics                 Original Chords
                    │                               │
                    │                      Simplification Engine
                    │                               │
                    │                               ▼
                    │                        Beginner Chords
                    │                               │
                    └───────────────┬───────────────┘
                                    ▼
                              SongTimeline
                      (Single Source of Truth)
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
  PlaybackClock            PianoPlaybackService        LyricsChordRenderer &
(Monotonic Time)         (Tone.Sampler / WebAudio)     BeginnerChartRenderer
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                    ▼
                     UnifiedPianoPlaybackController
                                    │
                                    ▼
                       HotChords Interactive UI
```

---

## 2. Component Inspection & Audit Results

### 1. Timeline & State Representations
- **Audit**: Inspected `backend/models/timeline.py` (`SongTimeline`, `ChordEvent`, `LyricWord`, `LyricLine`, `SectionEvent`).
- **Finding**: Single canonical representation in backend with Pydantic v2 validation. `original_chords` and `beginner_chords` are stored as distinct arrays on the same timeline without mutation or data collisions.
- **Status**: **PASS** — No duplicate or competing timeline representations.

### 2. Clocks & Timers
- **Audit**: Inspected `frontend/js/audio/playbackClock.js`, `songAudioController.js`, `originalChordPlaybackController.js`, `beginnerChordPlaybackController.js`, `unifiedPianoPlaybackController.js`.
- **Finding**: Single authoritative time source (`PlaybackClock.currentTime`) driven by monotonic `performance.now()` with exact rate scaling ($1.0\times, 0.75\times, 0.5\times$). Playback controllers do not run competing `setInterval` loops or secondary clocks; they schedule events directly on the hardware audio clock or synchronize on clock ticks.
- **Status**: **PASS** — Single clock architecture verified.

### 3. AudioContext Management
- **Audit**: Inspected `frontend/js/audio/pianoPlaybackService.js` and `songAudioController.js`.
- **Finding**: Single shared `AudioContext` managed by `PianoPlaybackService`. `SongAudioController` uses an `HTMLAudioElement` with native pitch preservation (`preservesPitch = true`), avoiding redundant Web Audio contexts.
- **Status**: **PASS** — Zero duplicate AudioContexts.

### 4. Tone.Sampler Instances
- **Audit**: Inspected `frontend/js/audio/pianoPlaybackService.js`.
- **Finding**: Single `Tone.Sampler` (and fallback Web Audio buffer pool) instantiated once during `PianoPlaybackService.initialize()`. `OriginalChordPlaybackController` and `BeginnerChordPlaybackController` both delegate to the same shared service instance.
- **Status**: **PASS** — Zero duplicate sampler instances.

### 5. Time Units Consistency
- **Audit**: Inspected backend models, API endpoints, and frontend renderers/controllers.
- **Finding**: Strictly **seconds** (float) across all time properties (`startTime`, `endTime`, `duration`, `currentTime`, `overlap_duration`). Milliseconds are only computed locally when interfacing with browser timers or Web Audio lookahead buffers.
- **Status**: **PASS** — Strict seconds-based standard maintained.

### 6. Chord Property Naming & Schema Alignment
- **Audit**: Inspected Pydantic aliases in `backend/models/timeline.py`, legacy export `to_analysis_dict()`, and frontend property accessors.
- **Finding**: Canonical camelCase (`startTime`, `endTime`, `chordName`, `originalChords`, `beginnerChords`) with dual support for legacy dictionary keys (`time`, `end`, `chord`). Frontend controllers defensively resolve both representations (e.g., `c.chordName || c.chord`).
- **Status**: **PASS** — Zero property access mismatch.

### 7. Frontend / Backend Schema Consistency
- **Audit**: Inspected `backend/api/router.py` (`/timeline`, `/result`, `/progress`).
- **Finding**: `/timeline` endpoint returns canonical Pydantic model dump with camelCase aliases. `/result` returns combined structure supporting existing frontend consumers.
- **Status**: **PASS** — Backward and forward compatibility verified.

### 8. Data Duplication & Memory Footprint
- **Audit**: Inspected `backend/alignment/engine.py` and `frontend/js/ui/lyricsChordRenderer.js`.
- **Finding**: `ChordLyricMap` stores indices (`segmentIndex`, `wordIndex`) referencing base transcript data rather than creating deep copies of lyric trees.
- **Status**: **PASS** — Zero unnecessary data duplication.

---

## 3. Reusable Components for Phase 6

Phase 6 (Beginner Learning Experience) should directly leverage the following existing, tested components:

| Component / Utility | File | Reusable Functionality for Phase 6 |
|:---|:---|:---|
| `PianoFingeringEngine` | `frontend/js/engine/pianoFingeringEngine.js` | `getChordVoicing(chordName, notes)`: Computes left/right hand MIDI notes, fingering numbers (1–5), and finger colors. |
| `PianoPlaybackService` | `frontend/js/audio/pianoPlaybackService.js` | Polyphonic chord playback, sample playback, volume/mute control, audio context resumption. |
| `PlaybackClock` | `frontend/js/audio/playbackClock.js` | Central monotonic playback timing, slow-motion practice rates (0.5x, 0.75x, 1.0x), seeking, pause/resume. |
| `UnifiedPianoPlaybackController` | `frontend/js/audio/unifiedPianoPlaybackController.js` | Mode switching between `ORIGINAL_CHORDS` and `BEGINNER_CHORDS`, chord trigger callbacks. |
| `BeginnerChartRenderer` | `frontend/js/ui/beginnerChartRenderer.js` | `detectRepetitions(chords)`: Deterministic progression loop detection for beginner practice routines. |
| `MusicTheoryFormatter` | `frontend/js/engine/musicTheoryFormatter.js` | Musician-friendly chord naming and note formatting. |
| `simplify_progression` | `backend/theory/theory.py` | Music theory simplification, diminished substitutions, and easy-key transposition. |

---

## 4. Dependencies Between Components

```
                    ┌─────────────────────────┐
                    │      SongTimeline       │
                    └────────────┬────────────┘
                                 │
                 ┌───────────────┼───────────────┐
                 ▼               ▼               ▼
         PlaybackClock     PianoService    Lyrics / Chart
                 │               │           Renderers
                 └───────┬───────┘               │
                         ▼                       │
           UnifiedPianoPlaybackController        │
                         │                       │
                         └───────────┬───────────┘
                                     ▼
                          Phase 6 Learning UI
```

---

## 5. Invariants: What Must Remain Untouched

The following systems are complete, fully validated, and **must not be modified** during Phase 6:

1. **`SongTimeline` & `ChordEvent` Data Models** (`backend/models/timeline.py`): The canonical schema must remain invariant.
2. **`PlaybackClock` Implementation** (`frontend/js/audio/playbackClock.js`): High-resolution monotonic clock behavior and rate formulas must remain untouched.
3. **Core Audio Analysis Pipeline** (`backend/analysis/`): Demucs stem separation, HPSS, Chroma CQT, Beat Tracking, and HMM chord detection.
4. **Vocal Transcription & Alignment** (`backend/transcription/`): Silero VAD, faster-whisper, and `PrecisionAlignmentEngine`.
5. **Production UI Layout & Existing Player Controls**: Existing player controls and layout styles.

---

## 6. Identified Issues & Severity

| Issue / Observation | Severity | Recommended Action |
|:---|:---:|:---|
| None (No blocking issues identified) | **None** | Proceed directly to Phase 6 feature implementation using existing modular abstractions. |

---

## 7. Conclusion & Readiness Assessment

### **PHASE 6 READY**

All systems, audio pipelines, timing controllers, theory engines, and data schemas are validated, consistent, and ready for the Beginner Learning Experience.
