"""
backend/analysis/timing.py

Beat and Downbeat Timing Analysis Abstraction for HotChords.
Provides a modular interface for extracting tempo, beat onsets, downbeats,
and timing grid metadata independently of any specific underlying MIR library.
"""

from typing import Optional, List
import numpy as np
import librosa
from backend.models.analysis_types import TimingData


class TimingAnalyzer:
    """
    Modular Timing Analyzer.
    
    Provides decoupled access to:
    - get_beats() -> np.ndarray
    - get_downbeats() -> Optional[np.ndarray]
    - get_tempo() -> float
    - get_timing_data() -> TimingData
    """

    def __init__(
        self,
        y: np.ndarray,
        sr: int = 22050,
        hop_length: int = 512,
        time_signature: str = "4/4",
        tempo_override: Optional[float] = None
    ):
        self.y = y
        self.sr = sr
        self.hop_length = hop_length
        self.time_signature = time_signature
        self.duration = float(len(y) / sr) if y is not None and len(y) > 0 else 0.0

        self._tempo: Optional[float] = tempo_override
        self._beat_frames: Optional[np.ndarray] = None
        self._beat_times: Optional[np.ndarray] = None
        self._downbeat_times: Optional[np.ndarray] = None
        self._beat_confidence: Optional[float] = None
        self._is_analyzed = False

    def analyze(self) -> "TimingAnalyzer":
        """Executes the rhythm and beat extraction pipeline."""
        if self._is_analyzed:
            return self

        if self.y is None or len(self.y) < self.sr * 0.2 or np.max(np.abs(self.y)) < 1e-5:
            self._tempo = 120.0
            self._beat_frames = np.array([], dtype=int)
            self._beat_times = np.array([], dtype=float)
            self._downbeat_times = None
            self._beat_confidence = 0.0
            self._is_analyzed = True
            return self

        try:
            # 1. Onset envelope calculation
            onset_env = librosa.onset.onset_strength(
                y=self.y,
                sr=self.sr,
                hop_length=self.hop_length
            )

            # 2. Beat tracking
            if self._tempo is None:
                tempo_arr, beat_frames = librosa.beat.beat_track(
                    onset_envelope=onset_env,
                    sr=self.sr,
                    hop_length=self.hop_length
                )
                raw_tempo = float(tempo_arr[0]) if hasattr(tempo_arr, '__len__') else float(tempo_arr)
                resolved_tempo = self._resolve_tempo_octave(onset_env, raw_tempo)
                self._tempo = resolved_tempo
                if abs(resolved_tempo - raw_tempo) > 1.0:
                    _, beat_frames = librosa.beat.beat_track(
                        onset_envelope=onset_env,
                        sr=self.sr,
                        hop_length=self.hop_length,
                        bpm=resolved_tempo
                    )
            else:
                _, beat_frames = librosa.beat.beat_track(
                    onset_envelope=onset_env,
                    sr=self.sr,
                    hop_length=self.hop_length,
                    bpm=self._tempo
                )

            self._beat_frames = beat_frames
            self._beat_times = librosa.frames_to_time(
                beat_frames,
                sr=self.sr,
                hop_length=self.hop_length
            )

            # 3. Beat confidence calculation (onset sharpness at beat positions)
            if len(beat_frames) > 1 and np.max(onset_env) > 1e-6:
                # Average onset strength at beat frames versus overall background
                valid_frames = beat_frames[beat_frames < len(onset_env)]
                if len(valid_frames) > 0:
                    beat_energy = np.mean(onset_env[valid_frames])
                    bg_energy = np.mean(onset_env)
                    ratio = beat_energy / (bg_energy + 1e-6)
                    self._beat_confidence = float(np.clip((ratio - 1.0) / 3.0, 0.0, 1.0))
                else:
                    self._beat_confidence = 0.5
            else:
                self._beat_confidence = 0.0

            # 4. Downbeat estimation based on time signature meter
            self._estimate_downbeats(onset_env)

        except Exception:
            self._tempo = 120.0
            self._beat_times = np.array([], dtype=float)
            self._downbeat_times = None
            self._beat_confidence = 0.0

        self._is_analyzed = True
        return self

    def _resolve_tempo_octave(self, onset_env: np.ndarray, raw_tempo: float) -> float:
        """
        Resolve half-time / double-time metrical octave ambiguity on raw beat_track tempo.

        Evaluates candidate tempos {T, T/2, 2*T} within [45, 200] BPM using normalized
        onset-envelope autocorrelation at 1-beat and 2-beat lags combined with a
        perceptual tempo prior centered around ~100 BPM.
        """
        if raw_tempo <= 0.0 or len(onset_env) < 32:
            return raw_tempo

        env = np.asarray(onset_env, dtype=float)
        env = env - np.mean(env)
        denom = float(np.dot(env, env))
        if denom <= 1e-9:
            return raw_tempo

        fps = float(self.sr) / float(self.hop_length)

        def _lag_corr(lag_frames: float) -> float:
            center = int(round(lag_frames))
            if center < 2 or center >= len(env) - 2:
                return 0.0
            best = 0.0
            for lag in (center - 1, center, center + 1):
                if 1 <= lag < len(env):
                    c = float(np.dot(env[:-lag], env[lag:])) / denom
                    if c > best:
                        best = c
            return max(0.0, best)

        candidates = [raw_tempo]
        if raw_tempo * 0.5 >= 48.0:
            candidates.append(raw_tempo * 0.5)
        if raw_tempo * 2.0 <= 195.0:
            candidates.append(raw_tempo * 2.0)

        best_bpm = raw_tempo
        best_score = -1.0
        for bpm in candidates:
            period = (60.0 / bpm) * fps
            ac1 = _lag_corr(period)
            ac2 = _lag_corr(2.0 * period)
            # Gentle perceptual prior peaking at 100 BPM (sigma ~0.55 octaves)
            prior = float(np.exp(-0.5 * ((np.log2(bpm / 100.0)) / 0.55) ** 2))
            pulse = 0.65 * ac1 + 0.35 * ac2
            score = pulse * (0.45 + 0.55 * prior)
            if score > best_score:
                best_score = score
                best_bpm = bpm

        return float(best_bpm)

    def _estimate_downbeats(self, onset_env: np.ndarray) -> None:
        """
        Estimates downbeats (bar boundaries) from detected beats and time signature meter.
        """
        if self._beat_times is None or len(self._beat_times) < 2:
            self._downbeat_times = None
            return

        beats_per_bar = 3 if self.time_signature == "3/4" else 4
        if len(self._beat_times) < beats_per_bar:
            self._downbeat_times = self._beat_times[:1] if len(self._beat_times) > 0 else None
            return

        # Score phase offsets (0, 1, 2, ... beats_per_bar-1) by onset energy at downbeats
        best_phase = 0
        best_score = -1.0

        for phase in range(beats_per_bar):
            candidate_indices = range(phase, len(self._beat_frames), beats_per_bar)
            candidate_frames = [self._beat_frames[i] for i in candidate_indices if self._beat_frames[i] < len(onset_env)]
            if candidate_frames:
                score = float(np.mean(onset_env[candidate_frames]))
                if score > best_score:
                    best_score = score
                    best_phase = phase

        downbeat_indices = list(range(best_phase, len(self._beat_times), beats_per_bar))
        self._downbeat_times = self._beat_times[downbeat_indices]

    def get_beats(self) -> np.ndarray:
        """Returns the array of beat timestamps in seconds."""
        if not self._is_analyzed:
            self.analyze()
        return self._beat_times if self._beat_times is not None else np.array([], dtype=float)

    def get_downbeats(self) -> Optional[np.ndarray]:
        """Returns the array of downbeat timestamps in seconds, or None if unavailable."""
        if not self._is_analyzed:
            self.analyze()
        return self._downbeat_times

    def get_tempo(self) -> float:
        """Returns the estimated tempo in BPM."""
        if not self._is_analyzed:
            self.analyze()
        return float(round(self._tempo, 1)) if self._tempo is not None else 120.0

    def get_confidence(self) -> Optional[float]:
        """Returns the beat tracking confidence score."""
        if not self._is_analyzed:
            self.analyze()
        return round(self._beat_confidence, 3) if self._beat_confidence is not None else None

    def get_timing_data(self) -> TimingData:
        """Returns the canonical TimingData model."""
        if not self._is_analyzed:
            self.analyze()
        return TimingData(
            tempo=self.get_tempo(),
            time_signature=self.time_signature,
            beat_times=[round(float(t), 3) for t in self.get_beats()],
            downbeat_times=[round(float(t), 3) for t in self.get_downbeats()] if self.get_downbeats() is not None else None,
            beat_confidence=self.get_confidence()
        )
