# HotChords Real-Piano Acoustic Recording & Benchmark Protocol
**Standardized Procedure for Acoustic Piano Data Collection & MIR Validation**

---

## 1. Overview & Objective
This protocol establishes a standardized, reproducible, and accessible recording methodology for capturing acoustic piano audio for the HotChords evaluation suite. The protocol is designed to be executed in everyday real-world environments (living rooms, teaching studios, practice rooms) using standard consumer or prosumer audio hardware without requiring laboratory-grade anechoic chambers.

---

## 2. Audio Capture Specifications

| Parameter | Specification | Rationale |
|---|---|---|
| **Audio Format** | Lossless Linear PCM WAV (`.wav`) or FLAC (`.flac`) | Prevents lossy compression artifacts (MP3/AAC psychoacoustic masking) from altering harmonic partials. |
| **Sample Rate** | $44.1\text{ kHz}$ or $48.0\text{ kHz}$ (downsampled to $22.05\text{ kHz}$ in pipeline) | Standard audio hardware rate; maintains Nyquist frequency well above highest piano fundamental ($4.186\text{ kHz}$). |
| **Bit Depth** | $24\text{-bit}$ preferred ($16\text{-bit}$ minimum) | Provides $>96\text{ dB}$ dynamic range, preventing quantization noise in soft pianissimo passages. |
| **Channel Count** | Mono or Dual Mono (Left channel processed) | Real-time microphone capture in browser Web Audio API is monophonic. |
| **Peak Recording Level** | Target peak: $-6\text{ dBFS}$ to $-3\text{ dBFS}$ | Guarantees clean headroom to eliminate digital clipping on fortissimo attacks. |
| **Preamplifier Gain** | Fixed gain throughout session | Prevents dynamic gain variations from confounding velocity and decay measurements. |

---

## 3. Microphone Positioning Configurations

Captures must evaluate three standardized microphone distances:

```
┌────────────────────────────────────────────────────────────────────────┐
│                    MICROPHONE POSITIONING MATRIX                       │
├────────────────────────────────┬───────────────────────────────────────┤
│ Position 1: CLOSE              │ • Distance: 0.3 – 0.5 meters           │
│ (Direct soundboard / rim)      │ • Angle: 45° over open lid / strings   │
│                                │ • High direct-to-reverberant ratio    │
├────────────────────────────────┼───────────────────────────────────────┤
│ Position 2: MEDIUM (PRACTICE)  │ • Distance: 0.8 – 1.2 meters           │
│ (Player Ear / Music Stand)     │ • Location: On music stand or laptop   │
│                                │ • Realistic HotChords practice position│
├────────────────────────────────┼───────────────────────────────────────┤
│ Position 3: AMBIENT / ROOM     │ • Distance: 2.5 – 3.5 meters           │
│ (Room corner / teaching space) │ • Location: Across the room            │
│                                │ • High room reverberation and decay   │
└────────────────────────────────┴───────────────────────────────────────┘
```

---

## 4. Acoustic Environment & Room Classifications

1. **Dry / Treated Room ($RT_{60} < 0.3\text{s}$)**:
   - Small bedroom or home studio with soft furnishings, rugs, and curtains. Minimal slapback echo.
2. **Normal Practice Room ($RT_{60} \approx 0.4 - 0.6\text{s}$)**:
   - Standard living room or music classroom with wood/tile floor, plaster walls, and moderate acoustic reflections.
3. **Reverberant Space ($RT_{60} > 0.8\text{s}$)**:
   - Untreated hall, church, or large high-ceiling room with prominent reverberation tails.

---

## 5. Piano Instrument Requirements

1. **Instrument Categories**:
   - **Acoustic Upright**: Standard 88-key vertical piano (e.g. Yamaha U1/U3, Kawai K-300, Baldwin).
   - **Acoustic Grand**: 88-key grand piano (e.g. Yamaha C3, Steinway Model B/M, Kawai GX-2).
   - **Digital Stage Piano with Acoustic Monitors**: High-grade weighted digital piano playing through external studio monitors into the room microphone (for controlled comparison).
2. **Tuning & Regulation**:
   - A4 reference pitch standard: $A4 = 440.0\text{ Hz} \pm 2\text{ cents}$.
   - Unison strings tuned to prevent excessive beating.
3. **Damper / Sustain Pedal State**:
   - Explicitly marked as **Pedal OFF** (clean damping on release) vs. **Pedal ON** (open string sympathetic resonance).

