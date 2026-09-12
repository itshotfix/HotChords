# HotChords — Phase 14.2A Playback Architecture Repair
**Development Report**

---

## 1. Root Cause Analysis

### A. Root Cause of Original Playback Failure
- **Clock-Fighting & Continuous Decoder Seeking**: In `SongAudioController.bindClock()`, the central `PlaybackClock` broadcast snapshots to subscribers on every `requestAnimationFrame` (60–120 fps). The controller executed a drift check (`Math.abs(audioEl.currentTime - snap.currentTime) > 0.15`) on every frame. Because HTML5 `<audio>` media elements update `currentTime` in discrete buffer increments (typically every 100–250ms), the computed drift routinely exceeded 150ms. As a result, `audioEl.currentTime = snap.currentTime` was written dozens of times per second, causing continuous buffer flushes, audio stuttering, and total silence.
- **Unhandled `play()` Promises**: `HTMLMediaElement.play()` returns a Promise. When called asynchronously or during rapid state/mode changes without waiting for resolution, browser autoplay policies or aborts (`AbortError`, `NotAllowedError`) caused silent failure without error recovery or UI synchronization.

### B. Root Cause of Restart Failure
- **Improper Transport Semantics**: `PlaybackClock.restart()` implemented `this.stop(); this.play();`, which unconditionally transitioned the state to `PLAYING` even when paused or stopped. Furthermore, if a loop was active, `stop()` reset the position to `_loopStart` rather than the canonical 0.0s timeline origin.
- **Missing Controller and UI Resets**: Visual components (3-chord reel cards, hero chord, hand voicings) were not explicitly reset to timestamp 0.0 upon restart.

### C. Root Cause of Loop Failure
- **Missing Track-Loop Control**: The UI only contained the conditional `4-Chord Loop` button (hidden when `four_chord_loop.available === false`), with no global full-track loop toggle.
- **Loop Boundary Transition Stutter**: When `PlaybackClock` reached `loopEnd` and jumped back to `loopStart`, rapid per-frame seek logic conflicted with media playback.

---

## 2. Playback State & Clock Architecture

HotChords maintains a single authoritative temporal authority:

```
                    PlaybackClock (Canonical Timeline)
                                   |
                +------------------+------------------+
                |                                     |
    UnifiedPianoPlaybackController           SongAudioController
        (Tone.js Synthesizer)               (HTMLAudioElement)
                |                                     |
           Piano Audio                            Song Audio
```

### Canonical State Ownership
1. **`PlaybackClock`**: Sole authority over musical timeline position ($T$), duration, rate multiplier, loop region ($[T_{start}, T_{end}]$), and playback state (`PLAYING`, `PAUSED`, `STOPPED`).
2. **`UnifiedPianoPlaybackController`**: Reacts to clock state and timeline chord events. When `enabled === false`, immediately silences all synth voices and suspends scheduling.
3. **`SongAudioController`**: Wraps the native `HTMLAudioElement`. Reconciles native playback with `PlaybackClock` smoothly without per-frame clock fighting. When `enabled === false`, pauses the media element.

---

## 3. Original Audio Reconciliation & Transport Strategy

To eliminate clock fighting and decoder stutter:
1. **Play Start Alignment**: On transitioning to `PLAYING`, if difference $> 80\text{ ms}$, `audioEl.currentTime` is set once, and `audioEl.play()` is awaited with full exception handling.
2. **Smooth Drift Reconciliation**: During continuous playback, `audioEl.currentTime` is **not** overwritten on every frame. Drift is evaluated with a conservative threshold ($> 350\text{ ms}$) and rate-limited to at most once every $500\text{ ms}$. This allows the native browser media engine to decode and render audio smoothly.
3. **Loop Transitions**: When `PlaybackClock` reaches loop boundaries, it seeks to `loopStart`, and the controller smoothly synchronizes the audio element.
4. **End-of-Track**: The native `ended` event stops the clock if looping is inactive, or triggers a loop jump if looping is active.

---

## 4. Mutual Exclusivity Strategy

