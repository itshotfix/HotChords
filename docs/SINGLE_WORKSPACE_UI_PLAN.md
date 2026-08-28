# HotChords — Single Workspace UI: Audit & Implementation Plan

> **Status:** Audit complete — awaiting approval before any production code changes.
> **Reference sketch:** hand-drawn layout (header → meta → mode → waveform → LEFT HAND | PREV/CUR/NEXT | RIGHT HAND → piano)

---

## A. Current Architecture Audit

### File inventory snapshot

| File | Role | Lines |
|---|---|---|
| `frontend/index.html` | Shell, screen switching, init orchestration | 622 |
| `frontend/css/piano.css` | All styles, accumulation of Phase 8 + 9A + 9B | 1501 |
| `js/ui/dynamicChordReel.js` | 3-lane animated chord timeline (CRT) | 624 |
| `js/ui/beginnerPianoLearningRenderer.js` | Practice-mode full HUD (current/next card + hand cards) | 523 |
| `js/ui/lyricsChordRenderer.js` | Lyrics teleprompter with chord tags | 324 |
| `js/ui/beginnerChartRenderer.js` | Repetition-detecting chord chart renderer | 216 |
| `js/ui/chordRibbon.js` | Horizontal chord ribbon with timestamps | 124 |
| `js/ui/handDiagrams.js` | SVG hand factory (LH/RH) | 60 |
| `js/ui/pianoKeyboard.js` | SVG 61-key piano, ResizeObserver | 288 |
| `js/animations/handAnimator.js` | GSAP finger animation (global selectors) | 97 |
| `js/audio/playbackClock.js` | Authoritative rAF clock, singleton | 271 |
| `js/audio/songAudioController.js` | Audio element to PlaybackClock bridge | 374 |
| `js/audio/unifiedPianoPlaybackController.js` | Tone.js piano to PlaybackClock orchestrator | 329 |
| `js/audio/pianoPlaybackService.js` | Tone.Sampler wrapper | ~400 |
| `js/engine/currentChordEngine.js` | Chord-at-time query, beginner/original modes | 392 |
| `js/engine/chordTransitionEngine.js` | Transition difficulty analysis | 502 |
| `js/engine/pianoFingeringEngine.js` | Voicing and fingering assignment | ~300 |
| `js/engine/musicTheoryFormatter.js` | Chord name normalisation | ~50 |

### DOM structure of the current workstation (results-screen)

```
.workstation-container
+-- .song-meta-strip                          Key / BPM / Time / Track
+-- .tab-nav-strip                            3 primary tabs + quick-controls
+-- .music-player-stage
    +-- .mode-content-viewport                scrollable, swaps content
    |   +-- #simplified-chords-view           TAB 1 (hidden when inactive)
    |   |   +-- .lyrics-subnav (layer pills)
    |   |   +-- #simplified-chord-reel        DynamicChordReel instance 1
    |   +-- #practice-view                    TAB 2 (hidden when inactive)
    |   |   +-- .practice-subnav
    |   |   +-- #practice-chord-reel          DynamicChordReel instance 2
    |   +-- #play-track-view                  TAB 3 (hidden when inactive)
    |       +-- .lyrics-subnav
    |       +-- #lyrics-chord-view            LyricsChordRenderer
    |       +-- #play-track-chord-reel        DynamicChordReel instance 3
    +-- .playback-bar-container               waveform + transport
    +-- .piano-dock                           PianoKeyboard (always visible)
```

The piano dock IS at the bottom of `music-player-stage` and is never hidden. Tab switching uses `classList.toggle('hidden', ...)` — it IS a visibility toggle, not a layout replacement.

However the core problems are structural: there are **three separate DynamicChordReel instances** and two competing chord-display architectures. `DynamicChordReel` and `BeginnerPianoLearningRenderer` are both capable of showing the current chord with hands, but BPLR is declared and immediately ignored — it is never mounted in the current `initResults` path.

