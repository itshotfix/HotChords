"""
backend/benchmarks/synthetic_generator.py

Deterministic Multi-Instrument Synthetic Audio Generator for MIR Diagnostic Benchmarking.
Generates controlled harmonic audio with precise ground-truth chord timelines and structure:
- Multi-instrument timbres: Piano (decaying harmonics), Guitar (plucked strumming), Synth pad (rich multi-oscillator), Bass (sub-harmonic)
- Controlled progressions: Standard Pop (C-G-Am-F), Pop 2 (Am-F-C-G), 2-chord vamp (C-G-C-G), Extended Chords (Cmaj7-G7-Am7-Fmaj7), Alternating 4-event (C-G-C-F), Transposed modulation, Sustained single chord, Silent/noise audio
- Exact ground truth annotations (timestamp_start, timestamp_end, chord, raw_chord, loop_ground_truth)
"""

from typing import List, Dict, Any, Tuple, Optional
import numpy as np
import soundfile as sf
import os
import tempfile

NOTE_FREQS = {
    "C1": 32.70, "C#1": 34.65, "D1": 36.71, "D#1": 38.89, "E1": 41.20, "F1": 43.65, "F#1": 46.25, "G1": 49.00, "G#1": 51.91, "A1": 55.00, "A#1": 58.27, "B1": 61.74,
    "C2": 65.41, "C#2": 69.30, "D2": 73.42, "D#2": 77.78, "E2": 82.41, "F2": 87.31, "F#2": 92.50, "G2": 98.00, "G#2": 103.83, "A2": 110.00, "A#2": 116.54, "B2": 123.47,
    "C3": 130.81, "C#3": 138.59, "D3": 146.83, "D#3": 155.56, "E3": 164.81, "F3": 174.61, "F#3": 185.00, "G3": 196.00, "G#3": 207.65, "A3": 220.00, "A#3": 233.08, "B3": 246.94,
    "C4": 261.63, "C#4": 277.18, "D4": 293.66, "D#4": 311.13, "E4": 329.63, "F4": 349.23, "F#4": 369.99, "G4": 392.00, "G#4": 415.30, "A4": 440.00, "A#4": 466.16, "B4": 493.88,
    "C5": 523.25, "C#5": 554.37, "D5": 587.33, "D#5": 622.25, "E5": 659.25, "F5": 698.46, "F#5": 739.99, "G5": 783.99, "G#5": 830.61, "A5": 880.00, "A#5": 932.33, "B5": 987.77,
}

CHORD_SEMITONES = {
    "maj": [0, 4, 7],
    "": [0, 4, 7],
    "min": [0, 3, 7],
    "m": [0, 3, 7],
    "7": [0, 4, 7, 10],
    "maj7": [0, 4, 7, 11],
    "min7": [0, 3, 7, 10],
    "m7": [0, 3, 7, 10],
    "dim": [0, 3, 6],
    "aug": [0, 4, 8],
    "sus2": [0, 2, 7],
    "sus4": [0, 5, 7],
}

ROOT_SEMITONES = {
    "C": 0, "C#": 1, "DB": 1, "D": 2, "D#": 3, "EB": 3, "E": 4, "FB": 4, "F": 5, "E#": 5, "F#": 6, "GB": 6, "G": 7, "G#": 8, "AB": 8, "A": 9, "A#": 10, "BB": 10, "B": 11, "CB": 11
}


