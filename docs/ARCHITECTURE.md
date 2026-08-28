# HotChords Architecture

Technical reference for contributors and curious developers.

---

## Overview

HotChords is a locally-served web application. The Python backend runs a FastAPI/Uvicorn server that serves both the REST API and the static frontend. There is no external network dependency, no database, and no build step.

```
python3 hotchords.py
    └── backend/main.py             starts Uvicorn + opens browser
        └── backend/api/router.py   FastAPI app
            ├── POST /analyze       receives audio file, starts background analysis
            ├── GET  /progress      returns { msg, pct } polling data
            ├── GET  /result        returns full JSON result when ready
            └── /css, /js, /       serves frontend static files
```

---

## Backend: Audio Analysis Pipeline

### Entry: `backend/analysis/pipeline.py → run_pipeline(filepath)`

The pipeline runs in a FastAPI `BackgroundTask`. Progress is written to a global dict polled by the frontend via `/progress`.

#### Stage 1 — Stem Separation (Optional)

```python
# Demucs 'htdemucs' separates:
#   sources[0] = drums
#   sources[1] = bass
#   sources[2] = other (melody/harmony)
#   sources[3] = vocals
#
# We use [0]+[1]+[2] as the instrumental stem for analysis because
# leaving vocals in confuses the chroma features with sung pitches.
# Falls back to original file if Demucs is not installed or fails.
instrumental_audio = sources[0] + sources[1] + sources[2]
```

Device selection is automatic: CUDA → MPS (Apple Silicon) → CPU.

#### Stage 2 — Audio Loading

```python
y, sr = librosa.load(path, sr=22050, mono=True)
# 22kHz is sufficient for chroma features (max pitch: C7 ≈ 2093Hz)
# and reduces memory by ~50% versus 44.1kHz.
```

#### Stage 3 — Harmonic-Percussive Source Separation (HPSS)

```python
y_harm = librosa.effects.harmonic(y, margin=4)
# HPSS separates the spectrogram into harmonic (tonal) and percussive
# (transient) components using median filtering.
# margin=4 means the harmonic filter is 4× stricter — we aggressively
# suppress drums and percussion to get cleaner chroma features.
```

#### Stage 4 — Chroma Constant-Q Transform (CQT)

```python
chroma = librosa.feature.chroma_cqt(y=y_harm, sr=sr, hop_length=512, bins_per_octave=36)
# CQT is preferred over STFT chroma because its frequency bins are
# logarithmically spaced — each octave has equal bin count.
# 36 bins/octave = 3× oversampling (standard is 12) for higher pitch accuracy.
# hop_length=512 at 22kHz → ~23ms per frame.
```

```python
# Smooth chroma over a ~0.4s window to reduce note-onset transient noise.
# Without smoothing, brief accidental notes create spurious chord detections.
win = max(1, int(0.4 * sr / hop))
chroma_s = np.apply_along_axis(lambda x: np.convolve(x, np.ones(win)/win, 'same'), 1, chroma)
```

#### Stage 5 — Chord Template Matching

```python
# Chord templates are L2-normalized 12-dimensional vectors.
# Each element = expected chroma energy at that pitch class.
# Cosine similarity between chroma observation and template measures chord fit.
similarity = CHORD_MAT.T @ chroma_norm   # shape: (61 chords, frames)
```

**Overtone-aware templates** (in `_build_overtone_templates()`):
```python
# Real instruments produce overtones at integer multiples of the fundamental.
# We model the first three relevant harmonics:
v[pitch]              += 1.0   # Fundamental
v[(pitch + 7)  % 12] += 0.35  # Perfect 5th (3rd harmonic) — very prominent
v[(pitch + 4)  % 12] += 0.15  # Major 3rd (5th harmonic) — present in most timbres
v[(pitch + 12) % 12] += 0.20  # Octave (2nd harmonic) — always present
# This prevents the Major 5th overtone from making everything look like a power chord.
```

#### Stage 6 — Beat Quantization

```python
# Instead of classifying every frame independently (noisy), we aggregate
# similarity scores within each beat-length segment.
# This naturally aligns chord detections with the musical grid.
beat_similarities[i] = similarity[:, mask].mean(axis=1)
```

#### Stage 7 — Viterbi HMM Decoding

This is the most important accuracy improvement over naive argmax detection.

**Transition matrix** (`build_transition_matrix(key, scale)`):
```python
# Music is not random — certain chord transitions are far more common.
# The transition matrix biases the HMM toward musically sensible sequences:

A[i, i] = 0.72         # 72% chance of staying on the same chord.
                        # Chords typically last 1-4 beats, not 1 frame.

weight *= 3.5           # Diatonic chords (in the detected key) are strongly preferred.
                        # A song in C major mostly uses C, Dm, Em, F, G, Am, Bdim.

weight *= 2.0           # Perfect 4th (5 semitones) and Perfect 5th (7 semitones) root
                        # motion is extremely common in all Western music (e.g. G→C, C→G).
```

**Viterbi decoding** (`viterbi_decode()`):
```python
# Viterbi finds the globally optimal chord sequence given both the per-beat
# acoustic observations AND the transition probabilities.
# Computed in log space to prevent numerical underflow with long songs.
log_A = np.log(transition_matrix + 1e-100)
log_emissions = similarity * 9.0   # Scale factor converts cosine similarity to
                                    # log-likelihood range comparable to log_A
```

#### Stage 8 — Theory Enrichment