---

## B. Root Causes of Current UI Problems

### B-1. Three separate DynamicChordReel instances

`simplifiedChordReel`, `practiceChordReel`, and `playTrackChordReel` are three separate live objects all consuming `PlaybackClock`. Each maintains its own `_lastResolvedIndex`, `_activeAnimations`, and hidden DOM subtree. `updateClockUI` routes the clock tick to only one reel per mode — but the other two remain alive. This creates:
- Wasted layout compute for hidden DOM
- Risk of stale state when re-entering a mode after seeking
- No single source of truth for "what chord are we on"

### B-2. BeginnerPianoLearningRenderer is never mounted

`beginnerPianoLearningRenderer` is declared at line 180 of `index.html` but the only reference is in `resetApp()` where it is unmounted. It is never mounted or wired in `initResults`. The `practice-view` shows only `practiceChordReel` without hands. The BPLR's hand/chord HUD is entirely dead code from the user's perspective.

### B-3. Mode switching pauses playback

`setPrimaryMode()` calls `PlaybackClock.pause()` as its first line. This creates an audible and visible pause every time the user switches between Simple/Original/Practice modes — antithetical to a unified workspace where modes should change data, not interrupt the experience.

### B-4. CSS accumulation over three phases creates contradictions

`piano.css` has three separate layers (Phase 8 base, Phase 9A CRT rules, Phase 9B overrides):
- Line 36: `--piano-height: clamp(90px, 18vh, 150px)` in `:root`
- Line 1341: `--piano-height: clamp(84px, 14vh, 124px)` in a second `:root` block — overrides the first
- `.mode-content-viewport` is defined twice (lines 357-365 and 1346-1351) with different padding and gap
- `.simplified-chords-view`, `.practice-view` have `min-height: 100%` (line 1357) which fights with the parent's `overflow-y: auto` — this is the **primary cause of empty vertical space**
- Old reel classes (`.reel-hand-col`, `.reel-slot-*`) are kept as `display:none` stubs

### B-5. overflow-y: auto + min-height: 100% causes empty space

`.mode-content-viewport` has `flex: 1; overflow-y: auto`. Children have `min-height: 100%`. This forces the scroll container to be at least as tall as its `flex: 1` height. When the CRT shell is compact (3-chord display), the remaining space below is empty gray.

### B-6. Hand animations never fire during playback

When `showHands: true` is passed to `practiceChordReel`, hands render inside the CRT shell. But `HandAnimator.animateChord()` uses global CSS selectors (`#lh-finger-1`, `#rh-finger-1`) that are never called from `updateClockUI`. The hands render statically but never animate during playback.

### B-7. Piano highlighting and chord reel are not sharing state

`updateClockUI` performs two separate chord lookups: `simplifiedChordReel.update(snap.currentTime)` and `currentChordEngine.getState(snap.currentTime)`. If the chord arrays were loaded differently there is no guarantee they resolve to the same chord — a latent piano vs reel mismatch.

### B-8. renderTimeline() references #timeline which does not exist

`renderTimeline()` at line 599 calls `document.getElementById('timeline')`. This element does not exist in the HTML. The function is never called and is dead code.

### B-9. HandAnimator uses global GSAP selectors

`HandAnimator.animateChord()` selects `.hand-finger path` globally. If two hand diagram sets exist on the page both react and fight because GSAP kills conflicting tweens by selector. The only safe design is one canonical set of hand SVG elements.

### B-10. Lyrics view creates a duplicate chord display

The Play Track view contains both `#lyrics-chord-view` (tall teleprompter) AND `#play-track-chord-reel` below it. Two simultaneous chord displays in one mode, plus a viewport taller than available space — forcing scroll that breaks the `overflow: hidden` app shell.

---

## C. Proposed Single-Workspace DOM Hierarchy

The workspace is one permanent layout. Upload and Analysis remain as modal screens. Once analysis completes the user enters the workspace and never leaves it (except "New Song").

