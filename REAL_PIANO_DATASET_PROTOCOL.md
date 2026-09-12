# Real-Piano Ground Truth Dataset & Evaluation Protocol (Phase 12)

## 1. Overview & Strict Honesty Disclosure

### Strict Disclosure:
- **Current Ground Truth Status**: `REAL_PIANO_GROUND_TRUTH = NOT_AVAILABLE`.
- HotChords has validated its DSP algorithms on deterministic synthetic mixtures and simulated practice streams.
- In accordance with rigorous scientific and audio engineering standards, HotChords **DOES NOT** claim verified real-world acoustic microphone accuracy until an annotated acoustic dataset recorded under this protocol is evaluated.

---

## 2. Dataset Collection & Recording Protocol

To establish true acoustic accuracy, ground truth MUST be captured via direct hardware synchronization (MIDI key sensors / optical key sensors) rather than subjective human annotation.

### Acoustic Recording Specifications:
1. **Instruments**:
   - Upright Acoustic Piano (e.g. Yamaha U1 / Kawai K-300)
   - Grand Acoustic Piano (e.g. Steinway Model B / Yamaha C7)
   - Weighted Digital Stage Piano (line-in + acoustic speaker emission)
2. **Microphone Configurations**:
   - `MIC_LAPTOP`: Integrated laptop microphone ($50\text{ cm}$ distance, off-axis).
   - `MIC_HEADSET`: Omnidirectional condenser headset mic.
   - `MIC_DESKTOP`: Studio cardioid condenser ($1\text{ m}$ distance at piano music stand).
3. **Room Acoustic Profiles**:
   - Dry Bedroom / Office ($RT_{60} \approx 0.2\text{s}$)
   - Living Room / Practice Studio ($RT_{60} \approx 0.5\text{s}$)
   - High Reverberation Hall ($RT_{60} \approx 1.2\text{s}$)

---

## 3. Ground Truth Dataset Schema

Lightweight, anonymous JSON ground truth schema without personally identifying information:
```json
{
  "$schema": "https://hotchords.app/schemas/dataset/v1/piano_ground_truth.json",
  "sessionId": "rec_20260912_upright_dry_01",
  "instrument": {
    "type": "acoustic_upright",
    "model": "Yamaha U1",
    "tuningHz": 440.0
  },
  "recording": {
    "microphone": "Built-in MacBook Pro 16",
    "distanceMeters": 0.6,
    "roomRt60Seconds": 0.35,
    "sampleRate": 44100,
    "bitDepth": 24
  },
  "groundTruthEvents": [
    {
      "timestamp": 1.240,
      "eventType": "NOTE_ON",
      "midiNotes": [60, 64, 67],
      "chordSymbol": "C",
      "velocities": [78, 82, 80],
      "damperPedal": false
    },
    {
      "timestamp": 2.890,
      "eventType": "NOTE_OFF",
      "midiNotes": [60, 64, 67],
      "damperPedal": false
    }
  ]
}
```

---

## 4. Evaluation Metrics for Real-World Validation

When the real-world dataset is gathered, the evaluation harness will compute:
1. **Note-Level Metrics**:
   - Precision, Recall, F1 across pitch classes and exact octaves.
2. **Onset Timing Error**:
   $$\Delta t_{\text{onset}} = t_{\text{detected}} - t_{\text{ground\_truth\_midi}}$$
3. **Polyphonic Chord Accuracy**:
   Percentage of chords where all constituent notes match with zero extraneous notes.
4. **False Positive Rate / False Negative Rate**:
   Spurious note triggers per minute of audio.
5. **Confidence Calibration**:
   Expected Calibration Error (ECE) and Brier Score plotted on reliability curves.
