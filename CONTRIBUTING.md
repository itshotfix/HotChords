# Contributing to HotChords

Thank you for your interest in contributing to HotChords! 

HotChords is an open-source, local-first music workstation designed to bridge cutting-edge Music Information Retrieval (MIR) with practical, accessible piano education. We welcome contributions from developers, MIR researchers, DSP engineers, pianists, and music theory enthusiasts.

---

## 1. Core Principles

1. **Local & Privacy-Preserving:** HotChords must run 100% locally on standard user machines without sending audio to remote APIs or collecting tracking telemetry.
2. **Harmonic Transparency:** We never claim synthetic or false detection accuracy. Confidence values must be mathematically formulated, explainable, and transparent to the user.
3. **Ergonomic Playability:** Voicings and beginner chord simplifications must follow sound musical voice leading and biomechanically plausible hand fingerings.
4. **Architectural Integrity:** All UI and audio renderers must synchronize strictly to the master `PlaybackClock` to avoid timing drift or clock fighting.

---

## 2. Development Setup

### Prerequisites
- **Python 3.10+** (Python 3.10 through 3.14)
- **Node.js 18+** (for running frontend and lifecycle tests)
- **FFmpeg** (installed locally or via your OS package manager)

### Local Setup
```bash
# 1. Clone your fork
git clone https://github.com/<your-username>/HotChords.git
cd HotChords

# 2. Setup Python virtual environment
python3 -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Setup Frontend test dependencies
npm install

# 4. Launch HotChords
python hotchords.py
```

---

## 3. Repository Structure

```
HotChords/
├── backend/
│   ├── analysis/       # Audio QC, harmonic routing, MIR chord engines, loop detection
│   ├── theory/         # Normalization, beginner simplification, piano voicing & fingering
│   ├── models/         # Pydantic data contracts and timeline response schemas
│   ├── api/            # FastAPI endpoints and background analysis worker
│   └── benchmarks/     # Audio profiling and evaluation benchmarks
├── frontend/
│   ├── css/piano.css   # Single workspace design system and layout rules
│   ├── index.html      # Permanent single-workspace application shell
│   └── js/
│       ├── audio/      # PlaybackClock, SongAudioController, PianoPlayback, Practice mic
│       ├── engine/     # Real-time fingering, transitions, and theory formatters
│       └── ui/         # DynamicChordReel, PianoKeyboard, WorkspaceHandController
├── tests/              # 195 Python unit/integration tests + 55 Node client test suites
└── docs/               # Architecture and technical specifications
```

---

## 4. Coding & Architecture Guidelines

### Python (Backend)
- Adhere to PEP 8 standards and type hinting where practical.
- Keep `backend/api/router.py` thin; delegate all business and DSP logic to `backend/analysis/` and `backend/theory/`.
- Ensure all new analysis outputs conform strictly to `SONG_RESULT_CONTRACT.md`.

### JavaScript & CSS (Frontend)
- Use **pure Vanilla ES6+** without adding heavy frontend frameworks.
- All playback actions, seek events, and timeline cursors must bind to `PlaybackClock`. Do not create competing timers or uncoordinated `setInterval` loops.
- Do not create multiple active `AudioContext` instances; reuse the shared service from `PianoPlaybackService`.
- Keep CSS modular and organized in `frontend/css/piano.css`. Avoid ad-hoc inline styles.

---

## 5. Testing Expectations

All pull requests must pass the complete test suite before merging:

```bash
# 1. Run all Python backend tests (195 tests)
pytest tests/

# 2. Run all frontend and UI/UX invariant tests (37 tests)
npm test

# 3. Run master PlaybackClock & dual-renderer lifecycle tests (6 scenarios)
node tests/test_playback_lifecycle.js

# 4. Run client pitch detection and feedback bridge tests (12 tests)
node tests/test_phase11_client_pitch_and_feedback.js
node tests/test_phase12_client_metrics.js
```

### Adding New Tests
- When adding a backend feature, add corresponding pytest unit tests in `tests/test_<feature>.py`.
- When modifying playback or UI components, add verification assertions to `tests/test_playback_lifecycle.js` or `tests/test_app_ui.js`.

---

## 6. Pull Request Process

1. **Open an Issue / Discussion:** For major architectural changes or new MIR algorithms, open a GitHub Issue first to align with the core maintainers.
2. **Create a Feature Branch:** `git checkout -b feature/your-feature-name`
3. **Commit Atomic Changes:** Write descriptive commit messages explaining *what* was changed and *why*.
4. **Verify Locally:** Ensure `pytest tests/` and `npm test` pass 100% green and no console errors occur.
5. **Submit PR:** Open your pull request against the `main` branch with a summary of changes and test evidence.