After chord sequence is finalized:
- Each chord is run through `musician_friendly_name()` for enharmonic normalization
- Roman numerals are computed relative to the detected key
- A beginner chart is generated via `simplify_progression()` (triad collapse + duration filtering + optional transposition to easy key)

---

## Music Theory Engine: `backend/theory/theory.py`

### Enharmonic Normalization

```python
# Rule: prefer flat-side enharmonics for black-key roots because
# musicians read Ab, Eb, Bb — not G#, D#, A#.
# Exception: F# is kept as F# (common key in guitar music).
ENHARMONIC_MAP = {
    'G#': 'Ab',   # Ab is standard in Western notation
    'D#': 'Eb',   # Eb appears in Bb jazz and classical keys
    'A#': 'Bb',   # Bb is ubiquitous
    'Gb': 'F#',   # F# is preferred for guitar contexts
    ...
}
```

### Chord Simplification (Beginner Mode)

The simplification has three passes:
1. **Triad collapse** — `Cmaj7 → C`, `Am7 → Am`, `Bdim → Bm` (with key-aware substitution)
2. **Merge consecutive identical chords** — avoids rapid flicker at beat boundaries
3. **Remove short passing chords** (<1.5s) — reduces cognitive load for learners

### Transposition to Easy Key

```python
# If the detected key has many sharps/flats, suggest transposing to a beginner key:
# Major: C (0 accidentals), G (1 sharp), F (1 flat)
# Minor: Am (0), Em (1 sharp), Dm (1 flat)
# 
# The closest easy key by semitone distance is chosen.
# The entire chord timeline is transposed chromatically.
```

---

## Frontend Architecture

The frontend is a single-page application loaded from `frontend/index.html`. There is no bundler, no npm, and no build step. Modules are loaded via plain `<script>` tags in dependency order.

### Module Load Order

```html
<!-- 1. Core theory (no deps) -->
<script src="/js/engine/musicTheoryFormatter.js"></script>

<!-- 2. Fingering engine (no deps) -->
<script src="/js/engine/pianoFingeringEngine.js"></script>

<!-- 3. UI modules (depend on engine) -->
<script src="/js/ui/handDiagrams.js"></script>
<script src="/js/ui/pianoKeyboard.js"></script>
<script src="/js/ui/keyboardOverlayManager.js"></script>

<!-- 4. Animation (depends on GSAP CDN + piano) -->
<script src="/js/animations/handAnimator.js"></script>

<!-- 5. App logic in index.html inline <script> -->
```

### Piano Keyboard: `pianoKeyboard.js`

The `PianoKeyboard` class generates a complete SVG of 61 piano keys (C2–C7) calculated from first principles:
- White key width = `containerWidth / 36` (36 white keys in 61-key range)
- Black key width = `whiteKeyWidth * 0.64` (standard piano proportion)
- Black key positions use octave-relative offsets (`BLACK_OFFSETS`)

Keys use **DOM state updates** rather than `innerHTML` re-renders on every chord change — this is critical for 60fps performance during playback.

### Fingering Engine: `pianoFingeringEngine.js`

Implements the **"One Voicing Per Hand"** pedagogical philosophy:
- **Left Hand**: Root + 5th in Octave 2 (MIDI 36+) — bass/power anchor
- **Right Hand**: Full chord tones in Octave 4 (MIDI 60+) — harmonic clarity

Finger assignments follow the standard classical 5-finger color system:
- Thumb (1) = Red, Index (2) = Yellow, Middle (3) = Green, Ring (4) = Teal, Pinky (5) = Blue

### Animation: `handAnimator.js`

GSAP 3 timeline:
1. Kill any running tweens from the previous chord
2. Reset all fingers to white/neutral
3. Animate active fingers: fill with pedagogical color + `y: 8` press motion
4. Piano keys: `scaleY` pulse + brightness flash via `PianoKeyboard.pulseKey()`

Respects `prefers-reduced-motion` — immediately skips to final state if set.

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/analyze` | Upload audio file (multipart/form-data) |
| `POST` | `/analyze-path` | Analyze a file by local path `{ "path": "..." }` |
| `GET` | `/progress` | `{ "msg": "...", "pct": 0–100 }` |
| `GET` | `/result` | Full analysis JSON (202 while processing) |
| `GET` | `/` | Serves `frontend/index.html` |
| Static | `/css/*`, `/js/*` | Frontend assets |

### `/result` JSON Schema

```json
{
  "ready": true,
  "duration": 214.5,
  "key": "C",
  "scale": "Major",
  "key_full": "C Major",
  "tempo": 120.3,
  "time_sig": "4/4",
  "scale_notes": [0, 2, 4, 5, 7, 9, 11],
  "chords": [
    { "time": 0.0, "end": 1.3, "chord": "C", "raw_chord": "C", "confidence": 0.87 }
  ],
  "unique_chords": ["C", "Am", "F", "G"],
  "chord_data": {
    "C": {
      "notes": [0, 4, 7],
      "note_names": ["C", "E", "G"],
      "fingers": { "0": 1, "4": 3, "7": 5 },
      "difficulty": "easy"
    }
  },
  "roman_numerals": { "C": "I", "Am": "vi", "F": "IV", "G": "V" },
```

---

## Lyrics & Transcription Reference

For full details on the decoupled lyrics pipeline, vocal separation, ASR, alignment engine, and phased roadmap, see [LYRICS_ARCHITECTURE.md](file:///Volumes/TIKDI/APP%20Development/HotChords%20App/docs/LYRICS_ARCHITECTURE.md).

