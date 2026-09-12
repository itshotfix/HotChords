# HotChords v0.3 — UI/UX & Animation Technical Bug Specification & Architecture Map

## Document Metadata
- **Status:** Phase 1 Analysis & Engineering Foundation Complete (Implementation deferred to Phase 2)
- **Scope:** HotChords Single-Workspace Desktop Application
- **Authoritative Clock:** `PlaybackClock` (`frontend/js/audio/playbackClock.js`)

---

## 1. System Architecture & Source of Truth Identification

Before planning any bug fixes, the authoritative sources of truth across the HotChords engine have been analyzed and verified:

| Domain / State | Authoritative Source of Truth | Primary Consuming Components | Invariant / Boundary Conditions |
| :--- | :--- | :--- | :--- |
| **Playback Clock & Time** | `PlaybackClock` (`frontend/js/audio/playbackClock.js`) | `SongAudioController`, `UnifiedPianoPlaybackController`, `WorkspaceChordTimeline`, `CurrentChordEngine` | Monotonic, rate-scaled seconds. Zero clock drift. Never driven or blocked by UI rendering. |
| **Current Chord** | `CurrentChordEngine.getCurrentChord(t)` | `WorkspaceChordTimeline`, `WorkspaceHandController`, `PianoKeyboard` | Binary search interval $[t_{\text{start}}, t_{\text{end}})$ over active mode dataset (`beginnerChords` vs `originalChords`). |
| **Previous & Next Chords** | `CurrentChordEngine.getPreviousChord(t)` & `getNextChord(t)` | `WorkspaceChordTimeline` | Immediate adjacent chord events relative to current index in timeline. |
| **Chord Timing** | `SongTimeline` canonical model (`startTime`, `endTime`, `duration`) | `CurrentChordEngine`, `WorkspaceChordTimeline`, `SongAudioController` | Millisecond-accurate timestamp intervals in seconds. |
| **Finger Assignments** | `PianoFingeringEngine.getChordVoicing()` (`frontend/js/engine/pianoFingeringEngine.js`) | `WorkspaceHandController`, `PianoKeyboard` | Deterministic pedagogical rules (Left Hand: Octave 2 bass root+5th; Right Hand: Octave 4 triad/7th). Standard 5-color palette (1=Thumb..5=Pinky). |
| **Piano Key Highlighting** | `PianoKeyboard.voicing` & `applyVoicingDOM()` (`frontend/js/ui/pianoKeyboard.js`) | SVG DOM elements (`#key-N`, `#key-label-N`, `#finger-dot-N`, `#finger-text-N`) | Strictly matches active MIDI keys from `PianoFingeringEngine`. Synchronized key depression and high-contrast label color. |
| **Playback Position & Scrubber** | `PlaybackClock.getSnapshot().currentTime` | `#seek-bar`, `#cur-time`, `#dur-time`, `#playhead` | Normalized $t / \text{duration} \times 100\%$ on waveform and seek bar. |
| **Waveform Width** | `#wf-wrap` / `#wf-canvas` container dimensions inside `.ws-playback` | Waveform Canvas 2D Context | Must span the full intended workspace width and align with transport row. |
| **Hand Diagrams & Active Fingers** | `WorkspaceHandController.update()` (`frontend/js/ui/workspaceHandController.js`) | SVG markup `#ws-lh-svg`, `#ws-rh-svg`, `#ws-lh-chips`, `#ws-rh-chips` | Direct reflection of `voicing.leftHand` and `voicing.rightHand`. |

---

## 2. Comprehensive Technical Bug Specification

### BUG 1 — PLAYBACK / WAVEFORM WIDTH & TRANSPORT ALIGNMENT
- **Problem Statement:**
  The playback transport controls and the waveform container do not share a consistent, aligned effective width or balanced container constraints.
  Specifically, in `frontend/css/piano.css`, `.ws-playback` holds `.ws-waveform` and `.ws-transport-row`. However, elements like `#playhead`, `.play-btn`, `.time-disp`, and `.seek-bar` lack refined dedicated sizing/alignment tokens, causing misaligned transport items, uneven gutters relative to the header and piano, and inconsistent width allocation across different window sizes.
- **Root Cause:**
  - Missing unified flex layout rules and CSS variable constraints linking `.ws-waveform` and `.ws-transport-row`.
  - `#playhead` lacks proper absolute bounding inside `.ws-waveform` container.
  - `.seek-bar` range input lacks customized cross-browser styling (thumb, track height, focus outline) for macOS Safari and Windows Chrome/Edge.