```html
<body class="app-shell">

  <div id="upload-screen" class="screen">...</div>
  <div id="analysis-screen" class="screen">...</div>

  <div id="workspace" class="workspace hidden" data-mode="simple">

    <!-- ROW 1: HEADER BAR -->
    <header class="ws-header">
      <div class="ws-logo">Hot<span>Chords</span></div>
      <div class="ws-meta">
        <span id="ws-key">--</span>
        <span id="ws-bpm">--</span>
        <span id="ws-sig">--</span>
        <span id="ws-track">--</span>
      </div>
      <div class="ws-mode-selector">
        <button class="mode-btn active" data-mode="simple">Simple</button>
        <button class="mode-btn" data-mode="original">Original</button>
        <button class="mode-btn" data-mode="practice">Practice</button>
      </div>
      <div class="ws-transport-controls">
        <!-- speed buttons, sustain, restart, stop, new-song -->
      </div>
    </header>

    <!-- ROW 2: WAVEFORM + PLAYBACK -->
    <div class="ws-playback">
      <div class="ws-waveform" id="wf-wrap">
        <canvas id="wf-canvas"></canvas>
        <div id="playhead"></div>
      </div>
      <div class="ws-transport-row">
        <button id="main-play-btn" class="play-btn">Play</button>
        <span id="cur-time" class="time-disp">0:00</span>
        <input id="seek-bar" type="range" class="seek-bar">
        <span id="dur-time" class="time-disp">0:00</span>
      </div>
    </div>

    <!-- ROW 3: CENTRAL LEARNING AREA -->
    <div class="ws-learning-area">

      <!-- LEFT HAND COLUMN (0fr in simple/original, expands in practice) -->
      <div id="ws-hand-left" class="ws-hand-col ws-hand-col--left">
        <div class="ws-hand-label">Left Hand</div>
        <div id="ws-lh-svg" class="ws-hand-svg"><!-- SVG injected once at init --></div>
        <div id="ws-lh-chips" class="ws-finger-chips"></div>
      </div>

      <!-- CENTER: CHORD TIMELINE (only chord display in all modes) -->
      <div class="ws-chord-center">

        <div id="chord-viewport" class="ws-chord-viewport">
          <div id="chord-track" class="ws-chord-track">
            <div id="chord-prev" class="chord-card chord-card--prev">
              <div class="chord-label">Previous</div>
              <div class="chord-name" data-chord-name>--</div>
            </div>
            <div id="chord-current" class="chord-card chord-card--current" aria-live="polite">
              <div class="chord-label">Now</div>
              <div class="chord-name" data-chord-name>--</div>
              <div class="chord-voicing" data-chord-voicing></div>
              <div class="chord-progress-track">
                <div id="chord-progress-fill" class="chord-progress-fill"></div>
              </div>
            </div>
            <div id="chord-next" class="chord-card chord-card--next">
              <div class="chord-label">Next</div>
              <div class="chord-name" data-chord-name>--</div>
            </div>
          </div>
        </div>

        <!-- LYRICS PANEL (0fr in simple/practice, 1fr in original) -->
        <div id="ws-lyrics-panel" class="ws-lyrics-panel">
          <div id="ws-lyrics-content" class="ws-lyrics-scroll"></div>
        </div>

      </div>

      <!-- RIGHT HAND COLUMN (0fr in simple/original, expands in practice) -->
      <div id="ws-hand-right" class="ws-hand-col ws-hand-col--right">
        <div class="ws-hand-label">Right Hand</div>
        <div id="ws-rh-svg" class="ws-hand-svg"><!-- SVG injected once at init --></div>
        <div id="ws-rh-chips" class="ws-finger-chips"></div>
      </div>

    </div>

    <!-- ROW 4: PERSISTENT PIANO (never hidden) -->
    <div id="ws-piano" class="ws-piano">
      <div id="piano-keyboard"></div>
    </div>

  </div>

</body>
```

