"""
backend/analysis/legacy_engine.py

Legacy Template Matching Chord Recognition Engine for HotChords.
Encapsulates the 61 overtone-aware template matcher and Viterbi HMM decoder
as a robust zero-weight fallback engine.
"""

from typing import List, Dict, Any, Optional
import numpy as np
import librosa
from backend.analysis.engine_base import ChordRecognitionEngine, ChordRecognitionResult
from backend.models.analysis_types import TimingData
from backend.theory.theory import (
    NOTE_NAMES, NOTE_FLAT, musician_friendly_name,
    _scale_notes, get_pitch_class
)
from backend.theory.normalization import normalize_chord_sequence


def _build_overtone_templates():
    """Builds chroma templates for 61 chord types incorporating overtone leaking."""
    T = {}
    chord_types = {
        '': [0, 4, 7],          # Major
        'm': [0, 3, 7],         # Minor
        '7': [0, 4, 7, 10],     # Dominant 7th
        'm7': [0, 3, 7, 10],    # Minor 7th
        'maj7': [0, 4, 7, 11]   # Major 7th
    }
    
    for i, r in enumerate(NOTE_NAMES):
        for suffix, notes in chord_types.items():
            v = np.zeros(12)
            for note in notes:
                pitch = (i + note) % 12
                v[pitch] += 1.0
                v[(pitch + 7) % 12] += 0.35
                v[(pitch + 4) % 12] += 0.15
                v[(pitch + 12) % 12] += 0.20
            T[r + suffix] = v / np.linalg.norm(v)
            
    T['N'] = np.ones(12) / np.sqrt(12)
    return T


TEMPLATES   = _build_overtone_templates()
CHORD_NAMES = list(TEMPLATES.keys())
CHORD_MAT   = np.array([TEMPLATES[c] for c in CHORD_NAMES]).T  # (12, 61)


def build_transition_matrix(key: str, scale: str) -> np.ndarray:
    """Builds music-theoretically informed transition probability matrix."""
    N = len(CHORD_NAMES)
    A = np.zeros((N, N))
    
    diatonic_chords = []
    if key != 'N':
        try:
            key_root = NOTE_NAMES.index(key) if key in NOTE_NAMES else NOTE_FLAT.index(key)
            is_minor = (scale == 'Minor')
            intervals = [0, 2, 3, 5, 7, 8, 10] if is_minor else [0, 2, 4, 5, 7, 9, 11]
            suffixes = ['m', 'dim', '', 'm', 'm', '', ''] if is_minor else ['', 'm', 'm', '', '', 'm', 'dim']
            
            for deg, interval in enumerate(intervals):
                root_note = NOTE_NAMES[(key_root + interval) % 12]
                suffix = suffixes[deg]
                diatonic_chords.append(musician_friendly_name(root_note + suffix))
        except Exception:
            pass

    for i in range(N):
        c_from = CHORD_NAMES[i]
        A[i, i] = 0.72
        remaining_weight = 0.28
        weights = np.zeros(N)
        
        for j in range(N):
            if i == j: continue
            c_to = CHORD_NAMES[j]
            weight = 1.0
            
            if c_to in diatonic_chords:
                weight *= 3.5
                
            r_from = get_pitch_class(c_from)
            r_to = get_pitch_class(c_to)
            if r_from is not None and r_to is not None:
                interval = (r_to - r_from) % 12
                if interval in [5, 7]:
                    weight *= 2.0
                    
            if c_from == 'N' or c_to == 'N':
                weight *= 1.5
                
            weights[j] = weight
            
        sum_w = np.sum(weights)
        if sum_w > 0:
            weights = (weights / sum_w) * remaining_weight
            for j in range(N):
                if i != j:
                    A[i, j] = weights[j]
        else:
            for j in range(N):
                if i != j:
                    A[i, j] = remaining_weight / (N - 1)
                    
    return A