- **Required Behavior:**
  - The waveform and the playback transport row must share an identical effective width, perfectly aligned with the margins of the docked piano and header.
  - The play/pause button, time indicators (`0:00 / 3:45`), and scrubber must form a cohesive, centered, and balanced horizontal unit.

---

### BUG 2 — PIANO CHORD & NOTE LABEL VISIBILITY
- **Problem Statement:**
  When piano keys are illuminated with active finger colors, note/chord labels (`#key-label-${n}`) can become unreadable, clash with finger number circles (`#finger-dot-${n}` / `#finger-text-${n}`), or disappear against low-contrast background fills (e.g. orange/yellow for Finger 2 `#FAAD14`).
- **Root Cause:**
  - `PianoKeyboard.js` sets `labelEl.style.fill = '#fff'` unconditionally on all highlighted keys, which has poor contrast on lighter finger colors (Finger 2 `#FAAD14`, Finger 3 `#52C41A`).
  - Vertical stacking order and coordinate placement: `key-label-${n}` (placed at `this.whiteKeyHeight - 14`) conflicts with `finger-dot-${n}` (placed at `this.whiteKeyHeight * 0.76`) when keys resize on different screen dimensions.
  - Black keys have two-line text spans (`C#` / `Db`) that overlap with finger dots on shorter viewports.
- **Required Behavior:**
  - Contrast-adaptive text color: ensure note labels and finger indicators maintain high WCAG contrast against every assigned finger color.
  - Coordinated vertical layout on white and black keys so the note name and finger badge remain distinct, legible, and unclipped at all keyboard scales.

---

### BUG 3 — HAND / FINGER PROPORTIONS & BADGE ALIGNMENT
- **Problem Statement:**
  Finger number badges (`#lh-finger-dot-*`, `#rh-finger-dot-*`) are visually oversized relative to the finger vector graphics, causing numbers and dots to protrude outside the finger outlines. Additionally, the entire hand illustrations are proportionally too small within the hand columns.
- **Root Cause:**
  - In `frontend/js/ui/handDiagrams.js`, finger paths have widths of 18px–22px in the SVG coordinate space (`viewBox="0 0 200 220"`), but the finger dots are defined with radius `r="14"` (diameter 28px) and `font-size="14"`. A 28px circle physically exceeds a 22px finger bounding path.
  - In `frontend/css/piano.css`, `.ws-hand-svg` is constrained to `clamp(120px, 15vw, 185px)`, resulting in excessive unused vertical dead space in `.ws-hand-col` while the hand graphic itself appears undersized.
- **Required Behavior:**
  - Proportionally recalibrate hand SVG geometry: increase finger outline widths and adjust finger dot radii (`r="8"` to `10px`) with proportional typography (`font-size="9"` to `11px`) so badges remain securely enclosed within the finger silhouette.
  - Expand hand graphic scale to fill the lateral columns comfortably without crowding the note chips.

---

### BUG 4 — HAND ANIMATION DEPTH & REPEATED STRIKE FEEDBACK
- **Problem Statement:**
  Hand diagrams feel static. When chords change, active fingers lack physical depth and natural key-strike dynamics. Crucially, when consecutive chords use the *same* finger (e.g. thumb playing in C Major then G Major), no re-strike or release animation occurs.
- **Root Cause:**
  - In `WorkspaceHandController.js`, `_animateFinger` only toggles `groupEl.style.transform = isActive ? 'translateY(5px)' : 'translateY(0)'`. Because `isActive` remains `true` for successive chords using the same finger, no transition fires.
  - Legacy `HandAnimator.js` relies on external GSAP instead of unified Motion/WAAPI and is decoupled from the main playback loop.
- **Required Behavior:**
  - Synchronized downward key-press animation ($Y+5\text{px}$ to $Y+8\text{px}$) with natural spring/easing when a chord begins.
  - Fingers remain depressed for the duration of the chord.
  - Smooth release upon chord end.
  - **Consecutive Note Detection:** If a finger remains active in the next chord, trigger a distinct re-strike pulse (quick upward bounce and re-press) to indicate the new musical event.

---

