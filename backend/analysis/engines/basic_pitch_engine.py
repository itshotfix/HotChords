"""
backend/analysis/engines/basic_pitch_engine.py

Isolated Spotify Basic Pitch (ICASSP 2022) transcription adapter using ONNX Runtime.
Repository: https://github.com/spotify/basic-pitch
Licence: Apache-2.0 (code & nmp.onnx weights)

Produces HotChords-compatible note event dicts:
    {"midi", "note", "start", "end", "velocity", "confidence", "source"}
"""

import os
import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import librosa
from scipy.signal import argrelmax

from backend.theory.piano_voicing import midi_to_note_name

logger = logging.getLogger(__name__)

# Basic Pitch model constants (ICASSP 2022 architecture)
BP_SAMPLE_RATE = 22050
BP_FFT_HOP = 256
BP_WINDOW_SAMPLES = 43844
BP_OVERLAP_FRAMES = 30
BP_OVERLAP_SAMPLES = BP_OVERLAP_FRAMES * BP_FFT_HOP  # 7680
BP_HOP_SAMPLES = BP_WINDOW_SAMPLES - BP_OVERLAP_SAMPLES  # 36164
BP_FRAMES_PER_WINDOW = 172
BP_ANNOT_FPS = BP_SAMPLE_RATE / BP_FFT_HOP  # ~86.1328 Hz
BP_MIN_MIDI = 21  # A0

DEFAULT_MODEL_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "assets",
        "models",
        "basic_pitch",
        "nmp.onnx",
    )
)


