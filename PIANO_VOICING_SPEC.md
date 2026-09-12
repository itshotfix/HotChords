# HotChords Piano Voicing & Voice-Leading Specification (Phase 8)

**Date**: September 2026  
**Module**: `backend/theory/piano_voicing.py`  
**Architecture Role**: Musical Intelligence Layer (Converts detected chords into playable, ergonomic piano voicings)  

---

## 1. Core Architectural Principle

In HotChords:
- **Audio / MIR Engine** decides *WHAT THE CHORD IS* (acoustics, chroma, root pitch classes, extensions).
- **Music Theory Engine** decides *WHAT THE CHORD MEANS* (canonical root, harmonic quality, diatonic function, beginner simplification).
- **Piano Voicing Engine** decides *HOW THE BEGINNER PLAYS IT* (register placement, voice leading, finger assignment, hand distribution).
- **PlaybackClock** decides *WHEN IT PLAYS* (authoritative continuous time synchronization).

These four layers are strictly decoupled. The piano voicing engine contains **zero machine learning** and executes with sub-millisecond CPU performance.

---

## 2. Register Boundaries & Range Constraints

To ensure audio clarity and avoid acoustic muddiness or high-register shrillness:

| Register Zone | MIDI Note Range | Pitch Range | Purpose / Musical Assignment |
|---|---|---|---|
| **Left Hand (Bass Anchor)** | **$36 - 55$** | $C2 - G3$ | Root or slash-chord bass note ($f_0$ foundation). |
| **Right Hand (Harmonic Core)** | **$55 - 79$** | $G3 - G5$ | 3-note or 4-note triads, inversions, and extensions. |
| **Right Hand Target Center** | **$64 \pm 4$** | $E4 \pm 4\text{ st}$ | Center anchor near Middle C ($C4 = 60$). |

---

## 3. Voice-Leading Cost Minimization Algorithm

For any transition between consecutive chords $A \to B$, the engine evaluates all valid inversions and octave placements of chord $B$ and selects the voicing that minimizes total voice-leading displacement:

$$\text{Cost}(P, C) = \sum_{j=1}^{m} \min_{i} |c_j - p_i| + \lambda_{\text{center}} |\bar{C} - 64| + \lambda_{\text{span}} \max(0, \text{span}(C) - 12) - \lambda_{\text{common}} |P \cap C|$$

Where:
- $P$: Previous chord right-hand MIDI notes.
- $C$: Candidate next chord right-hand MIDI notes.
- $\lambda_{\text{center}} = 0.25$: Penalizes register drift away from middle keyboard.
- $\lambda_{\text{span}} = 1.50$: Penalizes wide hand spans exceeding an octave ($> 12\text{ semitones}$).
- $\lambda_{\text{common}} = 3.00$: Rewards retaining shared common tones in the same physical voice.

### Cyclic 4-Chord Loop Optimization
For four-chord loops ($C \to G \to \text{Am} \to F$), the engine executes a circular voice-leading pass such that Chord 4 ($F$) transitions seamlessly back into Chord 1 ($C$) with minimal hand movement ($\le 4\text{ semitones}$).

---

## 4. Hand Assignment & Finger Color Map

### Left Hand
- **Bass Root or Slash Inversion**: Single solid root note in Octave 2/3 (or power 5th).
- **Default Finger**: 5 (Pinky) for bass foundation.

### Right Hand
- **Standard Triads (Root Position)**: Fingers $[1, 3, 5]$ (Thumb, Middle, Pinky).
- **1st Inversion Triads (e.g. $E-G-C$)**: Fingers $[1, 2, 5]$ (Thumb, Index, Pinky).
- **2nd Inversion Triads (e.g. $G-C-E$)**: Fingers $[1, 3, 5]$ (Thumb, Middle, Pinky).
- **4-Note 7th Chords**: Fingers $[1, 2, 3, 5]$.

### Visual UI Finger Color Coding:
- **Finger 1 (Thumb)**: `#FF4D4F` (Red)
- **Finger 2 (Index)**: `#FAAD14` (Orange/Yellow)
- **Finger 3 (Middle)**: `#52C41A` (Green)
- **Finger 4 (Ring)**: `#13C2C2` (Cyan)
- **Finger 5 (Pinky)**: `#1677FF` (Blue)

---

## 5. Supported Chord Voicing Vocabulary

| Harmonic Quality | Intervals (Semitones) | Example Input | Beginner Right Hand Voicing | Left Hand Bass |
|---|---|---|---|---|
| **Major Triad** | $[0, 4, 7]$ | `C` | `C4 - E4 - G4` ($[60, 64, 67]$) | `C2` ($36$) |
| **Minor Triad** | $[0, 3, 7]$ | `Am` | `A3 - C4 - E4` ($[57, 60, 64]$) | `A2` ($45$) |
| **Dominant 7th** | $[0, 4, 7, 10]$ | `G7` | `G3 - B3 - D4 - F4` ($[55, 59, 62, 65]$) | `G2` ($43$) |
| **Major 7th** | $[0, 4, 7, 11]$ | `Cmaj7` | `C4 - E4 - G4 - B4` ($[60, 64, 67, 71]$) | `C2` ($36$) |
| **Minor 7th** | $[0, 3, 7, 10]$ | `Dm7` | `D4 - F4 - A4 - C5` ($[62, 65, 69, 72]$) | `D2` ($38$) |
| **Suspended 2nd** | $[0, 2, 7]$ | `Csus2` | `C4 - D4 - G4` ($[60, 62, 67]$) | `C2` ($36$) |
| **Suspended 4th** | $[0, 5, 7]$ | `Gsus4` | `G3 - C4 - D4` ($[55, 60, 62]$) | `G2` ($43$) |
| **Diminished** | $[0, 3, 6]$ | `Bdim` | `B3 - D4 - F4` ($[59, 62, 65]$) | `B2` ($47$) |
| **Augmented** | $[0, 4, 8]$ | `Caug` | `C4 - E4 - G#4` ($[60, 64, 68]$) | `C2` ($36$) |
| **Slash Chord** | Triad on Bass | `C/E` | `G3 - C4 - E4` ($[55, 60, 64]$) | `E2` ($40$) |
| **Slash Chord** | Triad on Bass | `D/F#` | `A3 - D4 - F#4` ($[57, 62, 66]$) | `F#2` ($42$) |