---

## D. Proposed Responsive Layout Strategy

Single CSS Grid for the four rows. No `min-height: 100%` on children, no `overflow-y: auto` on content panels, no arbitrary pixel margins.

```css
.workspace {
  display: grid;
  grid-template-rows:
    44px
    clamp(52px, 9vh, 72px)
    1fr
    clamp(84px, 14vh, 124px);
  height: 100vh;
  overflow: hidden;
}

.ws-learning-area {
  display: grid;
  grid-template-columns: 0fr 1fr 0fr;
  transition: grid-template-columns 0.3s ease;
  align-items: center;
  overflow: hidden;
  padding: clamp(12px, 2.4vh, 24px) clamp(14px, 2.8vw, 32px);
  gap: clamp(12px, 2vw, 28px);
}

.workspace[data-mode="practice"] .ws-learning-area {
  grid-template-columns:
    clamp(130px, 18vw, 200px)
    1fr
    clamp(130px, 18vw, 200px);
}

.ws-chord-center {
  display: grid;
  grid-template-rows: 1fr 0fr;
  height: 100%;
  overflow: hidden;
}

.workspace[data-mode="original"] .ws-chord-center {
  grid-template-rows: auto 1fr;
}
```

Mode switching sets `data-mode` on `.workspace`. No elements are hidden — hand columns collapse to `0fr` via CSS grid transition. The lyrics panel collapses to `0fr` in simple/practice and expands in original mode. No `display:none` on any structural layout section.

---

## E. Proposed Chord Timeline Architecture / State Machine

One singleton: `WorkspaceChordTimeline` — not instantiated per mode.

```
PlaybackClock (rAF subscribe)
    |
    v
WorkspaceChordTimeline.onTick(currentTime)
    |-- index changed --> fireTransition(oldIdx, newIdx, isSeeking)
    |-- same index   --> updateProgress(currentTime, currentIdx)
```

`WorkspaceChordTimeline` owns:
- `_chords[]` — active chord array set by `loadChords()`
- `_currentIdx` — single authoritative index
- `_isAnimating` — single animation gate
- References to the three permanent DOM elements (`#chord-prev`, `#chord-current`, `#chord-next`)

Mode switching calls `loadChords(newArray)` on the singleton. No new objects are created.

State machine:
```
IDLE(idx)
  +-- enters new chord region --> TRANSITION(oldIdx -> newIdx)
  |     +-- forward +1 step AND not seeking --> ANIMATING
  |     |     --> WAAPI 300ms --> COMMITTED --> IDLE(newIdx)
  |     +-- else --> INSTANT_REBUILD(newIdx) --> IDLE(newIdx)
  +-- same idx --> UPDATE_PROGRESS
```

`ANIMATING` blocks further transitions until WAAPI `onfinish`. If a new change arrives during animation, WAAPI is cancelled and falls through to `INSTANT_REBUILD`.

---

## F. Proposed Chord Transition Animation

Inheriting proven mechanics from `dynamicChordReel.js` (WAAPI, 300ms, cubic-bezier(0.22, 1, 0.36, 1)) with corrections:

1. Three permanent elements at rest. During transition, inject a transient `#chord-incoming-next` into `#chord-track` at `X = +2D`, animate to `X = +D`. On `onfinish`, update data in the three permanent elements and remove the transient.

2. No `fill: 'forwards'` WAAPI commits. Commit by calling `cancel()` on all animations in `onfinish` and applying final transform via `el.style.transform`. This avoids the stale WAAPI fill state that caused Phase 9A visual glitches.

3. Lane distance `D` computed from viewport width at animation start.

4. Reduced motion: detect `prefers-reduced-motion` once at init. If true, skip WAAPI and call `_instantRebuild` on every chord change.

5. `#chord-prev` and `#chord-next` click handlers call `PlaybackClock.seek(startTime)`.

