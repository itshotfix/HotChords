"""
backend/analysis/realtime_pitch.py

Real-Time DSP Pitch & Polyphonic Piano Note Detector for HotChords (Phase 11).

Key Architectural & DSP Features:
1. Local & Transient Frame Processing: Pure in-memory DSP, zero disk writes, zero cloud calls.
2. Extended Piano Frequency Range: A0 (27.5 Hz, MIDI 21) to C8 (4186.0 Hz, MIDI 108).
3. Polyphonic Salience & Harmonic Overtone Suppression:
   - Evaluates multi-harmonic comb salience for fundamental pitch candidates.
   - Suppresses integer harmonic overtones (2*f0, 3*f0, 4*f0, 5*f0) to prevent overtone confusion (e.g. mistaking C5 or G5 for separate notes when C4 is played).
4. Temporal Stabilization & Hysteresis:
   - Note-on confirmation threshold (>= 2 frames).
   - Note-off release threshold (>= 3 frames).
   - Prevents single-frame noise flickers and flutter.
5. Deterministic Polyphonic Note Output: Returns sorted MIDI notes, note names, frequencies, and confidence scores.
"""

from typing import List, Dict, Optional, Tuple, Set
import numpy as np
from scipy.signal.windows import blackmanharris, hann

from backend.analysis.test_signals import midi_to_freq, midi_to_note_name


# MIDI Piano Range Constants
MIN_PIANO_MIDI = 21   # A0 (27.5 Hz)
MAX_PIANO_MIDI = 108  # C8 (4186.01 Hz)
MIN_PIANO_FREQ = 27.0
MAX_PIANO_FREQ = 4200.0


def freq_to_midi_exact(freq: float) -> float:
    """Convert exact frequency in Hz to fractional MIDI pitch (A4 = 440 Hz = MIDI 69)."""
    if freq <= 0:
        return 0.0
    return 69.0 + 12.0 * np.log2(freq / 440.0)


def midi_to_freq_exact(midi: float) -> float:
    """Convert MIDI pitch to frequency in Hz."""
    return 440.0 * (2.0 ** ((midi - 69.0) / 12.0))


def parabolic_interpolation(
    mag: np.ndarray,
    peak_idx: int,
    bin_freqs: np.ndarray,
) -> Tuple[float, float]:
    """
    Sub-bin quadratic/parabolic peak interpolation for accurate frequency & magnitude estimation.
    Returns (interpolated_frequency, interpolated_magnitude).
    """
    if peak_idx <= 0 or peak_idx >= len(mag) - 1:
        return bin_freqs[peak_idx], mag[peak_idx]

    alpha = mag[peak_idx - 1]
    beta = mag[peak_idx]
    gamma = mag[peak_idx + 1]

    denom = alpha - 2.0 * beta + gamma
    if abs(denom) < 1e-12:
        return bin_freqs[peak_idx], beta

    delta = 0.5 * (alpha - gamma) / denom
    delta = np.clip(delta, -0.5, 0.5)

    bin_width = bin_freqs[1] - bin_freqs[0] if len(bin_freqs) > 1 else 1.0
    interp_freq = bin_freqs[peak_idx] + delta * bin_width
    interp_mag = beta - 0.25 * (alpha - gamma) * delta
    return float(interp_freq), float(interp_mag)


class DetectedNote:
    """Represents a single detected piano note with frequency, MIDI, and confidence."""
    def __init__(
        self,
        midi: int,
        note_name: str,
        frequency: float,
        confidence: float,
        salience: float = 1.0,
    ):
        self.midi = int(midi)
        self.note_name = note_name
        self.frequency = round(float(frequency), 2)
        self.confidence = round(float(confidence), 3)
        self.salience = round(float(salience), 4)

    def to_dict(self) -> Dict[str, any]:
        return {
            "midi": self.midi,
            "noteName": self.note_name,
            "frequency": self.frequency,
            "confidence": self.confidence,
        }

    def __repr__(self) -> str:
        return f"<DetectedNote {self.note_name} (MIDI {self.midi}) conf={self.confidence}>"