### BUG 5 — 3-CHORD TIMELINE PHYSICAL SEQUENCE & FIXED COLUMN LABELS
- **Problem Statement:**
  The 3-chord timeline animation does not always maintain perfect geometric alignment with the stationary header labels (`PREVIOUS`, `CURRENT CHORD`, `NEXT`). The current chord must maintain unshakeable visual stability during its full duration.
- **Root Cause:**
  - In `frontend/js/ui/workspaceChordTimeline.js`, lane displacement is computed via `_getLaneDistance()` using `width * 0.30` clamped between 160px and 360px, whereas `.ws-fixed-labels-row` uses fixed CSS percentage widths (`25%` / `50%` / `25%`). This disparity causes chord cards to shift off-center from their structural labels on wide or narrow viewports.
  - Chord card dimensions and hero scaling must cleanly transition without text jumping or font reflow.
- **Required Behavior:**
  - Stationary labels `PREVIOUS`, `CURRENT CHORD`, `NEXT` remain 100% fixed in space.
  - Physical 4-lane sliding carousel:
    1. Previous fades out to the left ($-1D \to -2D$).
    2. Current glides smoothly left into Previous ($0 \to -1D$), shrinking from hero size.
    3. Next glides smoothly into Current ($+1D \to 0$), expanding to hero size and gaining glow.
    4. Incoming next chord enters from the right ($+2D \to +1D$).
  - Instant snap and animation cancellation on seek.

---

### BUG 6 — RESPONSIVE SCALING & CROSS-VIEWPORT PROPORTIONS
- **Problem Statement:**
  The permanent 4-tier workspace suffers from vertical crowding on compact laptop screens (e.g., 1366×768, 1280×800) and unutilized dead space on ultra-wide / 4K displays.
- **Root Cause:**
  - `piano.css` uses fixed `--piano-height: clamp(160px, 24vh, 260px)` and hardcoded grid fractions without dynamic viewport aspect-ratio balancing.
  - Arbitrary `@media (max-width: 640px)` media queries hide essential components (e.g. hand labels and chips) rather than reflowing gracefully.
- **Required Behavior:**
  - Fluid grid layout with balanced vertical height budgets across all 4 tiers: Header (44-48px), Central Learning Area (~40-45% of height), Piano (~25-30% of height), Playback Bar (56-64px).
  - No vertical scrollbars in standard desktop/laptop viewports. Zero horizontal overflow.
  - Natural fluid scaling for laptop screens, standard monitors, and 4K displays.

---

## 3. Existing Component Mapping & Architecture Notes

```
HotChords Frontend Component Hierarchy
├── PlaybackClock (frontend/js/audio/playbackClock.js) [AUTHORITATIVE TIME SOURCE]
│    │
│    ├──► SongAudioController (frontend/js/audio/songAudioController.js) [Audio Element]
│    ├──► UnifiedPianoPlaybackController (frontend/js/audio/unifiedPianoPlaybackController.js) [Tone.js Synth]
│    │
│    ├──► CurrentChordEngine (frontend/js/engine/currentChordEngine.js) [STATE RESOLUTION]
│    │     │
│    │     ├──► WorkspaceChordTimeline (frontend/js/ui/workspaceChordTimeline.js) [3-Chord WAAPI Carousel]
│    │     │
│    │     └──► PianoFingeringEngine (frontend/js/engine/pianoFingeringEngine.js) [VOICING & COLOR]
│    │           │
│    │           ├──► WorkspaceHandController (frontend/js/ui/workspaceHandController.js) [SVG Hands & Chips]
│    │           │     └──► HandDiagrams (frontend/js/ui/handDiagrams.js) [SVG Geometry]
│    │           │
│    │           └──► PianoKeyboard (frontend/js/ui/pianoKeyboard.js) [61-Key SVG Keyboard]
│    │
│    └──► UI Transport & Scrubber (frontend/index.html & frontend/css/piano.css) [Waveform + Controls]
```

---

## 4. Phase 1 Completion Confirmation
- [x] Codebase inspected and verified.
- [x] Source of truth mapped for all 9 core subsystems.
- [x] `hotchords-ui-ux` skill created at `.agents/skills/hotchords-ui-ux/SKILL.md`.
- [x] `hotchords-animation` skill created at `.agents/skills/hotchords-animation/SKILL.md`.
- [x] Technical bug specification documented in `docs/UI_UX_BUG_SPECIFICATION.md`.
- [x] Strict Phase 1 constraints observed: no code fixes applied, no tests executed, no git commits/pushes made. Ready for Phase 2 approval.
