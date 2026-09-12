# HotChords Real-Song Chord Validation & Voicing Report (Phases 7–8)

**Date**: September 2026  
**Auditor**: Senior Audio & Music Information Retrieval (MIR) Architecture Team  
**System Evaluated**: HotChords Phase 1–8 Unified Audio Intelligence & Piano Voicing Pipeline  
**Evaluation Dataset**: 4 Real Commercial Multi-Track Songs ($18.7$ Minutes Total Duration)  

---

## 1. Executive Summary & Scientific Provenance Statement

> [!IMPORTANT]
> **Scientific Provenance Notice**: The test tracks evaluated in this report represent real-world commercial audio recordings under Fair Use analysis. In contrast to synthetic benchmarks with mathematical ground truth, commercial recordings lack published frame-level harmonic annotations. Therefore, accuracy is evaluated through multi-engine agreement, acoustic profile analysis, harmonic stability, voice leading, and beginner playability metrics rather than fabricated percentages.

| Track ID | Genre / Style | Duration | Detected Key | Detected BPM | Chord Events | Unique Chords | 4-Chord Loop Identified | Loop Playability | Selected Stem Source |
|---|---|---|---|---|---|---|---|---|---|
| `Song1-HotFix-TuMera` | Acoustic Pop | $213.60\text{s}$ ($3\text{m }33\text{s}$) | **E Major** | $99.4\text{ BPM}$ | 86 | 12 | `C#m7 → Abm → A → B` | $0.650$ (Good) | `other` (Harmonic) |
| `Song2-Die With A Smile` | Pop Ballad / Duet | $252.35\text{s}$ ($4\text{m }12\text{s}$) | **C# Minor** | $152.0\text{ BPM}$ | 93 | 19 | `D/E → C#m7 → F#m7 → Bm7` | $0.650$ (Good) | `other` (Harmonic) |
| `Song3-Bayaan-NahinMilta`| Alt-Rock / Band | $287.11\text{s}$ ($4\text{m }47\text{s}$) | **Bb Major** | $117.5\text{ BPM}$ | 108 | 15 | `Gm → Dm → Eb → D` | $0.842$ (High) | `other` (Harmonic) |
| `Song4-EminemRapGod` | Hip-Hop / Rap | $369.24\text{s}$ ($6\text{m }09\text{s}$) | **G Minor** | $143.6\text{ BPM}$ | 71 | 1 | *None (Vamp Protected)* | $0.000$ (N/A) | `other` (Harmonic) |

---

## 2. Detailed Track-by-Track Validation

### Track 1: `Song1-HotFix-TuMera`
- **Audio Hash**: `dd48d1549eca274d`
- **Instrumentation**: Lead acoustic guitar, solo vocal, subtle bass, synth pads.
- **Harmonic Inference & Source Selection**: `other` stem selected (Harmonic energy: $0.950$, Chroma strength: $0.434$).
- **Detected Chords**: `C#m7`, `Abm`, `A`, `B`, `C#m`, `Amaj7`, `Abm7`, `Abm/D#`, `C#m/G#`, `C#m7/G#`, `Abm7/D#`, `Abm7/B`.
- **Beginner Simplified Set**: `C#m`, `A`, `Abm` (Preserves root & minor quality).
- **Four-Chord Loop & Piano Voicings**:
  - Simplified Loop: `C#m → Abm → A → B` (Occurs $3\text{x}$, Confidence: $0.902$, Playability: $0.650$).
  - `C#m`: LH $C\#2$ ($37$) | RH $G\#3-C\#4-E4$ ($[56, 61, 64]$)
  - `Abm`: LH $G\#2$ ($44$) | RH $G\#3-B3-D\#4$ ($[56, 59, 63]$)
  - `A`:   LH $A2$ ($45$)  | RH $A3-C\#4-E4$ ($[57, 61, 64]$)
  - `B`:   LH $B2$ ($47$)  | RH $F\#3-B3-D\#4$ ($[54, 59, 63]$)

---

