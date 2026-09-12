# HotChords Phase 14 Acoustic Failure Analysis & Error Taxonomy
**Detailed Physics, MIR Mechanics & Mitigation Strategies for Real-Piano Audio Detection**

---

## 1. Executive Summary
Detecting polyphonic notes played on a physical acoustic piano via a consumer microphone presents complex physical and acoustic challenges absent in synthetic tone tests. This document provides a rigorous mathematical and empirical breakdown of 14 key failure modes, their underlying physics, and how HotChords mitigates each error in its DSP pipeline.

---

## 2. Failure Mode Taxonomy & Physical Mechanics

```
┌────────────────────────────────────────────────────────────────────────┐
│               ACOUSTIC PIANO NOTE DETECTION FAILURE MODES              │
├──────────────────────────────────┬─────────────────────────────────────┤
│   SPECTRAL & HARMONIC FAILURES   │    ACOUSTIC & COUPLING FAILURES     │
├──────────────────────────────────┼─────────────────────────────────────┤
│ 1. Piano String Inharmonicity    │ 8. Sustain Pedal Resonance          │
│ 2. Harmonic Mistaken as $f_0$    │ 9. Room Reverberation & Decay Smear │
│ 3. Missing / Weak Fundamental    │ 10. Microphone Clipping & THD       │
│ 4. Octave Doubling / Halving     │ 11. Ambient Background Noise        │
│ 5. Shared Harmonic Overlap       │ 12. Transient Onset Jitter          │
│ 6. Loud-Note Masking             │ 13. Decay vs Release Flutter        │
│ 7. Dense Semitone Clusters       │ 14. Beginner Performance Stumbles   │
└──────────────────────────────────┴─────────────────────────────────────┘
```

---

### 2.1 Piano String Inharmonicity (Stiffness Factor $B$)
- **Physics**: Real acoustic piano strings have physical bending stiffness. As a consequence, higher partials deviate progressively sharp from exact integer multiples:
  $$f_n = n \cdot f_0 \sqrt{1 + B \cdot n^2}$$
  where $B \approx 0.0001\text{ to }0.0005$ in mid/high registers, and up to $B \approx 0.004$ in thick, short upright bass strings.
- **Symptom**: Partials $n=4, 5, 6$ lie $20\text{ to }45\text{ cents}$ higher than theoretical harmonics. Strict integer combs fail to match high partials.
- **HotChords Mitigation**: A calibrated $\pm 40\text{ cents}$ tolerance window and sub-bin parabolic peak interpolation accommodates $B$-coefficient stretching without missing partial energy.

---

### 2.2 Harmonic Mistaken as Fundamental (Overtone Confusion)
- **Physics**: When C4 ($261.63\text{ Hz}$) is struck, its 2nd harmonic ($523.25\text{ Hz} \approx \text{C5}$) and 3rd harmonic ($784.89\text{ Hz} \approx \text{G5}$) can contain high energy. A naive pitch detector detects 3 notes: C4, C5, and G5.
- **Symptom**: False positive notes detected an octave, 12th, or 15th above the played note.
- **HotChords Mitigation**: Overtone cancellation logic checks semitone intervals $12, 19, 24, 28$ above confirmed lower fundamentals; candidate notes whose salience is $\le 95\%$ of the underlying fundamental's overtone series are suppressed.

---

### 2.3 Missing Fundamental in Small Upright Pianos
- **Physics**: Low bass strings (A0–C2, $27.5\text{ Hz} - 65.4\text{ Hz}$) on upright pianos have small soundboards incapable of efficiently radiating long acoustic wavelengths. The fundamental $f_0$ may be $-18\text{ dB}$ weaker than the 2nd and 3rd partials ($2f_0, 3f_0$).
- **Symptom**: Low bass notes missed or detected as an octave higher.
- **HotChords Mitigation**: Harmonic comb salience calculates composite energy across 5 harmonics $[1.0, 0.65, 0.45, 0.30, 0.20]$, enabling fundamental inference from strong coherent upper partial pairs even if $f_0$ is weak.

---

### 2.4 Octave Doubling / Subharmonic Spurious Notes
- **Physics**: Subharmonics ($f_0 / 2$) can appear to have all their even harmonics match the real note's spectrum.
- **Symptom**: Playing C4 triggers a spurious detection of C3.
- **HotChords Mitigation**: **Fundamental Peak Requirement ($h_1 \ge 0.18$)**. Subharmonics whose putative fundamental has zero physical energy in the spectrum are immediately rejected.

