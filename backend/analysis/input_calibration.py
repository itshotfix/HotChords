"""
backend/analysis/input_calibration.py

Microphone Input Calibration & Signal Quality Engine for HotChords (Phase 12).

Principles & Architectural Rules:
1. Pure Observation & Calibration: Does not mutate SongTimeline or canonical song analysis.
2. In-Memory Transient Processing: Zero raw audio saved to disk; metadata-only profiling.
3. Robust Noise Floor Estimation: Computes median/percentile RMS and Wiener entropy (spectral flatness)
   over a short calibration window to derive an environment-specific noise gate.
4. Granular Signal Quality Classification:
   - CALIBRATING: Calibration window in progress.
   - READY: Calibrated successfully.
   - GOOD_SIGNAL: Piano audio clearly above noise floor with low inharmonic flatness (<0.12).
   - WEAK_SIGNAL: Signal detected but close to noise floor (<3 dB above noise).
   - NOISE: Ambient room noise / fan / speech detected (SFM > 0.15).
   - CLIPPING: Digital peak overload (>0.98 amplitude or >2% clipped samples).
   - LOW_CONFIDENCE: Unclear SNR or unsteady acoustic energy.
5. Relative Signal Energy: Exposes normalized signal level [0.0, 1.0] without claiming physical MIDI key velocity.
"""

import time
from enum import Enum
from typing import List, Dict, Optional, Any, Tuple
import numpy as np
from pydantic import BaseModel, Field, ConfigDict
from scipy.signal.windows import blackmanharris


class SignalQualityState(str, Enum):
    CALIBRATING = "CALIBRATING"
    READY = "READY"
    GOOD_SIGNAL = "GOOD_SIGNAL"
    WEAK_SIGNAL = "WEAK_SIGNAL"
    NOISE = "NOISE"
    CLIPPING = "CLIPPING"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"


class PracticeInputProfile(BaseModel):
    """Safe, serializable metadata-only profile representing the acoustic practice input environment."""
    sample_rate: int = Field(default=22050, alias="sampleRate")
    noise_floor_rms: float = Field(default=0.005, alias="noiseFloorRms")
    noise_gate_rms: float = Field(default=0.012, alias="noiseGateRms")
    peak_level: float = Field(default=0.0, alias="peakLevel")
    dynamic_range_db: float = Field(default=0.0, alias="dynamicRangeDb")
    clipping_ratio: float = Field(default=0.0, alias="clippingRatio")
    spectral_flatness: float = Field(default=0.0, alias="spectralFlatness")
    signal_quality: SignalQualityState = Field(default=SignalQualityState.READY, alias="signalQuality")
    calibration_timestamp: float = Field(default_factory=time.time, alias="calibrationTimestamp")
    frames_evaluated: int = Field(default=0, alias="framesEvaluated")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


def compute_spectral_flatness(frame: np.ndarray, n_fft: int = 2048) -> float:
    """Compute spectral flatness (Wiener entropy) of an audio frame."""
    if len(frame) < n_fft:
        pad = np.zeros(n_fft, dtype=np.float32)
        pad[:len(frame)] = frame
        frame = pad
    else:
        frame = frame[:n_fft]

    window = blackmanharris(len(frame)).astype(np.float32)
    spec = np.abs(np.fft.rfft(frame * window))
    power = spec ** 2 + 1e-12
    
    geom_mean = np.exp(np.mean(np.log(power)))
    arith_mean = np.mean(power)
    if arith_mean <= 1e-12:
        return 0.0
    return float(np.clip(geom_mean / arith_mean, 0.0, 1.0))