class BasicPitchEngine:
    """
    Isolated adapter for Spotify Basic Pitch via ONNX Runtime.
    Preserves existing HotChords transcription as fallback when disabled or unavailable.
    """

    def __init__(
        self,
        enabled: bool = True,
        model_path: Optional[str] = None,
        onset_threshold: float = 0.50,
        frame_threshold: float = 0.30,
        minimum_note_length_sec: float = 0.058,
        min_midi: int = 21,
        max_midi: int = 108,
        energy_tol_frames: int = 11,
    ):
        self.enabled = enabled
        self.model_path = model_path or DEFAULT_MODEL_PATH
        self.onset_threshold = onset_threshold
        self.frame_threshold = frame_threshold
        self.minimum_note_length_sec = minimum_note_length_sec
        self.min_midi = max(21, int(min_midi))
        self.max_midi = min(108, int(max_midi))
        self.energy_tol_frames = energy_tol_frames
        self._session = None

    @property
    def name(self) -> str:
        return "basic_pitch_onnx"

    def check_availability(self) -> Tuple[bool, Optional[str]]:
        if not self.enabled:
            return False, "BasicPitchEngine is disabled by configuration"
        if not os.path.isfile(self.model_path):
            return False, f"Basic Pitch ONNX model not found at {self.model_path}"
        try:
            import onnxruntime  # noqa: F401
        except ImportError as e:
            return False, f"onnxruntime unavailable: {e}"
        return True, None

    def _get_session(self):
        if self._session is None:
            import onnxruntime as ort
            available = ort.get_available_providers()
            providers = [p for p in ("CoreMLExecutionProvider", "CPUExecutionProvider") if p in available]
            if not providers:
                providers = ["CPUExecutionProvider"]
            self._session = ort.InferenceSession(self.model_path, providers=providers)
        return self._session

    def transcribe_file(
        self,
        audio_path: str,
        source: str = "accompaniment",
    ) -> List[Dict[str, Any]]:
        """Load an audio file and transcribe it to HotChords note events."""
        if not audio_path or not os.path.isfile(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        y, sr = librosa.load(audio_path, sr=BP_SAMPLE_RATE, mono=True)
        return self.transcribe_audio(y, sr=sr, source=source)

    def transcribe_audio(
        self,
        y: np.ndarray,
        sr: int = BP_SAMPLE_RATE,
        source: str = "accompaniment",
    ) -> List[Dict[str, Any]]:
        """Transcribe a mono/stereo waveform array into HotChords note events."""
        ok, reason = self.check_availability()
        if not ok:
            raise RuntimeError(reason or "BasicPitchEngine unavailable")

        if y is None or len(y) == 0:
            return []

        arr = np.asarray(y, dtype=np.float32)
        if arr.ndim > 1:
            arr = np.mean(arr, axis=0).astype(np.float32)
        if not np.all(np.isfinite(arr)):
            arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
        if len(arr) < int(0.05 * sr) or float(np.max(np.abs(arr))) < 1e-6:
            return []

        if int(sr) != BP_SAMPLE_RATE:
            arr = librosa.resample(arr, orig_sr=int(sr), target_sr=BP_SAMPLE_RATE).astype(np.float32)

        orig_len = len(arr)
        half_overlap = BP_OVERLAP_SAMPLES // 2
        padded = np.concatenate([np.zeros(half_overlap, dtype=np.float32), arr])

        windows: List[np.ndarray] = []
        pos = 0
        while pos < len(padded):
            chunk = padded[pos : pos + BP_WINDOW_SAMPLES]
            if len(chunk) < BP_WINDOW_SAMPLES:
                chunk = np.pad(chunk, (0, BP_WINDOW_SAMPLES - len(chunk)))
            windows.append(chunk)
            pos += BP_HOP_SAMPLES

        batch = np.stack(windows, axis=0)[..., np.newaxis]  # (B, 43844, 1)
        sess = self._get_session()
        input_name = sess.get_inputs()[0].name
        outs = sess.run(None, {input_name: batch})
        # Output mapping verified: out[0]=onset (B,172,88), out[1]=note (B,172,88)
        onset_windows = outs[0]
        note_windows = outs[1]

        onset_mat = self._unwrap_windows(onset_windows, orig_len)
        note_mat = self._unwrap_windows(note_windows, orig_len)

        return self._decode_notes(onset_mat, note_mat, source=source)

    @staticmethod
    def _unwrap_windows(windows: np.ndarray, orig_samples: int) -> np.ndarray:
        """Unwrap overlapping (B, 172, 88) windows into a continuous (T, 88) matrix."""
        half_frames = BP_OVERLAP_FRAMES // 2
        trimmed = windows[:, half_frames : BP_FRAMES_PER_WINDOW - half_frames, :]
        n_win, win_frames, n_bins = trimmed.shape
        stacked = trimmed.reshape(n_win * win_frames, n_bins)
        target_frames = int(np.ceil(orig_samples / float(BP_FFT_HOP)))
        return stacked[: min(target_frames, len(stacked))]

    def _decode_notes(
        self,
        onset_mat: np.ndarray,
        note_mat: np.ndarray,
        source: str,
    ) -> List[Dict[str, Any]]:
        """Decode onset and frame posteriors into discrete HotChords note events."""
        n_frames, n_keys = note_mat.shape
        if n_frames == 0:
            return []

        min_len_frames = max(1, int(round(self.minimum_note_length_sec * BP_ANNOT_FPS)))
        frame_dt = 1.0 / BP_ANNOT_FPS
        remaining_energy = note_mat.copy()
        events: List[Dict[str, Any]] = []

        # Local maxima in onset matrix per pitch (sorted strongest-first)
        peaks_t, peaks_k = argrelmax(onset_mat, axis=0, order=1)
        candidates: List[Tuple[float, int, int]] = []
        for t, k in zip(peaks_t, peaks_k):
            val = float(onset_mat[t, k])
            if val >= self.onset_threshold:
                candidates.append((val, int(t), int(k)))

        # Sort descending by onset probability, breaking ties by time
        candidates.sort(key=lambda x: (-x[0], x[1]))

        for onset_prob, t_start, key_idx in candidates:
            midi_val = BP_MIN_MIDI + key_idx
            if midi_val < self.min_midi or midi_val > self.max_midi:
                continue
            if t_start >= n_frames - 1:
                continue

            # Track note sustain forward with short dip tolerance
            t_end = t_start + 1
            dip_count = 0
            while t_end < n_frames:
                if remaining_energy[t_end, key_idx] < self.frame_threshold:
                    dip_count += 1
                    if dip_count >= self.energy_tol_frames:
                        break
                else:
                    dip_count = 0
                t_end += 1

            # Trim trailing below-threshold dip frames
            t_end = max(t_start + 1, t_end - dip_count)
            if (t_end - t_start) < min_len_frames:
                continue

            # Zero out consumed energy for this note (and small neighbor bleed)
            note_slice = remaining_energy[t_start:t_end, key_idx]
            mean_act = float(np.mean(note_slice)) if len(note_slice) > 0 else onset_prob
            remaining_energy[t_start:t_end, key_idx] = 0.0
            if key_idx > 0:
                remaining_energy[t_start:t_end, key_idx - 1] *= 0.25
            if key_idx < n_keys - 1:
                remaining_energy[t_start:t_end, key_idx + 1] *= 0.25

            conf = float(np.clip(0.55 * onset_prob + 0.45 * mean_act, 0.0, 1.0))
            vel = int(np.clip(round(36 + conf * 78), 35, 115))
            events.append({
                "midi": int(midi_val),
                "note": midi_to_note_name(int(midi_val)),
                "start": round(t_start * frame_dt, 4),
                "end": round(t_end * frame_dt, 4),
                "velocity": vel,
                "confidence": round(conf, 3),
                "source": source,
            })

        events.sort(key=lambda e: (e["start"], e["midi"]))
        return events