---

## G. Proposed Hand / Chord Relationship

### Single SVG set, permanently in the DOM

`HandDiagrams.getHandMarkup('LH')` and `getHandMarkup('RH')` are called once during workspace init and injected into `#ws-lh-svg` and `#ws-rh-svg`. These elements are never re-created.

### Hand update driven by WorkspaceChordTimeline

On chord change, `WorkspaceChordTimeline` calls:
```js
WorkspaceHandController.update(chordName, notes, voicing);
```

`WorkspaceHandController` updates finger dot colours / translateY and finger chip text in `#ws-lh-svg` / `#ws-rh-svg` / `#ws-lh-chips` / `#ws-rh-chips` by **element reference**, not global CSS selectors.

### Hand visibility via grid

`ws-hand-col` elements are `0fr` in simple/original modes. Elements remain in DOM but are zero-width with `overflow: hidden`. No layout jump on mode switch, no SVG re-render on mode switch.

---

## H. Piano Positioning Strategy

Piano stays in Row 4 of the workspace grid:
- Never hidden (no `display:none`, no `.hidden` toggling)
- Never inside a mode tab (outside `.ws-learning-area`)
- Sized by `--piano-height: clamp(84px, 14vh, 124px)` — one definition only, at the top of CSS
- `PianoKeyboard` ResizeObserver re-renders SVG on container resize — unchanged

Piano highlighting chain is **unchanged**:
```
updateClockUI
  --> currentChordEngine.getState(currentTime)
  --> piano.voicing = PianoFingeringEngine.getChordVoicing(chordName, notes)
  --> piano.applyVoicingDOM()
```

After refactor: `WorkspaceChordTimeline.loadChords(chords)` also updates `currentChordEngine` — they use the same chord reference, eliminating the dual-lookup mismatch.

---

## I. Mode-Switching Strategy

```js
let activeMode = 'simple';         // 'simple' | 'original' | 'practice'
let activeChordLayer = 'beginner'; // 'beginner' | 'original'
```

### What changes on mode switch

| Property | Simple | Original | Practice |
|---|---|---|---|
| `data-mode` on `.workspace` | `simple` | `original` | `practice` |
| Chord array | `beginnerChords` | `originalChords` | per chord layer |
| Hand column grid width | `0fr` | `0fr` | `clamp(130px, 18vw, 200px)` |
| Lyrics panel grid height | `0fr` | `1fr` | `0fr` |
| Key display | Easy key | Original key | per chord layer |
| Piano playback mode | `BEGINNER_CHORDS` | `ORIGINAL_CHORDS` | per chord layer |

### What does NOT change on mode switch

- PlaybackClock is NOT paused
- Piano dock position
- Waveform / playhead / transport
- Chord card DOM elements
- Hand SVG elements

### setMode

```js
function setMode(newMode) {
  activeMode = newMode;
  document.getElementById('workspace').dataset.mode = newMode;

  document.querySelectorAll('.mode-btn').forEach(btn =>
    btn.classList.toggle('active', btn.dataset.mode === newMode)
  );

  const chords = resolveChords(newMode, activeChordLayer);
  WorkspaceChordTimeline.loadChords(chords); // instant rebuild at current clock time

  UnifiedPianoPlaybackController.switchMode(
    resolvePlaybackMode(newMode, activeChordLayer)
  );

  document.getElementById('ws-key').textContent =
    resolveKeyDisplay(newMode, activeChordLayer);
}
```

---

## J. Lyrics Integration Strategy

Lyrics live inside `.ws-chord-center` as a collapsible panel below the chord viewport — not a separate mode screen.

In **Original mode**: `ws-lyrics-panel` grid row expands to `1fr`. The chord viewport shrinks to its intrinsic height. Lyrics scroll as teleprompter.

In **Simple / Practice modes**: `ws-lyrics-panel` is `0fr`. Chord viewport expands to fill all available height.

