# HotChords Release Version Audit & Determination

## 1. Current Repository Version State

### 1.1 Git History & Tags
- **`v0.1.0`** (Commit `d8e97d5`): Initial HotChords core application release.
- **`v0.2.0`** (Commit `176e76f`): Core architecture stabilization & cross-platform setup.
- **`v0.3.0`** (Commit `fc3fcaa` / `ca56b62`): Single unified workstation shell, spatial balance, and responsive layout.

### 1.2 Active Version References (Prior to this Release)
- `package.json`: `"version": "0.3.0"`
- `backend/models/__init__.py`: `APP_VERSION = "0.3.0"`
- `backend/api/router.py`: `version=APP_VERSION`
- `frontend/index.html`: `VER 0.3` (Header and Workstation branding)
- `scripts/build_macos_dmg.sh`: `0.3.0`
- `SONG_RESULT_CONTRACT.md`: `0.3.0`

---

## 2. Version Decision: `v0.4.0` (`0.4.0`)

### 2.1 Rationale
1. **Semantic Versioning Standard (`MAJOR.MINOR.PATCH`):**
   - The project is in active pre-1.0 development where minor version increments (`0.x.0`) represent significant architectural and feature expansions while maintaining backward-compatible API patterns.
   - The jump to `1.0.0` is reserved for post-public-beta stabilization following real-world physical acoustic piano benchmark validation.
2. **Substantial Feature & Architectural Additions in this Milestone:**
   - **Multi-Engine Harmonic Evidence Router:** Ensemble consensus between `lv-chordia` and CQT chroma correlation with dynamic spectral flatness / SNR profiling.
   - **Source-Aware Separation & Stem Routing:** Intelligently isolates harmonic carriers (piano/guitar/other) and excludes percussive/vocal interference.
   - **Harmonic Attribution & Confidence Transparency:** Displays detected source, source confidence percentage, mathematical consensus reason, and chord reliability breakdown in UI.
   - **Structural Segmentation & 4-Chord Loop:** Automatic verse/chorus recurrence segmentation and looping practice engine.
   - **Beginner-Friendly Chord Simplification & Voicing:** Dynamic root-position/inversion adaptation, Left/Right hand fingerings, and keyboard highlights.
   - **Unified Dual-Source Playback Architecture:** Synchronized polyphonic piano synthesizer and original track audio playback governed by the authoritative `PlaybackClock`.
   - **Realtime Microphone Pitch Detection & Practice Feedback:** Client-side autocorrelation / YIN note detection, dynamic octave tolerance, and practice metrics tracking.

### 2.2 Version Progression
`v0.1.0` → `v0.2.0` → `v0.3.0` → **`v0.4.0`**

---

## 3. Active Files Requiring Version Synchronization to `0.4.0`

| File Path | Component | Current String | Target String |
|---|---|---|---|
| [`package.json`](package.json) | NPM Package Metadata | `"version": "0.3.0"` | `"version": "0.4.0"` |
| [`backend/models/__init__.py`](backend/models/__init__.py) | Backend Package Constant | `APP_VERSION = "0.3.0"` | `APP_VERSION = "0.4.0"` |
| [`frontend/index.html`](frontend/index.html) | UI Header & Shell Brand | `VER 0.3` | `VER 0.4` |
| [`scripts/build_macos_dmg.sh`](scripts/build_macos_dmg.sh) | Build Script Metadata | `0.3.0` | `0.4.0` |
| [`SONG_RESULT_CONTRACT.md`](SONG_RESULT_CONTRACT.md) | API Data Contract Spec | `0.3.0` | `0.4.0` |
| [`tests/test_phase_7c_ui_ux.js`](tests/test_phase_7c_ui_ux.js) | Test Suite Version Assertion | `includes('v0.3')` | `includes('v0.4') \|\| includes('0.4.0')` |
| [`README.md`](README.md) | Documentation & Badges | `v0.3.0` | `v0.4.0` |
| [`CHANGELOG.md`](CHANGELOG.md) | Release Log | `[v0.3.0]` | `[v0.4.0]` |

*(Note: Historical phase reports such as `PHASE14_2A_PLAYBACK_DEVELOPMENT_REPORT.md` will retain their original development phase titles to preserve immutable historical records).*
