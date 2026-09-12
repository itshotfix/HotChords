"""
backend/analysis/test_signals.py

Deterministic Synthetic Piano-like Audio Signal Generator for HotChords (Phase 11).

Provides high-quality synthetic signals with harmonic overtones, exponential decay envelopes,
and controlled acoustic characteristics for unit testing and MIR DSP validation:
- Single notes (e.g. C4, A4)
- Common piano triads (C major, G major, A minor, F major, C minor)
- Four-note extended chords (C7, Cmaj7)
- Inversions and slash chords (C/E)
- Silence, white/pink noise, detuned frequencies, and overtone-rich tones
"""

from typing import List, Tuple, Union, Optional
import numpy as np


# Standard MIDI to Frequency (A4 = 440.0 Hz)
def midi_to_freq(midi: Union[int, float]) -> float:
    return 440.0 * (2.0 ** ((midi - 69.0) / 12.0))


def note_name_to_midi(name: str) -> int:
    """Convert note name (e.g., 'C4', 'F#3', 'Bb5') to MIDI note number."""
    notes = {'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3,
             'E': 4, 'F': 5, 'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8,
             'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11}
    name = name.strip()
    if len(name) < 2:
        raise ValueError(f"Invalid note name: {name}")
    
    if name[1] in ['#', 'b']:
        pitch_str = name[:2]
        octave_str = name[2:]
    else:
        pitch_str = name[:1]
        octave_str = name[1:]
        
    pitch = notes[pitch_str]
    octave = int(octave_str)
    return (octave + 1) * 12 + pitch


def midi_to_note_name(midi: int) -> str:
    """Convert MIDI note number (e.g. 60 -> 'C4', 69 -> 'A4') to pitch name."""
    note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    pitch = midi % 12
    octave = (midi // 12) - 1
    return f"{note_names[pitch]}{octave}"


def generate_piano_tone(
    freq: float,
    duration: float = 1.0,
    sr: int = 22050,
    amplitude: float = 0.5,
    decay_rate: float = 2.5,
    num_harmonics: int = 6,
    detune_cents: float = 0.0,
) -> np.ndarray:
    """
    Synthesize a single realistic piano-like tone with harmonic decay and overtone distribution.
    """
    actual_freq = freq * (2.0 ** (detune_cents / 1200.0))
    n_samples = int(sr * duration)
    t = np.linspace(0, duration, n_samples, endpoint=False)
    
    # Piano decay envelope: fast attack, exponential decay
    attack_samples = min(int(sr * 0.005), n_samples)
    envelope = np.exp(-decay_rate * t)
    if attack_samples > 0:
        envelope[:attack_samples] *= np.linspace(0.0, 1.0, attack_samples)
        
    # Harmonic overtone weights (piano spectral decay: higher harmonics decay faster)
    signal = np.zeros(n_samples, dtype=np.float32)
    for h in range(1, num_harmonics + 1):
        h_freq = actual_freq * h
        if h_freq >= sr / 2.0:
            break
        # Amplitude falls roughly as 1 / h^1.2, decay is faster for higher harmonics
        h_amp = 1.0 / (h ** 1.2)
        h_decay = np.exp(-(decay_rate * (1.0 + 0.35 * (h - 1))) * t)
        signal += h_amp * np.sin(2.0 * np.pi * h_freq * t) * h_decay
        
    # Normalize and scale
    max_val = np.max(np.abs(signal))
    if max_val > 1e-6:
        signal = (signal / max_val) * amplitude
    return signal.astype(np.float32)


def generate_chord_signal(
    midi_notes: List[int],
    duration: float = 1.5,
    sr: int = 22050,
    amplitude: float = 0.6,
    decay_rate: float = 2.0,
    num_harmonics: int = 6,
) -> np.ndarray:
    """
    Synthesize polyphonic chord audio from a list of MIDI note numbers.
    """
    n_samples = int(sr * duration)
    chord_signal = np.zeros(n_samples, dtype=np.float32)
    
    if not midi_notes:
        return chord_signal

    per_note_amp = amplitude / np.sqrt(len(midi_notes))
    for midi in midi_notes:
        freq = midi_to_freq(midi)
        tone = generate_piano_tone(
            freq=freq,
            duration=duration,
            sr=sr,
            amplitude=per_note_amp,
            decay_rate=decay_rate,
            num_harmonics=num_harmonics,
        )
        chord_signal += tone
        
    max_val = np.max(np.abs(chord_signal))
    if max_val > 1.0:
        chord_signal = chord_signal / max_val * 0.95
    return chord_signal.astype(np.float32)


def generate_silence(duration: float = 1.0, sr: int = 22050) -> np.ndarray:
    """Generate pure silent audio."""
    return np.zeros(int(sr * duration), dtype=np.float32)


def generate_noise(duration: float = 1.0, sr: int = 22050, amplitude: float = 0.1, pink: bool = False) -> np.ndarray:
    """Generate white or pink noise signal for robustness testing."""
    n_samples = int(sr * duration)
    white = np.random.normal(0, 1, n_samples).astype(np.float32)
    if not pink:
        max_v = np.max(np.abs(white))
        return (white / max_v * amplitude) if max_v > 0 else white
    
    # 1/f Pink filter approximation
    b = [0.049922035, -0.095993537, 0.050612699, -0.004408786]
    a = [1.0, -2.494956002, 2.017265875, -0.522189400]
    from scipy.signal import lfilter
    pink_signal = lfilter(b, a, white).astype(np.float32)
    max_v = np.max(np.abs(pink_signal))
    return (pink_signal / max_v * amplitude) if max_v > 0 else pink_signal


# Predefined Chord Presets for Standard MIR & Pedagogy Testing
TEST_PRESETS = {
    "C4_SINGLE": [60],                      # C4 (261.63 Hz)
    "A4_SINGLE": [69],                      # A4 (440.00 Hz)
    "C_MAJOR": [60, 64, 67],                # C4, E4, G4
    "G_MAJOR": [55, 59, 62],                # G3, B3, D4
    "A_MINOR": [57, 60, 64],                # A3, C4, E4
    "F_MAJOR": [53, 57, 60],                # F3, A3, C4
    "C_MINOR": [60, 63, 67],                # C4, Eb4, G4
    "C7": [60, 64, 67, 70],                 # C4, E4, G4, Bb4
    "CMAJ7": [60, 64, 67, 71],              # C4, E4, G4, B4
    "C_OVER_E": [52, 60, 64, 67],           # E3 (bass), C4, E4, G4
    "C_OCTAVE_SHIFTED": [48, 52, 55],       # C3, E3, G3 (octave lower than C4-E4-G4)
}


def get_preset_signal(preset_name: str, duration: float = 1.5, sr: int = 22050) -> np.ndarray:
    """Convenience helper to retrieve a synthesized preset audio signal."""
    preset = preset_name.upper()
    if preset == "SILENCE":
        return generate_silence(duration=duration, sr=sr)
    if preset == "NOISE":
        return generate_noise(duration=duration, sr=sr)
    if preset in TEST_PRESETS:
        return generate_chord_signal(TEST_PRESETS[preset], duration=duration, sr=sr)
    raise ValueError(f"Unknown preset name '{preset_name}'. Available: {list(TEST_PRESETS.keys()) + ['SILENCE', 'NOISE']}")