`LyricsChordRenderer.updateActive()` is called from `updateClockUI` unconditionally — safe when container is `0fr` (no layout queries triggered on hidden overflow).

The duplicate `#play-track-chord-reel` is removed entirely.

---

## K. Components to Reuse (unchanged)

| Component | Rationale |
|---|---|
| `PlaybackClock` singleton | Correct, authoritative, well-tested. |
| `SongAudioController` | Correct. |
| `UnifiedPianoPlaybackController` | Keep. `setMode()` calls `switchMode()` on it. |
| `PianoPlaybackService` | Keep. |
| `OriginalChordPlaybackController` | Keep. |
| `BeginnerChordPlaybackController` | Keep. |
| `CurrentChordEngine` | Keep. Wired via `WorkspaceChordTimeline.loadChords()`. |
| `ChordTransitionEngine` | Keep. Used internally. |
| `PianoFingeringEngine` | Keep. |
| `MusicTheoryFormatter` | Keep. |
| `HandDiagrams` | Keep SVG generator. Inject once. |
| `PianoKeyboard` | Keep. Mount once into `#ws-piano`. |
| `LyricsChordRenderer` | Keep. Mount once into `#ws-lyrics-content`. |

---

## L. Components to Refactor

### L-1. DynamicChordReel to WorkspaceChordTimeline

Convert from a multi-instantiable class to a singleton module operating on the three permanent DOM elements by ID reference. Remove `_render()` — layout lives in HTML. Keep all animation and state machine logic. Remove `showHands` option.

### L-2. HandAnimator to WorkspaceHandController

Replace global GSAP selectors with element-reference selectors scoped to `#ws-lh-svg` and `#ws-rh-svg`. Add `init(lhEl, rhEl)` initialiser. Remove GSAP dependency where possible — CSS transitions on `fill` and `transform` are sufficient.

### L-3. Inline script to workspace.js

Extract all inline `<script>` logic into `frontend/js/workspace.js`. Enables future testing.

### L-4. piano.css deduplication

- Remove second `:root` block
- Remove duplicate `.mode-content-viewport`
- Remove `.reel-*` backward-compat stubs
- Remove `.bplr-*` rules
- Rename `.crt-*` to `.chord-card--*` / `.ws-chord-*`
- Add workspace grid rules

---

## M. Components to Remove / Deprecate

| Component | Reason |
|---|---|
| `BeginnerPianoLearningRenderer` | Never mounted. Archive to `frontend/js/deprecated/`. |
| `BeginnerChartRenderer` | Not visible in any current mode. Archive. Remove from script load. |
| `ChordRibbon` | Horizontal ribbon with timestamps — against UX principles. Archive. |
| `keyboardOverlayManager.js` | Audit; remove if not used in new workspace. |
| `renderTimeline()` inline function | Dead code (`#timeline` does not exist). Delete. |
| `beginnerPianoLearningRenderer` variable | Never assigned. Delete. |
| Three reel variables | Replaced by `WorkspaceChordTimeline`. Delete. |

---

## N. Tests That Need to Be Added / Updated

### Tests to update

| Test file | Required change |
|---|---|
| `test_phase_8_rearchitecture.js` | Update to load `workspace.js`. Test `setMode()` does not pause clock. |
| `test_chord_reel_state_machine.js` | Update container mock to permanent 3-element structure. Remove multi-instance tests. |
| `test_beginner_piano_learning_renderer.js` | Update or archive. |
| `test_phase_7c_ui_ux.js` | Audit old tab ID references. Update to workspace structure. |

### New tests to add

| Test | Validates |
|---|---|
| `test_workspace_mode_switch.js` | `setMode()` does not pause PlaybackClock. Data-mode updates. Chord array swaps. Key display updates. |
| `test_workspace_chord_timeline.js` | Singleton loadChords, single index resolution, animation state machine, seek cancel. |
| `test_workspace_hand_controller.js` | DOM mutations scoped to `#ws-lh-svg` / `#ws-rh-svg` only. |
| `test_lyrics_panel_integration.js` | LyricsChordRenderer mounts once. updateActive safe when panel is 0fr. |
| Browser visual test (manual) | All 4 songs, all 4 viewports, all modes. |

