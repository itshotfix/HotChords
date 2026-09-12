# HotChords — Phase 14.2 Development Report
**Product Feature Integration**

---

## 1. Files Changed

1. **`frontend/js/audio/songAudioController.js`**
   - Added `this.enabled = false` flag and `setEnabled(enabled)` method.
   - Updated `_onTick()` to strictly respect `this.enabled` (pausing the underlying audio element if ticks occur while disabled).
   - Ensured that `play()`, `seek()`, and loop operations do not produce audio or desynchronize when original track mode is disabled.

2. **`frontend/js/audio/unifiedPianoPlaybackController.js`**
   - Added `this.enabled = true` flag and `setEnabled(enabled)` method.
   - Guarded chord triggering in `_onTick()` behind `if (!this.enabled) return;` to prevent synthesizer voices from playing when in Original Track mode.

3. **`frontend/css/piano.css`**
   - Added `.ws-audio-selector` and `.audio-src-btn` styles for the Apple-style segmented playback source switcher (`[ Piano Audio ]` / `[ Original Track ]`).
   - Added `.ctrl-btn.btn-mic-active` and `.ctrl-btn.btn-loop-active` states for active toolbar toggles.
   - Added `.ws-feedback-chip` and status variations (`.feedback-listening`, `.feedback-match`, `.feedback-partial`, `.feedback-wrong`, `.feedback-noinput`) for real-time acoustic feedback overlay inside the Hero Chord display.

4. **`frontend/index.html`**
   - Imported client practice modules (`realtimePitchDetector.js`, `realtimeInputService.js`, `inputCalibrationService.js`, `practiceFeedbackBridge.js`, `practiceMetricsTracker.js`).
   - Added header metadata indicators:
     - `Detected From`: `#val-source` (displaying authoritative backend instrument attribution).
     - `Chord Confidence`: `#val-confidence` (displaying authoritative overall confidence percentage).
   - Added playback mode selector: `#audio-btn-piano` and `#audio-btn-original` invoking `setAudioSource(src)`.
   - Added 4-Chord Loop toggle button: `#btn-4chord-loop` invoking `handleToggle4ChordLoop()`.
   - Added Real-time Mic Practice toggle button: `#btn-mic-practice` invoking `handleToggleMicPractice()`.
   - Added Hero Chord Feedback Chip: `#ws-feedback-chip` for real-time pitch feedback status.
   - Integrated logic in `initResults()` to extract and bind `source_selection` / `reliability.overall`, configure four-chord loop state, and set initial playback mode.
   - Implemented resource cleanup in `resetApp()` to stop microphone media stream tracks, detach feedback bridge, and reset mode selectors.

---

## 2. Features Connected

- **Harmonic Source / Instrument Attribution**: Authoritative instrument selection (Piano, Guitar, Vocals, Mixed) from `source_selection` rendered directly in the workspace header.
- **Chord Confidence %**: Overall reliability percentage from `reliability.overall` rendered as "Chord Confidence XX%".
- **Dual Playback Mode Switcher**: User-facing toggle between synthesized Piano Audio and Original Track Audio, synchronized seamlessly against `PlaybackClock`.
- **Four-Chord Loop Integration**: Dedicated loop toggle button automatically enabled when `four_chord_loop.available === true`, setting loop boundaries across the detected progression.
- **Microphone Pitch Practice Mode**: Toggle button enabling real-time microphone capture, auto-calibration, and note-matching feedback against the currently expected chord.
- **Real-Time Visual Feedback**: Chip inside the Hero Chord card indicating live practice state (`Listening...`, `Match!`, `Partial Match`, `Wrong Notes`, `No Input Detected`).

---

## 3. Backend / API Changes

- **API Contract Verification**: The existing Pydantic models in `backend/models/timeline.py` (`SongTimeline.to_analysis_dict()`) already serialize all necessary metadata:
  - `source_selection` (aliased as `selectedSource`, `selectedInstrument`, `selectionConfidence`, `reason`, `instruments`).
  - `reliability` (aliased as `overall`, `harmonicConsistency`, `rhythmRegularity`, `transitionPlausibility`, `structuralCoherence`).
  - `four_chord_loop` (aliased as `available`, `chords`, `startTime`, `endTime`, `confidence`, `reason`).
- **Frontend Parser Compatibility**: Frontend parsing in `index.html` was made fully agnostic to both camelCase and snake_case representations to guarantee seamless data binding without requiring backend schema alterations.

---

## 4. Frontend Changes

- **Workspace Header**:
  - Attached `#val-source` to show authoritative detected instrument (e.g., `Piano`, `Guitar`, `Vocals`, `Mixed Audio`).
  - Attached `#val-confidence` to show `Chord Confidence` as a clean percentage.