class PolyphonicPitchDetector:
    """
    Real-Time Polyphonic Pitch Detector optimized for acoustic and digital piano audio.
    """

    def __init__(
        self,
        sample_rate: int = 22050,
        n_fft: int = 4096,
        hop_size: int = 512,
        min_midi: int = MIN_PIANO_MIDI,
        max_midi: int = MAX_PIANO_MIDI,
        energy_threshold: float = 0.005,
        peak_threshold: float = 0.08,
        cents_tolerance: float = 40.0,
        max_polyphony: int = 6,
    ):
        self.sample_rate = sample_rate
        self.n_fft = n_fft
        self.hop_size = hop_size
        self.min_midi = min_midi
        self.max_midi = max_midi
        self.energy_threshold = energy_threshold
        self.peak_threshold = peak_threshold
        self.cents_tolerance = cents_tolerance
        self.max_polyphony = max_polyphony

        # Precompute window and frequency bins
        self.window = blackmanharris(n_fft).astype(np.float32)
        self.bin_freqs = np.fft.rfftfreq(n_fft, d=1.0 / sample_rate)

        # Precompute note target frequencies
        self.midi_notes = np.arange(min_midi, max_midi + 1)
        self.target_freqs = np.array([midi_to_freq_exact(m) for m in self.midi_notes])

    def detect_frame(self, audio_frame: np.ndarray) -> Dict[str, any]:
        """
        Process a single audio frame and return the detected polyphonic note set.
        
        Returns:
            Dict containing:
                - status: 'NO_INPUT' | 'LOW_CONFIDENCE' | 'DETECTED'
                - notes: List[DetectedNote] (sorted by MIDI number)
                - confidence: Aggregate frame confidence [0.0, 1.0]
                - polyphony_type: 'MONOPHONIC' | 'POLYPHONIC' | 'UNKNOWN'
        """
        # 1. Check frame amplitude / RMS energy
        if len(audio_frame) < self.n_fft:
            # Zero-pad if frame is shorter than FFT size
            padded = np.zeros(self.n_fft, dtype=np.float32)
            padded[:len(audio_frame)] = audio_frame
            audio_frame = padded
        else:
            audio_frame = audio_frame[:self.n_fft]

        rms = np.sqrt(np.mean(audio_frame ** 2) + 1e-12)
        if rms < self.energy_threshold:
            return {
                "status": "NO_INPUT",
                "notes": [],
                "confidence": 0.0,
                "polyphony_type": "UNKNOWN",
                "rms": float(rms),
            }

        # 2. Windowed FFT
        windowed = audio_frame * self.window
        spec = np.abs(np.fft.rfft(windowed))
        max_mag = np.max(spec)
        if max_mag < 1e-6:
            return {
                "status": "NO_INPUT",
                "notes": [],
                "confidence": 0.0,
                "polyphony_type": "UNKNOWN",
                "rms": float(rms),
            }

        norm_spec = spec / max_mag

        # Spectral Flatness check (Wiener entropy): Inharmonic / Noise rejection
        power_spec = norm_spec ** 2 + 1e-12
        geom_mean = np.exp(np.mean(np.log(power_spec)))
        arith_mean = np.mean(power_spec)
        spectral_flatness = float(geom_mean / arith_mean)
        if spectral_flatness > 0.12:
            return {
                "status": "LOW_CONFIDENCE",
                "notes": [],
                "confidence": 0.15,
                "polyphony_type": "UNKNOWN",
                "rms": float(rms),
            }

        # 3. Peak Finding in Spectrum
        peaks = []
        for i in range(1, len(norm_spec) - 1):
            if (norm_spec[i] > norm_spec[i - 1] and 
                norm_spec[i] > norm_spec[i + 1] and 
                norm_spec[i] >= self.peak_threshold):
                
                f_interp, m_interp = parabolic_interpolation(norm_spec, i, self.bin_freqs)
                if MIN_PIANO_FREQ <= f_interp <= MAX_PIANO_FREQ:
                    peaks.append((f_interp, m_interp))

        if not peaks:
            return {
                "status": "LOW_CONFIDENCE",
                "notes": [],
                "confidence": 0.1,
                "polyphony_type": "UNKNOWN",
                "rms": float(rms),
            }

        # 4. Harmonic Salience & Fundamental Candidate Scoring
        num_harmonics = 5
        harmonic_weights = [1.0, 0.65, 0.45, 0.30, 0.20]
        
        salience_map = np.zeros(len(self.midi_notes), dtype=np.float32)
        has_f0_peak = np.zeros(len(self.midi_notes), dtype=bool)
        peak_freqs = np.array([p[0] for p in peaks])
        peak_mags = np.array([p[1] for p in peaks])
        num_peaks = len(peak_freqs)

        for idx, midi in enumerate(self.midi_notes):
            f0 = self.target_freqs[idx]
            f0_salience = 0.0
            h1_mag = 0.0
            higher_h_count = 0
            
            for h in range(1, num_harmonics + 1):
                target_fh = f0 * h
                if target_fh > MAX_PIANO_FREQ:
                    break
                
                # Fast logarithmic search in sorted peak frequencies
                pos = np.searchsorted(peak_freqs, target_fh)
                best_idx = None
                best_cents = 999.0
                
                for p_cand in (pos - 1, pos, pos + 1):
                    if 0 <= p_cand < num_peaks:
                        c_diff = 1200.0 * abs(np.log2(peak_freqs[p_cand] / target_fh))
                        if c_diff < best_cents:
                            best_cents = c_diff
                            best_idx = p_cand
                
                if best_idx is not None and best_cents <= self.cents_tolerance:
                    match_mag = float(peak_mags[best_idx])
                    f0_salience += harmonic_weights[h - 1] * match_mag
                    if h == 1:
                        h1_mag = match_mag
                        has_f0_peak[idx] = True
                    elif match_mag > 0.15:
                        higher_h_count += 1

            # Fundamental requirement: A real played note must have a distinct fundamental peak (h=1)
            # or strong h1+h2 evidence. Subharmonics whose h=1 is absent are rejected.
            if h1_mag >= 0.18:
                salience_map[idx] = f0_salience + (0.5 * h1_mag)

        # 5. Overtone Cancellation & Selection of Distinct Fundamentals
        candidate_indices = np.where(salience_map > 0.50)[0]
        if len(candidate_indices) == 0:
            return {
                "status": "LOW_CONFIDENCE",
                "notes": [],
                "confidence": 0.15,
                "polyphony_type": "UNKNOWN",
                "rms": float(rms),
            }

        # Sort candidate notes by salience descending
        sorted_candidates = candidate_indices[np.argsort(-salience_map[candidate_indices])]
        
        selected_notes: List[DetectedNote] = []
        claimed_midis: Set[int] = set()
        
        for cand_idx in sorted_candidates:
            midi_cand = int(self.midi_notes[cand_idx])
            sal = float(salience_map[cand_idx])
            
            if midi_cand in claimed_midis:
                continue

            # Check if this candidate is an overtone of an already selected lower note
            is_overtone = False
            for sel in selected_notes:
                semitone_diff = midi_cand - sel.midi
                if semitone_diff in [12, 19, 24, 28]:
                    if sal <= sel.salience * 0.95:
                        is_overtone = True
                        break

            if is_overtone:
                continue

            # Compute calibrated confidence [0.0, 1.0]
            conf = float(np.clip(sal / 2.0, 0.45, 0.98))
            f_actual = midi_to_freq_exact(midi_cand)
            n_name = midi_to_note_name(midi_cand)
            
            selected_notes.append(DetectedNote(
                midi=midi_cand,
                note_name=n_name,
                frequency=f_actual,
                confidence=conf,
                salience=sal,
            ))
            claimed_midis.add(midi_cand)

            if len(selected_notes) >= self.max_polyphony:
                break

        # Sort selected notes by MIDI ascending
        selected_notes.sort(key=lambda n: n.midi)

        if not selected_notes:
            return {
                "status": "LOW_CONFIDENCE",
                "notes": [],
                "confidence": 0.25,
                "polyphony_type": "UNKNOWN",
                "rms": float(rms),
            }

        avg_conf = float(np.mean([n.confidence for n in selected_notes]))
        poly_type = "MONOPHONIC" if len(selected_notes) == 1 else "POLYPHONIC"

        return {
            "status": "DETECTED",
            "notes": selected_notes,
            "confidence": round(avg_conf, 3),
            "polyphony_type": poly_type,
            "rms": float(rms),
        }