def viterbi_decode(similarity_matrix: np.ndarray, transition_matrix: np.ndarray) -> List[int]:
    """Decodes optimal chord sequence using Viterbi in log space."""
    T, N = similarity_matrix.shape
    log_A = np.log(transition_matrix + 1e-100)
    log_emissions = similarity_matrix * 9.0
    
    viterbi_log = np.zeros((T, N))
    backpointer = np.zeros((T, N), dtype=int)
    
    viterbi_log[0] = np.log(1.0 / N) + log_emissions[0]
    
    for t in range(1, T):
        for n in range(N):
            temp = viterbi_log[t-1] + log_A[:, n]
            best_s = np.argmax(temp)
            viterbi_log[t, n] = temp[best_s] + log_emissions[t, n]
            backpointer[t, n] = best_s
            
    best_last = np.argmax(viterbi_log[-1])
    path = [best_last]
    for t in range(T - 1, 0, -1):
        best_last = backpointer[t, path[-1]]
        path.append(best_last)
        
    path.reverse()
    return path


class LegacyTemplateEngine(ChordRecognitionEngine):
    """
    Legacy Template Matcher + Viterbi HMM chord recognition engine.
    """

    @property
    def name(self) -> str:
        return "legacy_template"

    def check_availability(self) -> tuple[bool, Optional[str]]:
        """Legacy template matcher is always available offline with zero external model weights."""
        return True, None

    def analyze(
        self,
        audio_path: str,
        timing_data: Optional[TimingData] = None,
        duration: Optional[float] = None,
        key: str = "C",
        scale: str = "Major",
        fallback_reason: Optional[str] = None
    ) -> ChordRecognitionResult:
        """Executes legacy template matching on audio."""
        y, sr = librosa.load(audio_path, sr=22050, mono=True)
        if duration is None:
            duration = float(librosa.get_duration(y=y, sr=sr))

        y_harm = librosa.effects.harmonic(y, margin=4)
        hop = 512
        chroma = librosa.feature.chroma_cqt(y=y_harm, sr=sr, hop_length=hop, bins_per_octave=36)
        win = max(1, int(0.4 * sr / hop))
        chroma_s = np.apply_along_axis(lambda x: np.convolve(x, np.ones(win) / win, 'same'), 1, chroma)

        beat_times = timing_data.beat_times if timing_data else []
        frame_times = librosa.frames_to_time(np.arange(chroma.shape[1]), sr=sr, hop_length=hop)

        norms = np.linalg.norm(chroma_s, axis=0, keepdims=True)
        norms = np.maximum(norms, 1e-6)
        chroma_norm = chroma_s / norms
        chroma_norm = np.nan_to_num(chroma_norm, nan=0.0, posinf=0.0, neginf=0.0)

        similarity = CHORD_MAT.T @ chroma_norm
        boundaries = np.concatenate([[0], beat_times, [duration]]) if len(beat_times) > 0 else np.array([0, duration])

        T_segments = len(boundaries) - 1
        beat_similarities = np.zeros((T_segments, len(CHORD_NAMES)))

        for i in range(T_segments):
            t0, t1 = boundaries[i], boundaries[i+1]
            mask = (frame_times >= t0) & (frame_times < t1)
            if np.any(mask):
                beat_similarities[i] = similarity[:, mask].mean(axis=1)
            else:
                beat_similarities[i] = np.zeros(len(CHORD_NAMES))
                beat_similarities[i][-1] = 1.0

        transition_matrix = build_transition_matrix(key, scale)
        viterbi_path = viterbi_decode(beat_similarities, transition_matrix)

        raw_events = []
        for i in range(T_segments):
            t0, t1 = boundaries[i], boundaries[i+1]
            idx = viterbi_path[i]
            raw_name = CHORD_NAMES[idx]
            conf = float(np.clip(beat_similarities[i, idx], 0, 1))

            raw_events.append({
                'start_time': round(float(t0), 3),
                'end_time': round(float(t1), 3),
                'chord': raw_name,
                'confidence': round(conf, 3)
            })

        normalized_events = normalize_chord_sequence(raw_events)
        avg_conf = float(np.mean([e['confidence'] for e in normalized_events])) if normalized_events else 0.5

        return ChordRecognitionResult(
            engine=self.name,
            version="0.3.0-legacy",
            fallbackReason=fallback_reason,
            events=normalized_events,
            rawEvents=raw_events,
            confidence=round(avg_conf, 3)
        )
