# Changelog

All notable changes to HotChords are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [v0.2.0] — Core Architecture Stabilization Milestone (2026-08-28)

> [!IMPORTANT]
> **Product Development Status**:
> - **Version**: 0.2.0 (Development Milestone)
> - **UI/UX Status**: In Progress / Active Development
> - **Application Development**: Not Complete
> 
> *Version 0.2 is an intentional stabilization milestone. During earlier development, multiple features and UI experiences were built simultaneously. This created unnecessary complexity, duplicated UI patterns, inconsistent layouts, synchronization challenges, and made the core experience harder to validate. For this milestone, we intentionally stripped away secondary and redundant functionality and concentrated the application around the core HotChords interactive music stand experience.*

### Core Architecture Highlights

- **Single Permanent Loaded-Song Workspace**:
  - Eliminated the concept of competing multi-tab layouts (legacy Simplified Chords, Practice, and Play Original screens).
  - Consolidated into one permanent 4-tier music stand hierarchy:
    1. Header & Song Metadata (Key, BPM, Time Signature, Track Title)
    2. Mode Selector (`Simplified` / `Original`) + Quick Controls
    3. Central Chord Learning Area (Left Hand | 3-Chord Reel | Right Hand)
    4. Persistent 61-Key SVG Piano Dock
    5. Bottom Transport Bar (Waveform Seek Canvas + Audio Controls)
- **Deterministic 3-Chord Timeline**:
  - Strict 3-position physical reel: **Previous < Current Hero > Next**.
  - Current Chord is the dominant visual hero (`scale(1.08)` + subtle glow + chord notes breakdown `C · E · G`), with Previous and Next muted and secondary (`scale(0.55)`).
  - Coordinated 4-lane WAAPI physical sliding animation on sequential (+1) playback boundary crossings.
  - Zero text-swapping illusion; clock ticks only update the progress bar width without layout or DOM reflows.
  - Instantaneous seek reset: seeking (forward/backward/rapid) immediately cancels in-flight animations and snaps resting cards without animation queue lag.
- **Permanent Left & Right Hand Diagrams in All Modes**:
  - Left Hand (Bass root + 5th power foundation) and Right Hand (Harmonic triad / 7th voicings) are active in both Simplified and Original modes.
  - Reactive finger press micro-animations (`translateY(5px)`, active color fill, and drop-shadow glow) on chord changes.
  - Finger number badges (1=Thumb..5=Pinky) and note chip tags match `PianoFingeringEngine`.
- **Persistent Piano Keyboard**:
  - Shared 61-key SVG keyboard maintained across all playback states.
  - Strict 1-to-1 color-coded key illumination synchronized with Left/Right hand finger pads.
- **Single Authoritative Timing System**:
  - `SongTimeline` $\to$ `PlaybackClock` $\to$ `CurrentChordEngine` $\to$ `PianoFingeringEngine` $\to$ Hands / Piano / UI.
  - Audio playback, synth piano, hand diagrams, and chord reel stay strictly in sync during play, pause, seek, speed changes (0.50x, 0.75x, 1.00x), and sustain pedal toggling.
- **Simplified / Original Mode Toggle**:
  - Switching mode dynamically swaps the underlying dataset (`SongTimeline.beginnerChords` vs `SongTimeline.originalChords`) with zero layout reorganization or playback disruption.

### Intentionally Removed / Deferred Features
- **Lyrics & Transcription Subsystem**: Removed Whisper transcription, vad, transliteration, and lyrics teleprompter components to focus exclusively on chord learning and piano guidance.
- **Legacy Fragmented UIs**: Removed duplicate chord ribbons, vertical chord lists, and per-mode duplicate containers.

---

## [v0.1.0] — Initial Public Release

*First official public open-source release of HotChords on GitHub.*
- Local audio upload and Demucs stem separation.
- Beat-synchronized chroma extraction and Viterbi HMM chord smoothing.
- SVG 61-key piano keyboard with initial fingering engine.
