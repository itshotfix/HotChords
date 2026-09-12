# Real-Time Piano Note Detection Specification (Phase 11)

## 1. Overview & Architectural Principles

HotChords Phase 11 introduces an in-browser and backend real-time DSP note detection layer designed for acoustic and digital piano practice observation.

### Core Architectural Invariants:
1. **Observation Layer Only**: Microphone input NEVER mutates `SongTimeline`, `ChordEvent`, detected harmony, practice loops, original BPM, or canonical timing.
2. **Local-First & Transient**: All audio processing occurs in memory in real time. No `.wav`, `.mp3`, or raw audio files are written to disk, and no audio is transmitted across the network or uploaded to cloud services.
3. **Immediate Hardware Release**: All `MediaStreamTrack`s are explicitly terminated (`track.stop()`) the moment input is deactivated.
4. **Single Shared AudioContext**: Connects to the existing `AudioContext` managed by `PianoPlaybackService`, avoiding redundant contexts or competing browser clocks.

---

## 2. Signal Path & Processing Pipeline

```
Microphone / Test Signal
        ↓
MediaStreamSourceNode / Synthetic Buffer
        ↓
Web Audio AnalyserNode (N = 4096, Blackman-Harris window)
        ↓
RMS Energy & Wiener Entropy (Spectral Flatness) QC Gating
        ↓
Sub-Bin Parabolic Peak Interpolation
        ↓
Harmonic Comb Salience & Fundamental Candidate Scoring
        ↓
Integer Overtone Suppression (2*f0, 3*f0, 4*f0, 5*f0)
        ↓
Temporal Hysteresis Buffer (Note-On >= 2 frames, Note-Off >= 3 frames)
        ↓
Sorted Deterministic Polyphonic Note Set Output:
{
  "notes": [
    {"midi": 60, "noteName": "C4", "frequency": 261.63, "confidence": 0.91},
    {"midi": 64, "noteName": "E4", "frequency": 329.63, "confidence": 0.88},
    {"midi": 67, "noteName": "G4", "frequency": 392.00, "confidence": 0.85}
  ],
  "confidence": 0.88,
  "polyphonyType": "POLYPHONIC"
}
```

---

## 3. DSP Configuration & Mathematical Formulation

### FFT & Frame Parameters:
- **Sample Rate ($f_s$)**: $22,050\text{ Hz}$ / $44,100\text{ Hz}$ / $48,000\text{ Hz}$.
- **FFT Size ($N$)**: $4096$ samples (provides bin resolution $\Delta f \approx 5.38\text{ Hz}$ at $22,050\text{ Hz}$ and $10.76\text{ Hz}$ at $44,100\text{ Hz}$).
- **Hop Size ($H$)**: $512$ samples ($\sim 23.2\text{ ms}$ at $22,050\text{ Hz}$ / $11.6\text{ ms}$ at $44,100\text{ Hz}$).
- **Target Frequency Range**: Piano $A_0 (27.5\text{ Hz}, \text{MIDI } 21)$ to $C_8 (4186.0\text{ Hz}, \text{MIDI } 108)$.
- **Window**: Blackman-Harris window (suppresses side-lobe spectral leakage below $-92\text{ dB}$).

### Sub-Bin Peak Interpolation:
Given a local spectral magnitude peak at bin index $k$:
$$\delta = \frac{1}{2} \cdot \frac{\alpha - \gamma}{\alpha - 2\beta + \gamma}$$
$$f_{\text{interp}} = (k + \delta) \cdot \Delta f$$
where $\alpha = |X[k-1]|$, $\beta = |X[k]|$, $\gamma = |X[k+1]|$.

### Inharmonic Noise Rejection (Spectral Flatness / Wiener Entropy):
$$\text{SFM} = \frac{\exp\left(\frac{1}{M}\sum_{m=1}^M \ln |X[m]|^2\right)}{\frac{1}{M}\sum_{m=1}^M |X[m]|^2}$$
Signals with $\text{SFM} > 0.12$ are flagged as noise/inharmonic and routed to `LOW_CONFIDENCE` with 0 false notes.

### Harmonic Comb Salience & Fundamental Likelihood:
For candidate fundamental $f_0$, salience is computed across the first 5 harmonics with weights $w = [1.0, 0.65, 0.45, 0.30, 0.20]$:
$$S(f_0) = \sum_{h=1}^5 w_h \cdot |X(h \cdot f_0)|$$
**Fundamental Requirement**: A candidate $f_0$ must possess significant energy at its actual fundamental $h=1$ ($|X(f_0)| \ge 0.18$). Subharmonics lacking $h=1$ energy are strictly rejected.

### Integer Overtone Suppression:
For any active fundamental $f_0$, higher candidate notes at octave ($2f_0$, $+12\text{ semitones}$), octave+fifth ($3f_0$, $+19\text{ semitones}$), two octaves ($4f_0$, $+24\text{ semitones}$), and two octaves+major third ($5f_0$, $+28\text{ semitones}$) are suppressed if their individual salience does not significantly exceed the fundamental's overtone decay envelope.

---

## 4. Temporal Stabilization (Hysteresis)

To eliminate single-frame dropouts, acoustic reverberation flutter, and transient noise:
- **`NOTE_ON` Confirmation Threshold**: Requires note presence across $\ge 2$ consecutive frames ($\approx 46\text{ ms}$).
- **`NOTE_OFF` Release Threshold**: Requires note absence across $\ge 3$ consecutive frames ($\approx 70\text{ ms}$).

---

## 5. Input Modes & Browser Compatibility

| Input Mode | Support Status | Notes |
| :--- | :--- | :--- |
| `MICROPHONE` | Supported on all modern browsers (Chrome, Safari, Firefox, Edge) | Uses `navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false } })`. |
| `TEST_SIGNAL` | Universal / Offline | Deterministic synthetic piano generator for automated QA, CI/CD, and regression suites. |
| `SYSTEM_AUDIO` | Browser-Restricted | Standard web browsers do not permit arbitrary system audio loopback without screen sharing / tab-capture prompts. Handled cleanly with `INPUT_UNSUPPORTED` when native loopback is unavailable. |

---

## 6. Privacy & Security Assurance

1. **Zero External API**: 100% of the DSP executes locally on the user's CPU via Web Audio / NumPy.
2. **Zero Persistent Storage**: No microphone buffers are recorded to `.wav`, indexed in SQLite/IndexedDB, or written to temp folders.
3. **Deterministic Teardown**: Invoking `RealtimeInputService.stop()` calls `track.stop()` on all active media tracks.