class RealTimeNoteTracker:
    """
    Temporal Stabilization & Hysteresis Tracker for Real-Time Note Detection.
    - Note-On Confirmation: Requires note presence across >= persistence_threshold frames.
    - Note-Off Release: Requires note absence across >= release_threshold frames.
    - Eliminates transient jitter and frame-to-frame dropouts.
    """

    def __init__(
        self,
        detector: Optional[PolyphonicPitchDetector] = None,
        persistence_threshold: int = 2,
        release_threshold: int = 3,
    ):
        self.detector = detector or PolyphonicPitchDetector()
        self.persistence_threshold = persistence_threshold
        self.release_threshold = release_threshold

        # Tracking state: midi -> consecutive count
        self.candidate_counts: Dict[int, int] = {}
        self.active_notes: Dict[int, DetectedNote] = {}
        self.missing_counts: Dict[int, int] = {}

    def reset(self) -> None:
        """Reset all temporal tracking state."""
        self.candidate_counts.clear()
        self.active_notes.clear()
        self.missing_counts.clear()

    def process_frame(self, audio_frame: np.ndarray) -> Dict[str, any]:
        """
        Process audio frame and return stabilized, temporally smoothed active notes.
        """
        frame_result = self.detector.detect_frame(audio_frame)
        
        detected_dict = {n.midi: n for n in frame_result["notes"]}
        detected_midis = set(detected_dict.keys())

        # Update candidate counts for newly detected notes
        for midi, note in detected_dict.items():
            self.candidate_counts[midi] = self.candidate_counts.get(midi, 0) + 1
            self.missing_counts[midi] = 0
            
            # Confirm note if persistence threshold reached
            if self.candidate_counts[midi] >= self.persistence_threshold:
                self.active_notes[midi] = note

        # Update missing counts for currently active notes that were not detected in this frame
        all_active_midis = list(self.active_notes.keys())
        for midi in all_active_midis:
            if midi not in detected_midis:
                self.missing_counts[midi] = self.missing_counts.get(midi, 0) + 1
                if self.missing_counts[midi] >= self.release_threshold:
                    # Release note
                    del self.active_notes[midi]
                    self.candidate_counts[midi] = 0
                    del self.missing_counts[midi]

        # Clean up candidate counts for unconfirmed notes that disappeared
        for midi in list(self.candidate_counts.keys()):
            if midi not in detected_midis and midi not in self.active_notes:
                self.candidate_counts[midi] = max(0, self.candidate_counts[midi] - 1)

        # Assemble stable note set
        stable_notes = sorted(list(self.active_notes.values()), key=lambda n: n.midi)

        if not stable_notes:
            status = frame_result["status"] if frame_result["status"] == "NO_INPUT" else "LISTENING"
            return {
                "status": status,
                "notes": [],
                "confidence": frame_result.get("confidence", 0.0),
                "polyphony_type": "UNKNOWN",
                "rms": frame_result.get("rms", 0.0),
            }

        avg_conf = float(np.mean([n.confidence for n in stable_notes]))
        poly_type = "MONOPHONIC" if len(stable_notes) == 1 else "POLYPHONIC"

        return {
            "status": "DETECTED",
            "notes": stable_notes,
            "confidence": round(avg_conf, 3),
            "polyphony_type": poly_type,
            "rms": frame_result.get("rms", 0.0),
        }
