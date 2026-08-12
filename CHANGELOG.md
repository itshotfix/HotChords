# Changelog

All notable changes to HotChords are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [v0.1.0] — Initial Public Release

*This is the first official public open-source release of HotChords on GitHub.* 
*(Note: Internal development history progressed up to v5.5 prior to this public release).*

### Current State

HotChords is a functional, locally-running piano chord detection workstation. The application can:

- Accept audio file uploads (MP3, WAV, FLAC, M4A, OGG, AAC)
- Detect key, scale, BPM, time signature, and song structure
- Identify chords using a 61-template overtone-aware cosine similarity approach smoothed by a music-theoretically informed Viterbi HMM
- Display chords beat-synced with audio playback on an interactive SVG waveform
- Render a 61-key SVG piano with correct LH/RH voicings and finger assignments
- Animate hand diagrams with GSAP on chord changes
- Optionally perform AI source separation via Demucs before analysis

### Architecture

- **Backend**: Python + FastAPI + Uvicorn
- **Frontend**: Vanilla JavaScript SPA + GSAP 3 animations + Web Audio API
- **No build step required**: frontend is served as static files

### Features Introduced Prior to Public Release (Internal v1.0 - v5.5)

- **DSP & Analysis**:
  - Harmonic separation (HPSS) to filter percussive transients.
  - Overtone-aware templates modeling 2nd, 3rd, and 5th harmonics.
  - Viterbi HMM decoder with diatonic bias and 4th/5th root motion bonus.
  - Structure detection using O(n) chroma novelty curve.
  - Krumhansl-Schmuckler key and scale detection.
- **Music Theory Engine**:
  - Enharmonic normalization (e.g., G# -> Ab).
  - Beginner chart generation (collapsing complex chords to basic triads).
  - Roman numeral analysis.
- **Piano & UI**:
  - SVG 61-key mathematically proportioned piano keyboard.
  - "One Voicing Per Hand" engine locking LH to Octave 2 and RH to Octave 4.
  - Apple-inspired design system with GSAP animated hand diagrams.
  - Real-time Web Audio API pitch-shifting (detune) and synchronized playback.
