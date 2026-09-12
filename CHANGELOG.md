# Changelog

All notable changes to HotChords are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [v0.4.0] — Harmonic Intelligence, Four-Chord Loop & Real-Time Practice (2026-09-12)

### Added
- **Multi-Engine Harmonic Evidence Router:** Ensemble consensus combining `lv-chordia` deep neural chord transcription with CQT Chroma fallback and slash chord / bass fusion.
- **Harmonic Source & Instrument Attribution:** Identifies the primary harmonic carrier (`Harmonic Stem`, `Piano`, `Guitar`, `Original Mix`) while strictly excluding drums and vocals.
- **Chord Confidence & Mathematical Transparency:** Computes explicit reliability metrics ($0\dots100\%$) based on harmonic strength ($40\%$), temporal stability ($35\%$), and beat alignment ($25\%$), with detailed breakdown tooltips in the UI.
- **Four-Chord Loop Practice Engine:** Sliding 4-chord progression detection under modulo-12 transposition invariants with automatic zero-drift hardware loop binding (`0:00 - 0:20`).
- **Adaptive Beginner Chord Simplification:** Intelligently maps extended and jazz chords into clean root-position triads while preserving structural harmony.
- **Dynamic Piano Voicings & Ergonomic Fingering:** Voice-led chord inversions and biomechanical finger assignment ($1\dots5$) displayed on an interactive 88-key piano keyboard and hand diagrams.
- **Dual-Source Audio Architecture:** Full mutual exclusivity between polyphonic Salamander Grand Piano synthesizer and original track audio playback with OS-level pitch preservation.
- **Real-Time Microphone Practice Mode:** Low-latency client-side YIN autocorrelation pitch detection with note tolerance ($150\text{ms}$ window) and practice metrics tracking.
- **Comprehensive Automated Test Suite:** 195 Python backend tests and 55 Node client test suites covering MIR DSP, source separation, playback lifecycle, and practice calibration.
- **Standalone Windows x64 Installer:** Packaged standalone installer (`HotChords-v0.4.0-Windows-x64-Setup.exe`) for Windows 10 & 11 (x64) with bundled FFmpeg and automated browser launch.
- **Standalone macOS Apple Silicon Installer:** Packaged DMG distribution (`HotChords-v0.4.0-macOS-AppleSilicon.dmg`) for Apple Silicon Macs.

### Changed
- Refactored `SongAudioController` to preserve Object URL lifetimes and enforce explicit volume/unmuted states during track switching.
- Standardized single `PlaybackClock` authority across UI ribbon, dynamic reel, keyboard canvas, and dual audio renderers.
- Updated project API contracts (`SONG_RESULT_CONTRACT.md`) and package metadata to version `0.4.0`.

### Fixed
- Fixed audio source switching where original track playback had no audible volume due to premature Object URL revocation.
- Fixed `run_pipeline()` callback compatibility and progress reporting under FastAPI background tasks.
- Resolved race conditions during rapid seek jumps and loop wrap-around boundaries.

---

## [v0.3.0] — Core Workspace Scale, Spatial Balance & Processing UX (2026-08-28)

> [!IMPORTANT]
> **Product Development Status**:
> - **Version**: 0.3.0 (Development Milestone)
> - **UI/UX Status**: In Progress / Active Development
> - **Application Development**: Not Complete
> - **Milestone Focus**: Large immersive music-learning scale, stationary spatial column labels, persistent application shell, honest pipeline milestone tracking, and seamless entry transitions.
> - **Accuracy & Reality**: Chord detection accuracy is under active validation using real-world audio; v0.3 is an open development foundation, not a finished commercial product.

### Product Direction & Philosophy
Earlier iterations accumulated fragmented layouts, multiple competing screens, and excessive empty dead space. Version 0.3 enforces a single, unified application shell with large, immersive learning elements designed to function like an actual music stand instrument.

### Highlights in v0.3.0

- **Unified Application Shell & Persistent Identity**:
  - Maintained consistent top header (`HotChords VER 0.3`) across all lifecycle states (Upload $\to$ Processing $\to$ Loaded Workspace).
  - Eliminated disconnected, floating modals and screen flashing.
- **Redesigned Initial Upload Experience**:
  - Clean, structured entry screen with clear product hierarchy (*"Turn any song into chords you can play."*).
  - Interactive upload card with format badges (`MP3`, `WAV`, `M4A`, `FLAC`), drag-and-drop pulsing feedback (`.drag-over`), and keyboard accessibility (`Enter`/`Space`).
- **Honest & Transparent Processing State**:
  - Live song filename visibility throughout analysis (e.g. `Song1-HotFix-TuMera.mp3`).
  - Animated audio waveform pulse.
  - Live 5-stage pipeline checklist reflecting actual backend DSP progress:
    1. *Preparing audio & separation*
    2. *Analyzing musical chroma & tempo*
    3. *Detecting chords & musical key*
    4. *Building piano voicings & fingering*
    5. *Preparing interactive music stand*
  - Replaced decorative spinners with measurable backend `pct` indicators.
  - Graceful error state handling with clear messages, *Retry Analysis*, and *Choose Another File* actions without breaking the application shell.
- **Large Immersive Workspace Scale & Spatial Balance**:
  - **Stationary Column Anchors**: Fixed spatial labels row (`PREVIOUS`, `CURRENT CHORD`, `NEXT`) positioned permanently above the chord track. Labels remain strictly fixed in space while the chord objects physically animate beneath them.
  - **Massive Hero Chord**: Current Chord typography scaled to `clamp(3.8rem, 8.5vw, 6.2rem)` with bold weight, radiant blue glow, note spellings (`C# · E · G#`), and a linear duration progress bar.
  - **Enlarged Hand Illustrations**: Left and Right hand SVG diagrams enlarged to `185 × 205px` on desktop with clear finger number badges and note chips.
  - **Substantial Docked Piano**: Keyboard height expanded to `clamp(160px, 24vh, 260px)`, filling the bottom half as a dedicated docked instrument.
  - **Responsive Intrinsic Layout**: Sizing reflows across viewports (1440x900 down to 390x844) with zero horizontal overflow and balanced vertical distribution.
- **Engineering & Synchronization**:
  - Single authoritative `PlaybackClock` orchestrating audio playback, synthesized tones, chord carousel animations, hand diagrams, and piano keys.
  - Deterministic seeking (forward/backward/rapid) with instantaneous card snap and zero transient DOM leaks.
  - Automated visual QA validation suite testing multi-viewport rendering and real-song playback transitions.

### Known Limitations
- UI/UX layout and proportions remain under active refinement.
- Chord detection uses Chroma CQT template matching and Viterbi HMM decoding; complex polyphonic or heavily distorted mixes remain an active research focus.
- Stem separation latency depends on local hardware capabilities.

---

## [v0.2.0] — Core Architecture Stabilization Milestone (2026-08-28)

- Single permanent loaded-song workspace eliminating legacy fragmented screens.
- Deterministic 3-chord timeline with 4-lane WAAPI physical sliding carousel.
- Permanent Left and Right hand diagrams synchronized with 61-key piano.
- Single authoritative `PlaybackClock` timing architecture.
- Simplified and Original mode dataset switching.
- Complete removal of the legacy lyrics feature to focus on core piano learning.

---

## [v0.1.0] — Initial Public Release

- Local audio upload and Demucs stem separation.
- Beat-synchronized chroma extraction and Viterbi HMM chord smoothing.
- SVG 61-key piano keyboard with initial fingering engine.