class InputCalibrator:
    """
    Transient In-Memory Audio Input Calibrator.
    Evaluates ambient room noise over a short calibration period to derive dynamic noise gates and quality thresholds.
    """

    def __init__(self, sample_rate: int = 22050, default_noise_gate: float = 0.010):
        self.sample_rate = sample_rate
        self.default_noise_gate = default_noise_gate
        self.is_calibrating = False
        self.calibration_start_time = 0.0
        self.calibration_duration_s = 2.0
        
        # Transient frame statistics (cleared on finish/reset)
        self.rms_values: List[float] = []
        self.peak_values: List[float] = []
        self.flatness_values: List[float] = []
        self.clipping_counts: List[int] = []
        self.total_samples = 0

        # Cached active profile
        self.profile: Optional[PracticeInputProfile] = None

    def start_calibration(self, duration_seconds: float = 2.0) -> None:
        """Start a new calibration session."""
        self.reset_calibration()
        self.is_calibrating = True
        self.calibration_duration_s = max(0.5, min(10.0, float(duration_seconds)))
        self.calibration_start_time = time.perf_counter()

    def process_calibration_frame(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        Process a single calibration audio frame.
        """
        if not self.is_calibrating:
            return {"status": "NOT_CALIBRATING", "progress": 1.0}

        frame = np.asarray(frame, dtype=np.float32)
        n_samp = len(frame)
        if n_samp == 0:
            return {"status": "EMPTY_FRAME", "progress": 0.0}

        rms = float(np.sqrt(np.mean(frame ** 2) + 1e-12))
        peak = float(np.max(np.abs(frame)))
        flatness = compute_spectral_flatness(frame)
        n_clipped = int(np.sum(np.abs(frame) >= 0.98))

        self.rms_values.append(rms)
        self.peak_values.append(peak)
        self.flatness_values.append(flatness)
        self.clipping_counts.append(n_clipped)
        self.total_samples += n_samp

        elapsed = time.perf_counter() - self.calibration_start_time
        progress = min(1.0, elapsed / self.calibration_duration_s)

        if progress >= 1.0:
            self.finish_calibration()

        return {
            "status": "CALIBRATING",
            "progress": round(progress, 2),
            "rms": round(rms, 5),
            "peak": round(peak, 4),
            "flatness": round(flatness, 4),
            "isComplete": not self.is_calibrating,
        }

    def finish_calibration(self) -> PracticeInputProfile:
        """
        Finalize calibration and derive the PracticeInputProfile.
        """
        self.is_calibrating = False

        if not self.rms_values:
            # Fallback default profile
            self.profile = PracticeInputProfile(
                sampleRate=self.sample_rate,
                noiseFloorRms=0.005,
                noiseGateRms=self.default_noise_gate,
                peakLevel=0.0,
                dynamicRangeDb=40.0,
                clippingRatio=0.0,
                spectralFlatness=0.05,
                signalQuality=SignalQualityState.READY,
                calibrationTimestamp=time.time(),
                framesEvaluated=0,
            )
            return self.profile

        # Robust statistics
        noise_floor_rms = float(np.median(self.rms_values))
        p90_rms = float(np.percentile(self.rms_values, 90))
        peak_level = float(np.max(self.peak_values))
        median_flatness = float(np.median(self.flatness_values))
        
        total_clips = sum(self.clipping_counts)
        clipping_ratio = float(total_clips / max(1, self.total_samples))

        # Derive dynamic noise gate (2.2x median noise floor or 1.3x p90 noise floor)
        noise_gate_rms = max(0.004, min(0.08, float(max(noise_floor_rms * 2.2, p90_rms * 1.3))))

        # Dynamic range estimation (peak / noise floor)
        if noise_floor_rms > 1e-6 and peak_level > noise_floor_rms:
            dynamic_range_db = float(20.0 * np.log10(max(1.0, peak_level) / noise_floor_rms))
        else:
            dynamic_range_db = 40.0

        # Determine overall calibrated quality
        if clipping_ratio > 0.05:
            quality = SignalQualityState.CLIPPING
        elif noise_floor_rms > 0.04 and median_flatness > 0.25:
            quality = SignalQualityState.NOISE
        elif noise_floor_rms > 0.06:
            quality = SignalQualityState.NOISE
        else:
            quality = SignalQualityState.READY

        self.profile = PracticeInputProfile(
            sampleRate=self.sample_rate,
            noiseFloorRms=round(noise_floor_rms, 5),
            noiseGateRms=round(noise_gate_rms, 5),
            peakLevel=round(peak_level, 4),
            dynamicRangeDb=round(dynamic_range_db, 1),
            clippingRatio=round(clipping_ratio, 5),
            spectralFlatness=round(median_flatness, 4),
            signalQuality=quality,
            calibrationTimestamp=time.time(),
            framesEvaluated=len(self.rms_values),
        )

        # Clear transient arrays to maintain zero persistent storage
        self.rms_values.clear()
        self.peak_values.clear()
        self.flatness_values.clear()
        self.clipping_counts.clear()

        return self.profile

    def reset_calibration(self) -> None:
        """Reset all calibration state."""
        self.is_calibrating = False
        self.calibration_start_time = 0.0
        self.rms_values.clear()
        self.peak_values.clear()
        self.flatness_values.clear()
        self.clipping_counts.clear()
        self.total_samples = 0
        self.profile = None

    def classify_signal(
        self,
        frame: np.ndarray,
        profile: Optional[PracticeInputProfile] = None,
    ) -> Dict[str, Any]:
        """
        Classify the real-time acoustic signal quality of an active audio frame.
        """
        active_prof = profile or self.profile
        noise_gate = active_prof.noise_gate_rms if active_prof else self.default_noise_gate
        noise_floor = active_prof.noise_floor_rms if active_prof else 0.005

        frame = np.asarray(frame, dtype=np.float32)
        if len(frame) == 0:
            return {
                "qualityState": SignalQualityState.LOW_CONFIDENCE.value,
                "rms": 0.0,
                "peak": 0.0,
                "signalLevel": 0.0,
                "isPlayable": False,
            }

        rms = float(np.sqrt(np.mean(frame ** 2) + 1e-12))
        peak = float(np.max(np.abs(frame)))
        n_clipped = int(np.sum(np.abs(frame) >= 0.98))
        clip_ratio = n_clipped / len(frame)

        # Relative signal energy / loudness level [0.0, 1.0]
        signal_level = float(np.clip(peak / 0.85, 0.0, 1.0))

        # Check CLIPPING
        if peak >= 0.98 or clip_ratio >= 0.02:
            return {
                "qualityState": SignalQualityState.CLIPPING.value,
                "rms": round(rms, 5),
                "peak": round(peak, 4),
                "signalLevel": signal_level,
                "isPlayable": False,
                "reason": "Microphone signal overloaded/clipping.",
            }

        # Check NOISE (inharmonic Wiener entropy)
        flatness = compute_spectral_flatness(frame)
        if flatness > 0.18 and rms > noise_gate:
            return {
                "qualityState": SignalQualityState.NOISE.value,
                "rms": round(rms, 5),
                "peak": round(peak, 4),
                "signalLevel": signal_level,
                "isPlayable": False,
                "reason": "Excessive ambient room noise / inharmonic sound.",
            }

        # Check WEAK_SIGNAL
        if rms < noise_gate:
            if rms > noise_floor * 1.1:
                state = SignalQualityState.WEAK_SIGNAL
            else:
                state = SignalQualityState.LOW_CONFIDENCE
            return {
                "qualityState": state.value,
                "rms": round(rms, 5),
                "peak": round(peak, 4),
                "signalLevel": signal_level,
                "isPlayable": False,
                "reason": "Signal below noise gate threshold.",
            }

        # Clean GOOD_SIGNAL
        return {
            "qualityState": SignalQualityState.GOOD_SIGNAL.value,
            "rms": round(rms, 5),
            "peak": round(peak, 4),
            "signalLevel": signal_level,
            "isPlayable": True,
            "reason": "Clear acoustic signal.",
        }
