# Practice Feedback & Matching Engine Specification (Phase 11)

## 1. Overview

The Practice Feedback Engine (`backend/theory/practice_feedback.py` and `frontend/js/audio/practiceFeedbackBridge.js`) performs deterministic comparison between authoritative expected chord voicings and real-time observed notes.

---

## 2. Authoritative Expected State Derivation

Expected note states are derived strictly from:
- `PianoVoicingEngine.voice_chord(...)` or
- `PracticeSession.guidance`

The microphone layer **never generates or alters** expected chord voicings.

---

## 3. Note & Chord Comparison Metrics

### Sets:
- Expected Notes: $E = \{e_1, e_2, \dots, e_n\}$
- Observed Notes: $O = \{o_1, o_2, \dots, o_m\}$
- Correct Notes: $C = E \cap O$
- Missing Notes: $M = E \setminus O$
- Extra Notes: $X = O \setminus E$

### Objective Metrics:
$$\text{Recall} = \frac{|C|}{|E|}$$
$$\text{Precision} = \frac{|C|}{|C| + |X|}$$
$$\text{F1 Score} = 2 \cdot \frac{\text{Precision} \cdot \text{Recall}}{\text{Precision} + \text{Recall}}$$

---

## 4. Matching Modes

### `EXACT_NOTE_MATCH`:
Compares exact MIDI note numbers (e.g., $E = \{60, 64, 67\}$ for $C_4, E_4, G_4$). Playing $C_3, E_3, G_3$ ($48, 52, 55$) will be reported as missing $60, 64, 67$ and extra $48, 52, 55$.

### `PITCH_CLASS_MATCH`:
Compares modulo-12 pitch classes ($e \pmod{12}$). Playing $C_3, E_3, G_3$ produces pitch classes $\{0, 4, 7\}$, matching expected $\{0, 4, 7\}$ with $1.0\text{ Recall}$ and $1.0\text{ Precision}$.

---

## 5. Feedback Status Definitions

| Status | Trigger Condition | Pedagogical Meaning |
| :--- | :--- | :--- |
| `NO_INPUT` | RMS energy below threshold or zero detected notes | Player has not yet struck any keys. |
| `LISTENING` | Low-amplitude audio detected; stabilizing | Awaiting clear attack. |
| `PARTIAL` | $\text{Recall} \ge 0.50$ and $\text{Precision} \ge 0.50$ | Some notes correct, but one or more chord tones missing. |
| `MATCH` | $\text{Recall} \ge 0.80$ and $\text{Precision} \ge 0.70$ | Full chord successfully struck. |
| `WRONG_NOTES` | Audible notes detected but $\text{Recall} < 0.50$ | Incorrect chord or extraneous keys played. |
| `LOW_CONFIDENCE` | Input SNR or confidence $< 0.35$ | Background noise or unclear acoustic signal. |
| `EXPECTED_CHORD_UNAVAILABLE` | Playback position is silent / between chords | No target chord expected at this time. |
| `INPUT_PERMISSION_DENIED` | User denied microphone permission | Prompts user to check browser permissions. |
| `INPUT_UNAVAILABLE` | Microphone hardware disconnected/busy | Audio input device not ready. |
| `INPUT_UNSUPPORTED` | Browser lacks `getUserMedia` | Incompatible browser environment. |

---

## 6. Timing Grace Windows & Sustain Hysteresis

### Timing Phases:
- `PREPARING`: $T < \text{chordStart}$
- `ACTIVE`: $\text{chordStart} \le T \le \text{chordEnd} - \text{graceWindow}$
- `TRANSITION`: Within $\pm 250\text{ ms}$ of chord boundaries.

### Sustain Decay Tolerance:
During the transition grace window, ringing notes from the immediately preceding chord ($P$) are filtered from being penalized as `extra_notes`:
$$X_{\text{effective}} = (O \setminus E) \setminus P$$
This prevents acoustic piano decay and natural finger legato from falsely triggering `WRONG_NOTES`.