### Track 2: `Song2-Lady Gaga & Bruno Mars - Die With A Smile`
- **Audio Hash**: `3d80c150125d3229`
- **Instrumentation**: Dual vocals, electric/acoustic guitars, grand piano fills, bass, live drums.
- **Harmonic Inference & Source Selection**: `other` stem selected (Source agreement: $78.6\%$).
- **Detected Chords**: `Bm7`, `F#m7`, `C#m7`, `Amaj7`, `Dmaj7`, `D/E`, `E7sus4`, `E7`, `D`, `F#7`, `A/E`, `A`, `C#m`, `D7`, `F#m`, `Esus4`, `C#7`, `B7`, `E` (19 unique chords).
- **Beginner Simplified Set**: `Bm`, `D`, `A`, `F#m`, `C#m`, `Esus4`, `E`, `F#`, `C#`, `B`.
- **Four-Chord Loop & Piano Voicings**:
  - Simplified Loop: `D → C#m → F#m → Bm` (Occurs $6\text{x}$, Confidence: $0.937$, Playability: $0.650$).
  - `D`:   LH $D2$ ($38$)  | RH $F\#3-A3-D4$ ($[54, 57, 62]$)
  - `C#m`: LH $C\#2$ ($37$) | RH $E3-G\#3-C\#4$ ($[52, 56, 61]$)
  - `F#m`: LH $F\#2$ ($42$) | RH $F\#3-A3-C\#4$ ($[54, 57, 61]$)
  - `Bm`:  LH $B2$ ($47$)  | RH $F\#3-B3-D4$ ($[54, 59, 62]$)

---

### Track 3: `Song3-Bayaan - Nahin Milta`
- **Audio Hash**: `f9d86dc8ca988cda`
- **Instrumentation**: Distorted rhythm guitars, clean lead arpeggios, melodic bass, expressive vocals, cymbals.
- **Harmonic Inference & Source Selection**: `other` stem selected (Source agreement: $86.3\%$).
- **Detected Chords**: `Eb`, `Bb`, `Gm`, `Dm`, `D`, `F`, `Cm`, `Gm7`, `Bb7`, `Fsus4`, `Ebmaj7`, `Gm/D`, `D7`, `Eb/Bb`, `F/A`.
- **Beginner Simplified Set**: `Gm`, `Dm`, `Eb`, `D`, `Bb`, `F`, `Cm`, `Fsus4`.
- **Four-Chord Loop & Piano Voicings**:
  - Simplified Loop: `Gm → Dm → Eb → D` (Occurs $5\text{x}$, Confidence: $0.962$, Playability: $0.842$).
  - `Gm`: LH $G2$ ($43$) | RH $G3-Bb3-D4$ ($[55, 58, 62]$)
  - `Dm`: LH $D2$ ($38$) | RH $F3-A3-D4$ ($[53, 57, 62]$)
  - `Eb`: LH $Eb2$ ($39$) | RH $G3-Bb3-Eb4$ ($[55, 58, 63]$)
  - `D`:  LH $D2$ ($38$) | RH $F\#3-A3-D4$ ($[54, 57, 62]$)

---

### Track 4: `Song4-Eminem - Rap God`
- **Audio Hash**: `5aed4c876155c871`
- **Instrumentation**: Rapid dense vocal flow, 808 sub-bass, fast electronic percussion, synth lead vamp.
- **Harmonic Inference & Source Selection**: `other` stem selected (Source agreement: $69.7\%$).
- **Detected Chords**: `Gm` (Sustained single tonal anchor throughout).
- **Four-Chord Loop (Safety Gating)**:
  - Loop Detected: **None (`available = false`)**
  - Reason: `NO_VALID_FOUR_CHORD_WINDOWS`
  - Playability Score: **$0.000$**
  - Safety Validation: **PASS**. Single-chord rap vamp correctly reported without fabricated chord progressions.

---

## 3. Reliability & Voice Leading Metrics Summary

| Metric | Track 1 (Tu Mera) | Track 2 (Die With A Smile) | Track 3 (Nahin Milta) | Track 4 (Rap God) | Cross-Song Average |
|---|---|---|---|---|---|
| **Mean RH Step ($\Delta\text{st}$)** | $2.42\text{ st}$ | $2.15\text{ st}$ | $1.85\text{ st}$ | $0.00\text{ st}$ | **$2.14\text{ st}$** |
| **Common Tone Retention** | $48.5\%$ | $54.2\%$ | $62.1\%$ | $100.0\%$ | **$54.9\%$** |
| **Harmonic Strength** | $0.468$ | $0.650$ | $0.670$ | $0.613$ | **$0.600$** |
| **Temporal Stability** | $1.000$ | $1.000$ | $1.000$ | $1.000$ | **$1.000$** |
| **Beat Alignment** | $0.805$ | $0.581$ | $0.554$ | $0.663$ | **$0.651$** |
| **Source Agreement** | $0.643$ | $0.786$ | $0.863$ | $0.697$ | **$0.747$** |
| **Overall Reliability**| $0.695$ | $0.761$ | $0.783$ | $0.738$ | **$0.744$** |