---

## O. Implementation Sequence (Small Safe Phases)

Each phase is independently deployable. All 90 Python tests pass at the end of every phase.

### Phase 1 — CSS Reset only (no HTML or JS changes)

1. Remove duplicate `:root` block (lines 1340-1344) — one `--piano-height` definition only
2. Merge duplicate `.mode-content-viewport` definitions
3. Remove `min-height: 100%` from `.simplified-chords-view`, `.practice-view`, `.play-track-view`
4. Change `.mode-content-viewport` from `overflow-y: auto` to `overflow: hidden`
5. Add explicit height to `.crt-viewport` to prevent collapse

Acceptance: Empty space eliminated. Three-chord reel fills available area. All 90 Python tests pass.

---

### Phase 2 — DOM Restructure (HTML + CSS additions, no JS logic changes)

1. Replace `#results-screen` inner HTML with new workspace DOM (Section C)
2. Add workspace CSS grid rules (Section D)
3. All existing JS continues to work against preserved IDs (`seek-bar`, `cur-time`, etc.)
4. Verify upload and analysis screens unchanged

Acceptance: Structural grid renders. Hand column placeholders visible. Chord viewport visible but empty. Piano at bottom. No JS errors.

---

### Phase 3 — WorkspaceChordTimeline

1. Create `frontend/js/ui/workspaceChordTimeline.js` from `DynamicChordReel` without `_render()`
2. Wire in `initResults()`: `WorkspaceChordTimeline.loadChords(timeline.beginnerChords)`
3. Wire `updateClockUI` to call only `WorkspaceChordTimeline.update(snap.currentTime)`
4. Remove the three separate reel variables and their init code
5. Update `test_chord_reel_state_machine.js`

Acceptance: Single chord reel animates during playback. Piano keys highlight in sync. Seeking works. Previous/Next click-to-seek works.

---

### Phase 4 — Mode Switching (no pause)

1. Implement `setMode(mode)` per Section I
2. Remove `PlaybackClock.pause()` from mode switch path
3. Wire mode buttons to `setMode()`
4. Implement `setChordLayer(layer)` for Easy/Original chord sub-toggle
5. Add `test_workspace_mode_switch.js`

Acceptance: Switching modes mid-playback is seamless. No audio pause. No visual jump. Chord reel updates immediately.

---

### Phase 5 — Hand Integration

1. Create `WorkspaceHandController` scoped to element references
2. Inject `HandDiagrams` SVG once into `#ws-lh-svg` / `#ws-rh-svg` during `initWorkspace()`
3. Wire `WorkspaceChordTimeline` to call `WorkspaceHandController.update()` on chord change
4. Apply `data-mode="practice"` CSS to expand hand columns via grid transition
5. Add `test_workspace_hand_controller.js`

Acceptance: In Practice mode, hands animate per chord change. In Simple/Original, hand columns are collapsed. No GSAP global selector conflicts.

---

### Phase 6 — Lyrics Integration

1. Mount `LyricsChordRenderer` into `#ws-lyrics-content` once after analysis
2. Call `LyricsChordRenderer.updateActive()` unconditionally in `updateClockUI`
3. `data-mode="original"` CSS expands lyrics panel grid row
4. Remove `#play-track-chord-reel` from HTML and JS
5. Add `test_lyrics_panel_integration.js`

Acceptance: Original mode shows lyrics panel below chord reel. Scrolls correctly. Simple/Practice show no lyrics panel. No duplicate chord display.

---

### Phase 7 — Cleanup and Polish