---

## 6. Performance Repertoire & Test Matrix

The recording session must systematically execute the following performance matrix:

### 6.1 Single Notes (Register Sweep)
- **Low Register (A0 – B2, MIDI 21–47)**: Evaluate low-frequency inharmonicity and slow decay.
- **Middle Register (C3 – B4, MIDI 48–71)**: Core fundamental range for triads and accompaniments.
- **High Register (C5 – C8, MIDI 72–108)**: High-frequency transient resolution with short decay.

### 6.2 Polyphonic Triads & Extended Chords
- **Major Triads**: Root position and inversions across C, G, D, A, E, F, Bb, Eb roots.
- **Minor Triads**: Root position and inversions across Am, Em, Dm, Bm, Fm, Cm roots.
- **Dominant & Major 7ths**: C7, G7, Fmaj7, Cmaj7, Bb7.
- **Minor 7ths & Half-Diminished**: Am7, Dm7, Em7, Bm7b5.
- **Extended Voicings (5–6 notes)**: Cmaj9, G13, F9, Dm11 (test upper partial clutter and overtone masking).

### 6.3 Harmonic Progressions & Loops
- **Standard 4-Chord Pop Progressions**:
  - $I - V - vi - IV$ ($C \rightarrow G \rightarrow Am \rightarrow F$)
  - $vi - IV - I - V$ ($Am \rightarrow F \rightarrow C \rightarrow G$)
  - $ii - V - I - IV$ ($Dm \rightarrow G \rightarrow C \rightarrow F$)
- **Transposed Variants**: In D Major, G Major, F Major, and A Minor.

### 6.4 Dynamic Range & Velocities
- **Pianissimo ($pp$)**: Velocity $\approx 25 - 40$. Tests low SNR and noise floor threshold.
- **Mezzo-Forte ($mf$)**: Velocity $\approx 60 - 80$. Standard practicing dynamic.
- **Fortissimo ($ff$)**: Velocity $\approx 100 - 120$. Tests clipping resistance and overtone surge.

### 6.5 Realistic Beginner-Style Imperfections
- **Flammed / Asynchronous Onsets**: Notes within a chord struck with $30\text{ms} - 80\text{ms}$ stagger.
- **Adjacent Ghost Notes**: Accidental soft grazing of an adjacent white or black key.
- **Hesitant / Slow Transitions**: Chords held past boundary or delayed by $200\text{ms} - 400\text{ms}$.
- **Uneven Finger Velocity**: One note in triad struck significantly louder than the other two.

---

## 7. Ground-Truth Data Logging Format

Every acoustic recording must be accompanied by an authoritative JSON ground-truth file:

```json
{
  "recordingId": "REC_2026_YAMAHA_U1_001",
  "audioFilename": "yamaha_u1_practice_c_major.wav",
  "audioHash": "e3b0c44298fc1c149afbf4c8996fb924",
  "pianoType": "ACOUSTIC_UPRIGHT",
  "micPosition": "MEDIUM_MUSIC_STAND",
  "roomCondition": "NORMAL_LIVING_ROOM",
  "pedalCondition": "NO_PEDAL",
  "velocityDynamic": "MF",
  "playerStyle": "CLEAN_PRACTICE",
  "durationSeconds": 16.5,
  "notes": [
    {
      "onset": 1.050,
      "offset": 2.850,
      "midi": 60,
      "pitchName": "C4",
      "velocity": 72
    },
    {
      "onset": 1.055,
      "offset": 2.850,
      "midi": 64,
      "pitchName": "E4",
      "velocity": 68
    },
    {
      "onset": 1.060,
      "offset": 2.845,
      "midi": 67,
      "pitchName": "G4",
      "velocity": 75
    }
  ],
  "chords": [
    {
      "start": 1.000,
      "end": 3.000,
      "chord": "C",
      "root": "C",
      "quality": "maj",
      "midi": [60, 64, 67]
    }
  ]
}
```

---

## 8. Summary Checklist for Recording Operators
1. [ ] Check microphone input level (ensure no clipping on loudest chord strike).
2. [ ] Record 5 seconds of room silence at start of session for background profiling.
3. [ ] Keep room silent of external speech, air conditioners, or television.
4. [ ] Strike chords cleanly and allow natural decay.
5. [ ] Log audio file and pair with synchronous MIDI capture or frame-by-frame DAW transcript.