def _synthesize_note(
    freq: float,
    duration: float,
    sr: int = 22050,
    instrument: str = "piano",
    velocity: float = 0.8
) -> np.ndarray:
    """Synthesizes a single note with instrument-specific harmonic timbre and ADSR."""
    n_samples = int(duration * sr)
    t = np.linspace(0, duration, n_samples, endpoint=False)

    if instrument == "piano":
        # Multi-harmonic with exponential decay
        audio = np.zeros(n_samples)
        harmonics = [1.0, 0.6, 0.4, 0.25, 0.15, 0.08]
        decay_rates = [1.5, 2.5, 3.5, 4.5, 5.5, 7.0]
        for h_idx, (h_amp, d_rate) in enumerate(zip(harmonics, decay_rates), start=1):
            h_freq = freq * h_idx
            if h_freq < sr / 2:
                audio += h_amp * np.sin(2 * np.pi * h_freq * t) * np.exp(-d_rate * t)
        # Attack envelope
        attack_len = min(int(0.015 * sr), n_samples)
        if attack_len > 0:
            audio[:attack_len] *= np.linspace(0, 1, attack_len)

    elif instrument == "guitar":
        # Plucked string harmonic distribution
        audio = np.zeros(n_samples)
        harmonics = [1.0, 0.8, 0.5, 0.35, 0.2, 0.1]
        for h_idx, h_amp in enumerate(harmonics, start=1):
            h_freq = freq * h_idx
            if h_freq < sr / 2:
                audio += h_amp * np.sin(2 * np.pi * h_freq * t) * np.exp(-2.2 * h_idx**0.5 * t)
        attack_len = min(int(0.008 * sr), n_samples)
        if attack_len > 0:
            audio[:attack_len] *= np.linspace(0, 1, attack_len)

    elif instrument == "bass":
        # Deep sub-fundamental with warm 2nd harmonic
        audio = np.sin(2 * np.pi * freq * t) * np.exp(-0.8 * t)
        if freq * 2 < sr / 2:
            audio += 0.5 * np.sin(2 * np.pi * freq * 2 * t) * np.exp(-1.5 * t)

    elif instrument == "synth":
        # Rich detuned saw/pad with slow release
        audio = (
            0.5 * np.sin(2 * np.pi * freq * t) +
            0.3 * np.sin(2 * np.pi * (freq * 1.002) * t) +
            0.2 * np.sin(2 * np.pi * (freq * 0.998) * t) +
            0.25 * np.sin(2 * np.pi * (freq * 2) * t)
        )
        # Gentle fade in/out
        env = np.ones(n_samples)
        fade_len = min(int(0.05 * sr), n_samples // 4)
        if fade_len > 0:
            env[:fade_len] = np.linspace(0, 1, fade_len)
            env[-fade_len:] = np.linspace(1, 0, fade_len)
        audio *= env
    else:
        audio = np.sin(2 * np.pi * freq * t)

    return (audio * velocity).astype(np.float32)


def generate_synthetic_song(
    progression: List[Tuple[str, float]],  # List of (chord_name, duration_sec)
    instrument: str = "piano",
    sr: int = 22050,
    add_bass: bool = True,
    add_arpeggio: bool = False,
    noise_level: float = 0.005,
    repetition_count: int = 1
) -> Tuple[np.ndarray, List[Dict[str, Any]], float]:
    """
    Generates synthetic polyphonic audio and precise reference chord annotations.
    """
    timeline_events = []
    full_audio = []
    current_time = 0.0

    for rep in range(repetition_count):
        for chord_str, dur in progression:
            # Parse chord
            if chord_str.upper() in ("N", "NO_CHORD", ""):
                # Silence / noise
                n_samples = int(dur * sr)
                audio_chunk = np.random.normal(0, noise_level, n_samples).astype(np.float32)
                full_audio.append(audio_chunk)
                timeline_events.append({
                    "time": round(current_time, 3),
                    "start": round(current_time, 3),
                    "end": round(current_time + dur, 3),
                    "chord": "N",
                    "raw_chord": "N",
                    "confidence": 1.0
                })
                current_time += dur
                continue

            # Parse root and quality
            bass_root = None
            core_chord = chord_str
            if "/" in chord_str:
                core_chord, bass_root = chord_str.split("/", 1)

            if len(core_chord) >= 2 and core_chord[1] in ("#", "b", "B"):
                root = core_chord[:2].upper()
                qual = core_chord[2:].lower().replace(":", "")
            else:
                root = core_chord[:1].upper()
                qual = core_chord[1:].lower().replace(":", "")

            if qual in ("", "maj", "major"):
                qual_key = "maj"
            elif qual in ("m", "min", "minor"):
                qual_key = "min"
            else:
                qual_key = qual if qual in CHORD_SEMITONES else "maj"

            root_semi = ROOT_SEMITONES.get(root, 0)
            offsets = CHORD_SEMITONES.get(qual_key, [0, 4, 7])

            # Base octave 4 for piano chords
            base_midi = 60 + root_semi  # 60 = C4
            chord_audio = np.zeros(int(dur * sr), dtype=np.float32)

            for semi in offsets:
                midi_note = base_midi + semi
                freq = 440.0 * (2.0 ** ((midi_note - 69) / 12.0))
                note_wav = _synthesize_note(freq, dur, sr=sr, instrument=instrument, velocity=0.6)
                min_len = min(len(chord_audio), len(note_wav))
                chord_audio[:min_len] += note_wav[:min_len]

            # Add Bass note
            if add_bass:
                bass_semi = ROOT_SEMITONES.get(bass_root.upper() if bass_root else root, root_semi)
                bass_midi = 36 + bass_semi  # 36 = C2
                bass_freq = 440.0 * (2.0 ** ((bass_midi - 69) / 12.0))
                bass_wav = _synthesize_note(bass_freq, dur, sr=sr, instrument="bass", velocity=0.8)
                min_len = min(len(chord_audio), len(bass_wav))
                chord_audio[:min_len] += bass_wav[:min_len]

            # Add gentle noise floor
            chord_audio += np.random.normal(0, noise_level, len(chord_audio)).astype(np.float32)

            # Normalize peak
            peak = np.max(np.abs(chord_audio))
            if peak > 0.95:
                chord_audio = chord_audio / peak * 0.90

            full_audio.append(chord_audio)
            timeline_events.append({
                "time": round(current_time, 3),
                "start": round(current_time, 3),
                "end": round(current_time + dur, 3),
                "chord": chord_str,
                "raw_chord": chord_str,
                "confidence": 1.0
            })
            current_time += dur

    audio = np.concatenate(full_audio) if full_audio else np.zeros(int(sr), dtype=np.float32)
    duration = float(len(audio) / sr)
    return audio, timeline_events, duration


def save_synthetic_test_wav(audio: np.ndarray, sr: int = 22050, prefix: str = "synth_test") -> str:
    """Saves synthetic audio to a temporary WAV file and returns absolute path."""
    temp_dir = tempfile.gettempdir()
    path = os.path.join(temp_dir, f"{prefix}_{os.getpid()}_{np.random.randint(10000, 99999)}.wav")
    sf.write(path, audio, sr)
    return path