1. Archive `BeginnerPianoLearningRenderer`, `BeginnerChartRenderer`, `ChordRibbon`
2. Remove dead `renderTimeline()` function
3. Extract inline JS to `frontend/js/workspace.js`
4. Remove all `.reel-*` and `.bplr-*` stubs from `piano.css`
5. Final CSS audit
6. Run all 90 Python tests + all updated JS tests
7. Manual browser validation — all 4 test songs, all 4 viewport sizes

---

## P. Visual Acceptance Criteria

Validated in actual browser only — automated tests cannot confirm these.

### Structure
- [ ] Header always visible and compact (no taller than 44px)
- [ ] Waveform + transport always directly below header
- [ ] Piano always docked at bottom, never hidden
- [ ] No vertical scrollbar in app shell at any viewport width >= 375px
- [ ] No empty gray space between chord reel and piano dock in any mode

### Chord timeline
- [ ] Three slots always visible: Previous (left, muted), Current (center, large, glowing), Next (right, muted)
- [ ] Current chord name is >= 3x font size of Previous/Next
- [ ] Chord transition animates physically left (not a text swap) at every natural chord change
- [ ] Seeking instantly rebuilds all three slots with no animation glitch
- [ ] Progress fill bar under current chord moves in real time
- [ ] Previous and Next are click-to-seek targets

### Mode switching
- [ ] Switching modes does not pause or stutter audio playback
- [ ] No scroll or layout jump on mode switch
- [ ] Mode button active state updates immediately
- [ ] Chord reel updates to correct data immediately after mode switch

### Practice mode hands
- [ ] Hand columns appear with smooth grid expansion (no layout jump)
- [ ] Finger pads animate with colour on each chord change
- [ ] Finger number labels visible and correctly mirrored on left hand

### Original mode lyrics
- [ ] Lyrics panel expands below chord reel (grid row transition, no jump)
- [ ] Active lyric line highlighted and auto-scrolls
- [ ] Chord tags above lyrics are clickable for seeking
- [ ] Chord reel (3 slots) remains visible above lyrics at all times

### Piano
- [ ] Keys highlight correctly for current chord voicing
- [ ] Left hand bass keys and right hand harmony keys highlighted simultaneously
- [ ] Key highlighting updates within one rAF tick of chord change

### Responsiveness — all four viewport widths
- [ ] 1440px: full layout, hands + reel + piano in correct proportions
- [ ] 1024px: layout correct, no wrapping or overflow
- [ ] 768px: hand columns collapse gracefully
- [ ] 375px: chord reel dominates, hands hidden, piano visible
- [ ] All 4 test songs: Tu Mera, Die With A Smile, Nahi Milta, Rap God

---

## Open Questions Requiring Approval Before Coding Begins

> [!IMPORTANT]
> **Q1 — Mode naming.** Sketch shows Simple / Original / Practice. Current code uses `simplified_chords / play_track / practice`. The plan adopts **Simple / Original / Practice** as the final mode names. Confirm.

> [!IMPORTANT]
> **Q2 — Sub-layer chord selector.** Currently Simple and Play Track each have an Easy/Original sub-selector. In the unified workspace, should this be:
> **(A)** A single toggle visible in all modes (Simple / Original / Practice all respect it), OR
> **(B)** Sub-selector only in Simple mode; Original always shows original chords; Practice always shows beginner chords?

> [!IMPORTANT]
> **Q3 — Lyrics in Practice mode.** The sketch does not show lyrics in Practice mode. The plan hides the lyrics panel in Practice mode. Confirm this is correct.

> [!NOTE]
> **Q4 — BeginnerChartRenderer.** This repetition-detecting chord chart renderer is loaded but not visible in any mode. The plan archives it entirely. If you want it exposed somewhere in the new workspace, note this now before it is archived.

> [!NOTE]
> **Q5 — Piano playback audio in Practice mode.** Simple uses beginner chord audio. Original uses original chord audio. Should Practice always use beginner chords (learning focus), or match the chord layer selector?
