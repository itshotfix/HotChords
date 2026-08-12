# HotChords: System Documentation & Architecture (v5.5-Workstation)

HotChords is a professional-grade, offline piano chord detection and educational workstation. It transforms raw audio into a playable "pedagogical blueprint," showing users not just what chords are playing, but exactly how to play them using standard piano technique.

## 1. Core Mission
To provide the most intuitive, zero-latency, and visually elegant offline chord learning experience, focusing on professional music theory and pedagogical clarity.

---

## 2. Technical Stack
- **Backend:** Python 3.9+
- **Signal Processing:** Librosa (Chroma CQT, Beat Tracking, Key Detection)
- **Frontend Architecture:** Modular SPA (Vanilla JS, CSS3, SVG)
- **Animation Engine:** GSAP 3 (GreenSock) for 60fps instructional motion.
- **Server:** Python `http.server.HTTPServer` with custom routing and static file support.

---

## 3. System Architecture

### A. Backend (The "Detection Engine")
Located in `hotchords.py`, the backend handles the heavy lifting:
- **Audio Pipeline:** Loads audio at 22kHz, performs Harmonic-Percussive Source Separation (HPSS) to isolate harmonic content.
- **Feature Extraction:** Generates 36-bin Chroma Constant-Q Transforms (CQT) for high-frequency resolution.
- **Classification:** Uses cosine similarity against a library of 61 chord templates (Major, Minor, 7ths, Suspended, etc.).
- **Music Theory Engine:** 
    - **Enharmonic Normalization:** Automatically converts complex theoretical names to musician-friendly versions (e.g., G#m -> Abm).
    - **Chord Simplification:** Maps complex extensions back to playable core voicings.
- **API Endpoints:**
    - `POST /analyze`: Multipart file upload.
    - `GET /progress`: JSON status of current background analysis.
    - `GET /result`: Final analysis payload including chords, timings, and metadata.

### B. Frontend (The "Workstation")
A modular architecture designed for high-performance rendering:
- **`pianoKeyboard.js`:** A custom-built 61-key (C2-C7) SVG rendering engine. It handles mathematical piano proportions, responsive scaling, and note labeling.
- **`pianoFingeringEngine.js`:** A deterministic local module that calculates standard RH/LH fingerings.
- **`handAnimator.js`:** A GSAP-driven engine that animates finger presses and key pulses synchronized with audio playback.
- **`musicTheoryFormatter.js`:** Ensures UI-wide consistency in chord naming.

---

## 4. Key Features

### I. Pedagogical Voicing System
Unlike standard visualizers that highlight every octave, HotChords implements **"One Voicing Per Hand"**:
- **Left Hand:** Fixed to Octave 2 for power/bass shell.
- **Right Hand:** Fixed to Octave 4 for harmonic clarity.
This creates a single, playable "blueprint" for the learner, reducing cognitive load.

### II. Instructional Hand Animation
- **Realistic Hand Models:** SVG-based hands with visible palms and articulate fingers.
- **Downward Press Motion:** Fingers perform an 8px downward "strike" animation on chord changes.
- **Glow & Pulse:** Matching piano keys pulse in brightness when struck.

### III. Professional Color System
A strict 5-color pedagogical system used across the entire app:
- **Finger 1 (Thumb):** Red (#FF4D4F)
- **Finger 2 (Index):** Yellow (#FAAD14)
- **Finger 3 (Middle):** Green (#52C41A)
- **Finger 4 (Ring):** Teal (#13C2C2)
- **Finger 5 (Pinky):** Blue (#1677FF)
Colors are synchronized between the **Hand Diagrams**, **Finger Numbers**, and **Piano Keys**.

### IV. Apple-Inspired UI (Midnight/Premium White)
- **Design Language:** Clean, minimal, and high-contrast, inspired by Apple.com.
- **Zero-Scroll Viewport:** The app is locked to `100vh`. The piano is docked to the bottom (30-35vh), while the "Chord Hero" and "Waveform" dynamically occupy the top sections.

---

## 5. File Structure
```text
/
├── hotchords.py              # Main entry point & Python Backend
├── frontend/
│   ├── index.html            # Main SPA entry
│   ├── css/
│   │   └── piano.css         # Apple Premium Styles & Layout
│   └── js/
│       ├── engine/
│       │   ├── musicTheoryFormatter.js
│       │   └── pianoFingeringEngine.js
│       ├── ui/
│       │   ├── pianoKeyboard.js
│       │   └── handDiagrams.js
│       └── animations/
│           └── handAnimator.js
```

---

## 6. Logic Flow (Upload to Playback)
1. **User Uploads File:** `POST /analyze` creates a background thread.
2. **Analysis:** Librosa processes audio -> Chords detected -> Result object cached.
3. **Result Loading:** Frontend polls `/result`, receives JSON, calls `initResults()`.
4. **Voicing Generation:** `pianoFingeringEngine` creates absolute MIDI mappings for LH/RH.
5. **UI Update:**
    - Piano renders the specific keys for the voicing.
    - Hand Diagrams update finger assignments.
    - GSAP triggers the press animations.
6. **Playback Sync:** The `requestAnimationFrame` loop in `index.html` checks current audio time and triggers `updateUI(t)` to swap chords instantly.

---
**End of Project Snapshot**