- **Transport Bar**:
  - Embedded segmented audio switch: `[ Piano Audio ]` / `[ Original Track ]`.
  - Added `#btn-4chord-loop` (`4-Chord Loop`) button with active indicator state.
  - Added `#btn-mic-practice` (`Mic Practice`) button with active indicator state.
- **Music Stand / Hero Chord Card**:
  - Embedded `#ws-feedback-chip` displaying real-time match evaluation and detected notes.

---

## 5. Playback Architecture & Audio Exclusivity

- **Clock Authority**: `PlaybackClock` remains the single, authoritative timekeeper. Neither controller runs an independent timer.
- **Mutual Audio Exclusivity**:
  - `UnifiedPianoPlaybackController` and `SongAudioController` implement `.setEnabled(boolean)`.
  - In `Piano` mode: `pianoController.setEnabled(true)` and `songAudioController.setEnabled(false)`. The song audio is muted/paused; piano voicings trigger on clock ticks.
  - In `Original` mode: `pianoController.setEnabled(false)` and `songAudioController.setEnabled(true)`. The piano synthesizer voice triggers are suppressed; the original audio element plays synchronized with the clock.
  - Switching mode on the fly preserves `PlaybackClock.currentTime` and play/pause state without duplicate audio overlap.

---

## 6. Source Attribution Integration

- Extracted from `window.currentTimelineData.source_selection` or `sourceSelection`.
- Formats instrument name cleanly (capitalized) with tooltip showing selection confidence and reason if available.
- Honors empty/unsupported states honestly without fabricating instrument classifications.

---

## 7. Confidence Integration

- Extracted from `window.currentTimelineData.reliability.overall` (or `reliability_score`).
- Scaled to 0–100% and formatted as `XX%`.
- Labeled strictly as **Chord Confidence** (avoiding unverified "Accuracy %" claims).

---

## 8. Four-Chord Loop Integration

- Reads `window.currentTimelineData.four_chord_loop`.
- If `available: true`, the 4-Chord Loop button is enabled with chord names displayed in the tooltip.
- Clicking toggles loop boundaries:
  - ON: sets `PlaybackClock.setLoop(startTime, endTime)` and seeks to `startTime`.
  - OFF: clears loop boundaries `PlaybackClock.clearLoop()`.
- If `available: false`, button is cleanly disabled with empty state text.

---

## 9. Practice Integration & Microphone Lifecycle

- Clicking `Mic Practice` initializes:
  1. `RealtimeInputService.start()` requesting `navigator.mediaDevices.getUserMedia({ audio: true })`.
  2. `InputCalibrationService.calibrate()` measuring ambient noise floor.
  3. `PracticeFeedbackBridge.attach()` hooking into `PlaybackClock.subscribe()`.
- Live feedback evaluates incoming detected notes vs. the expected chord from the active timeline step.
- Hardware cleanup:
  - Toggling Mic Practice OFF or clicking `Upload New Audio` / `resetApp()` invokes `realtimeInputService.stop()`, which explicitly calls `MediaStreamTrack.stop()` on all audio tracks to immediately release hardware and guarantee user privacy.

---

## 10. Unresolved Implementation Issues / Boundaries

- **Real Piano Acoustic Validation Dataset**: As established in Phase 14, real acoustic piano validation requires ground-truth audio recordings (currently mocked / simulated in unit tests). The detector is integrated and functional for client microphone input.
- **Mobile Web Audio Policy**: Autoplay policies on iOS Safari require user interaction before `AudioContext` resumption; standard UI click handlers currently handle resumption.

---

## 11. Targeted Checks Performed

- **Node.js Playback & Client Suite**: `npm test` -> **21/21 PASSED (100%)**
  - `test_phase4_playback_sync.js`
  - `test_phase11_client_pitch_and_feedback.js`
  - `test_phase12_client_metrics.js`
- **Playback Lifecycle Test**: `node tests/test_playback_lifecycle.js` -> **4/4 Scenarios PASSED (100%)**
  - Scenario 1: Initial load default state.
  - Scenario 2: Switch to Original Track mode.
  - Scenario 3: Switch back to Piano mode while maintaining clock.
  - Scenario 4: Pause/Seek during playback.
- **Python Backend Unit Tests**: `pytest` -> **195/195 PASSED (100%)**
  - `test_chord_engines.py`
  - `test_four_chord_loop.py`
  - `test_evidence_and_reliability.py`
  - `test_phase10_practice_session.py`
  - `test_phase11_practice_feedback.py`
  - `test_phase12_practice_metrics.py`
  - `test_phase14_real_piano_evaluation.py`
  - Full pipeline regression tests.
- **Live Local Server Verification**: Verified live HTTP endpoints and markup on `http://127.0.0.1:5501/`.

---

> [!NOTE]
> **Phase 14.2 Development is complete.** Final testing and full test campaign are intentionally withheld for the dedicated testing prompt.
