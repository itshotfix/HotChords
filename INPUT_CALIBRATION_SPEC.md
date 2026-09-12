# Input Calibration & Signal Quality Specification (Phase 12)

## 1. Overview & Architectural Principles

HotChords Phase 12 introduces a transient, local-first audio input calibration and signal quality classification engine. It dynamically models room acoustics and ambient noise levels to adaptively calibrate detection thresholds, ensuring robust real-time performance across diverse microphones, rooms, and piano instruments.

### Key Guarantees:
1. **Zero Audio Recording**: Calibration frames are processed in memory and discarded. Zero audio files (`.wav`, `.mp3`, `.raw`) are written to disk or transmitted to external services.
2. **Metadata-Only Profile**: Calibration results are stored strictly as safe JSON metadata (`PracticeInputProfile`).
3. **No Hardware Gain Manipulation**: Does not attempt hazardous or unsupported operating system / browser microphone gain modification; dynamic normalization and gates operate entirely in digital DSP space.
4. **Non-Destructive Observation**: Calibration never modifies `SongTimeline`, `ChordEvent`, detected harmony, or canonical BPM.

---

## 2. Noise Floor Estimation & Dynamic Gate Derivation

### Mathematical Formulation:
During the calibration window (typically $1.0$–$2.0\text{ seconds}$, evaluating $\sim 50$–$100\text{ frames}$):
1. **Median Ambient RMS**:
   $$\text{RMS}_{\text{ambient}} = \text{median}\left(\{\text{RMS}_1, \text{RMS}_2, \dots, \text{RMS}_K\}\right)$$
2. **90th Percentile Peak Noise**:
   $$\text{RMS}_{p90} = \text{percentile}_{90}\left(\{\text{RMS}_k\}\right)$$
3. **Dynamic Noise Gate**:
   $$\text{Gate}_{\text{RMS}} = \text{clamp}\left(0.004, 0.08, \max\left(2.2 \times \text{RMS}_{\text{ambient}}, 1.3 \times \text{RMS}_{p90}\right)\right)$$
4. **Dynamic Range ($DR_{\text{dB}}$)**:
   $$DR_{\text{dB}} = 20 \cdot \log_{10}\left(\frac{\max(1.0, \text{Peak})}{\text{RMS}_{\text{ambient}}}\right)$$

---

## 3. Signal Quality States

The real-time classifier categorizes each incoming frame into one of 7 mutually exclusive states:

| Quality State | Acoustic Condition | Classification Trigger | Playable Flag | Action / Meaning |
| :--- | :--- | :--- | :--- | :--- |
| `CALIBRATING` | Calibration active | Calibration duration elapsed $< 100\%$ | `False` | Measuring ambient noise floor. |
| `READY` | Calibrated & awaiting audio | RMS $\le \text{RMS}_{\text{ambient}}$ | `False` | Ready for piano key strikes. |
| `GOOD_SIGNAL` | Clean piano chord | $\text{RMS} \ge \text{Gate}_{\text{RMS}}$, $\text{SFM} \le 0.12$, Peak $< 0.98$ | `True` | Harmonic tone clearly above noise gate. |
| `WEAK_SIGNAL` | Quiet / distant piano strike | $\text{RMS}_{\text{ambient}} < \text{RMS} < \text{Gate}_{\text{RMS}}$ | `False` | Suggest playing firmer or moving closer. |
| `NOISE` | Room fan / speech / clapping | $\text{SFM} > 0.18$ (Wiener entropy) and $\text{RMS} > \text{Gate}_{\text{RMS}}$ | `False` | Inharmonic acoustic disturbance. |
| `CLIPPING` | Overloaded microphone input | Peak $\ge 0.98$ or Clip Ratio $\ge 0.02$ | `False` | Reduce microphone input volume. |
| `LOW_CONFIDENCE` | Borderline / unsteady signal | Indeterminate SNR | `False` | Low acoustic certainty. |

---

## 4. Calibration Lifecycle & API

### JavaScript Client (`InputCalibrationService`):
```javascript
// Start calibration
window.InputCalibrationService.startCalibration(window.RealtimeInputService, 2000);

// Subscribe to progress & completion
window.InputCalibrationService.subscribe((event) => {
    if (event.type === 'CALIBRATION_COMPLETE') {
        console.log('Calibrated noise gate:', event.profile.noiseGateRms);
    }
});
```

### Python Backend (`InputCalibrator`):
```python
calibrator = InputCalibrator(sample_rate=22050)
calibrator.start_calibration(duration_seconds=2.0)
for frame in ambient_audio_frames:
    calibrator.process_calibration_frame(frame)
profile = calibrator.finish_calibration()
```