---

### 2.5 Shared Harmonic Overlap in Consonant Chords (Root-Fifth Voicings)
- **Physics**: In a C Major triad (C4, E4, G4), the 3rd harmonic of C4 ($784.89\text{ Hz}$) perfectly coincides with the 2nd harmonic of G4 ($784.00\text{ Hz}$).
- **Symptom**: One of the two notes is starved of harmonic salience or flagged as a redundant overtone.
- **HotChords Mitigation**: Each pitch candidate's fundamental peak ($h=1$) is verified independently prior to overtone suppression, preventing independent notes from being wrongly pruned.

---

### 2.6 Loud-Note Masking in High-Velocity Strikes
- **Physics**: If the thumb strikes a bass note fortissimo ($ff$) while the pinky plays a soft melody note pianissimo ($pp$), the bass note's spectral energy can be $+20\text{ dB}$ higher, submerging the soft note below peak thresholds.
- **Symptom**: Drop of quiet inner notes in polyphonic chords.
- **HotChords Mitigation**: Dynamic logarithmic peak thresholding ($0.08$ normalized to maximum local spectral energy) captures secondary peaks within a $22\text{ dB}$ dynamic window.

---

### 2.7 Dense Semitone Clusters & Dissonance
- **Physics**: Minor 2nd intervals (e.g. B3 and C4, separation $15.5\text{ Hz}$) cause acoustic phase beating at $\Delta f$ rate.
- **Symptom**: Beating amplitude oscillations cause frame-to-frame magnitude flutter.
- **HotChords Mitigation**: Temporal hysteresis tracking ($2\text{ frames}$ note-on confirmation, $3\text{ frames}$ release) bridges instantaneous beat nulls.

---

### 2.8 Sustain / Damper Pedal Sympathetic String Resonance
- **Physics**: When the sustain pedal is held down, all 88 string dampers are lifted. Striking a chord excites sympathetic vibrations across undamped related strings throughout the soundboard.
- **Symptom**: "Ghost" harmonically related notes linger after fingers release the keys.
- **HotChords Mitigation**: Practice feedback grace windows ($\pm 250\text{ms}$) and pitch-class matching evaluate active musical alignment without penalizing natural soundboard reverberation.

---

### 2.9 Room Reverberation & Decay Smearing
- **Physics**: In reverberant rooms ($RT_{60} > 0.8\text{s}$), early reflections and diffuse reverberation smear transient energy across several hundred milliseconds.
- **Symptom**: Delayed note-off detection; notes appear sustained across chord changes.
- **HotChords Mitigation**: Wiener spectral flatness filtering rejects diffuse unvoiced reverberation energy while tracking sharp harmonic decay.

---

### 2.10 Preamp Digital Clipping & Intermodulation Distortion
- **Physics**: Excessively high microphone gain causes waveform flat-topping at $\pm 1.0$, creating odd harmonic distortion spikes ($3f, 5f, 7f, 9f$).
- **Symptom**: Spurious high-register note detections.
- **HotChords Mitigation**: Phase 12 input calibration detects clipping ratio ($>2\%$ clipped samples) and flags `SignalQualityState.CLIPPING`, instructing the user to reduce mic input gain.

---

### 2.11 Ambient Room Noise (HVAC, Fans, Street Traffic)
- **Physics**: Broadband fan noise or HVAC rumble raises the acoustic noise floor.
- **Symptom**: False triggers or failure to detect quiet practice notes.
- **HotChords Mitigation**: Dynamic noise gate calculated as $\text{Gate}_{\text{RMS}} = \max(2.2 \times \text{RMS}_{\text{floor}}, 1.3 \times \text{RMS}_{p90})$. Frames below gate are rejected as `NO_INPUT`.

---

### 2.12 Beginner Performance Anomalies (Flammed Chords & Hesitations)
- **Physics**: Inexperienced players rarely strike all 3 or 4 notes of a chord with sub-millisecond synchrony; fingers land with $30\text{ms} - 80\text{ms}$ stagger.
- **Symptom**: Strict frame-instant evaluators mark the chord as "wrong" during the $50\text{ms}$ landing window.
- **HotChords Mitigation**: Practice feedback transition phase ($\pm 250\text{ms}$) accumulates notes across landing window before grading chord accuracy.

---

## 3. Summary
This failure analysis directly guides the evaluation engine metrics, ensuring error reporting separates acoustic physical limitations from algorithmic software regressions.
