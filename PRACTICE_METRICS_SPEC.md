# Practice Metrics, Mastery & Targeted Pedagogy Specification (Phase 12)

## 1. Objective Metric Philosophy

HotChords Phase 12 strictly avoids collapsing practice feedback into a single subjective "Player Accuracy = 94%" score. Instead, it exposes granular, objective mathematical components:
- `notePrecision`: $\frac{|C|}{|C| + |X|}$ (penalizes extraneous/adjacent struck keys)
- `noteRecall`: $\frac{|C|}{|E|}$ (measures completeness of chord tones)
- `noteF1`: Harmonic mean of precision and recall
- `averageTimingOffsetMs` & `medianTimingOffsetMs`: Temporal anticipation/lag (ms)
- `chordsAttempted`, `chordsMatched`, `chordsPartial`, `chordsMissed`

---

## 2. Structured Player Feedback Events

Discrete feedback events emitted into the bounded memory ring buffer:

| Event Type | Trigger Condition | Payload Data |
| :--- | :--- | :--- |
| `CHORD_READY` | Chord approached within grace window | `timestamp`, `chordName`, `expectedMidi` |
| `CHORD_MATCHED` | Full target chord struck ($\text{Recall} \ge 0.80$, $\text{Precision} \ge 0.70$) | `timingOffsetMs`, `noteRecall`, `notePrecision`, `noteF1` |
| `CHORD_PARTIAL` | Incomplete chord struck ($\text{Recall} \ge 0.50$) | `missingNotes`, `correctNotes` |
| `CHORD_MISSED` | Chord duration ended with zero match | `missCount`, `duration` |
| `WRONG_NOTES` | Conflicting audible notes detected | `extraNotes`, `detectedMidi` |
| `NO_INPUT` | Zero audio energy detected during active chord | `rms`, `noiseGate` |
| `LOW_CONFIDENCE`| Unsteady or noisy acoustic signal | `confidence` |
| `INPUT_PROBLEM` | Digital clipping or permission failure | `errorReason` |

---

## 3. Bounded In-Memory Event Log

To ensure zero memory growth during long practice sessions (e.g. 30+ minutes):
- Events are logged into a fixed-size ring buffer with `max_recent_events = 50`.
- All session aggregates (`chords_matched`, `timing_offsets`, `note_recalls`) are maintained incrementally in fixed-size registers.

---

## 4. Per-Chord Mastery Tracking

Tracks independent performance statistics for each unique chord symbol ($C$, $G$, $Am$, $F$, $C\#m$, etc.):
```json
{
  "C#m": {
    "chordName": "C#m",
    "attempts": 8,
    "matches": 3,
    "partials": 2,
    "misses": 3,
    "avgTimingOffsetMs": 175.0,
    "avgNoteRecall": 0.54,
    "avgNotePrecision": 0.72,
    "difficultyScore": 2.4,
    "simplificationLevel": 0
  }
}
```

---

## 5. Targeted Practice Recommendations

Deterministic, explainable recommendation heuristics based on measured session metrics:
1. **Weak Chord Focus**: Identifies chords with $\text{attempts} \ge 2$ and $\text{avgNoteRecall} < 0.60$ -> `"Focus on [Chord]: note recall is X%. Practice individual hand shape."`
2. **Timing Lag Warning**: Emitted when $\text{avgTimingOffsetMs} > +150\text{ ms}$ across $\ge 4$ chord changes -> `"Late chord transitions observed (avg +Xms). Consider slowing tempo."`
3. **Extra Note Warning**: Emitted when $\text{notePrecision} < 0.70$ -> `"Extraneous notes detected. Verify finger placement and arch."`

---

## 6. Conservative Adaptive Tempo Advice

Adaptive tempo recommendations are strictly advisory and do **NOT** silently alter playback tempo:
- **Increase Tempo**: Recommended when $\ge 2$ consecutive loops achieve $\ge 88\%$ match rate ($\text{recommendedBpm} = \min(\text{originalBpm}, \text{currentBpm} + 3)$).
- **Decrease Tempo**: Recommended when $\ge 2$ consecutive loops achieve $\le 45\%$ match rate ($\text{recommendedBpm} = \max(30.0, \text{currentBpm} - 5)$).
- **Maintain Tempo**: Default steady state.