At no time do both renderers produce audible audio:
- **`PIANO` Mode**: `UnifiedPianoPlaybackController.setEnabled(true)` and `SongAudioController.setEnabled(false)`. Piano chords trigger via Tone.js; original audio is muted and paused.
- **`ORIGINAL` Mode**: `UnifiedPianoPlaybackController.setEnabled(false)` and `SongAudioController.setEnabled(true)`. Piano notes are silenced; uploaded audio plays synchronized to `PlaybackClock`.
- Mode transitions preserve `PlaybackClock.currentTime` and playback status (`PLAYING` / `PAUSED`).

---

## 5. UI Control Layout Reorganization

Primary playback controls have been moved **ABOVE** the timeline into a dedicated controls bar inside the playback section:

```
┌────────────────────────────────────────────────────────────────────────┐
│  [↺ Restart]  [▶ Play]  [⇄ Loop]  [4-Chord Loop]   [ Piano | Original ]│
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  ───────────────────────── Waveform Timeline ───────────────────────── │
│                                                                        │
│  0:00                          [ Seekbar ]                        3:42 │
└────────────────────────────────────────────────────────────────────────┘
```

- **Top Transport Bar (`.ws-playback-controls-bar`)**:
  - `↺ Restart` (`#btn-transport-restart`): Canonical reset to 0.0s.
  - `▶ / ❚❚ Play/Pause` (`#main-play-btn`): Central toggle button reflecting real clock state.
  - `⇄ Loop` (`#btn-track-loop`): Full-track loop toggle.
  - `4-Chord Loop` (`#btn-4chord-loop`): Section-specific loop (when available).
  - Segmented Source Selector (`#audio-btn-piano` / `#audio-btn-original`).
- **Waveform (`.ws-waveform`)**: Interactive click-to-seek waveform canvas with live playhead.
- **Time & Seek Row (`.ws-transport-row`)**: Current time, seek slider, and total duration.

---

## 6. Files Changed

1. **`frontend/js/audio/playbackClock.js`**
   - Canonical `restart()` implementation (resets to 0.0s, retains play/pause state).
   - Loop wrap-around support in `getCurrentTime()` and `seek()`.
2. **`frontend/js/audio/songAudioController.js`**
   - Implemented Promise-aware `play()` with error handling.
   - Replaced aggressive per-frame seeking with smooth drift reconciliation.
   - Added `getDiagnostics()` for development diagnostics.
   - Handled `ended`, `error`, `canplay`, and `loadedmetadata` events cleanly.
3. **`frontend/css/piano.css`**
   - Added styles for `.ws-playback-controls-bar`, `.ws-playback-left-group`, `.ws-playback-right-group`.
   - Polished transport button states and pill selectors.
4. **`frontend/index.html`**
   - Reordered workspace footer DOM to place controls above timeline.
   - Added `#btn-transport-restart` and `#btn-track-loop`.
   - Wired canonical handlers: `handleTogglePlay()`, `handleRestart()`, `handleStop()`, `handleToggleTrackLoop()`, `handleToggle4ChordLoop()`, `setAudioSource()`.
   - Updated `updateClockUI()` to sync play/pause and loop UI states.
5. **`tests/test_playback_lifecycle.js`**
   - Expanded regression suite covering 6 core scenarios (Lifecycle, Pause, Restart, Mutual Exclusivity, Loop wrap-around, Diagnostics & error recovery).

---

## 7. Targeted Verification Checks Performed

- **Node.js Playback Lifecycle Suite**: `node tests/test_playback_lifecycle.js` -> **6/6 Scenarios PASSED (100%)**
- **Full Node Client Suite**: `npm test` + client tests -> **49/49 Tests PASSED (100%)**
- **Pytest Suite**: `pytest tests/test_playback_lifecycle.py tests/test_phase4_playback_sync.py tests/test_phase8_song_contract.py` -> **5/5 PASSED (100%)**

---

> [!NOTE]
> **Phase 14.2A Development is complete.** Final browser testing and the full test campaign are intentionally withheld for the dedicated testing prompt.
