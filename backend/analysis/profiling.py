"""
backend/analysis/profiling.py

Audio Quality & Song Profiling Component for HotChords.
Calculates objective acoustic and MIR features without arbitrary pseudo-percentages,
and classifies the physical/harmonic status of the audio signal.
"""

import numpy as np
import librosa
from scipy.stats import entropy
from backend.models.analysis_types import AudioProfile, AudioStatus


def compute_chunked_hpss(
    y: np.ndarray,
    sr: int,
    margin: float = 3.0,
    chunk_sec: float = 30.0
) -> tuple[np.ndarray, np.ndarray]:
    """
    Memory-safe Harmonic-Percussive Source Separation (HPSS) using chunked STFT processing.
    Avoids runaway memory allocation on long audio (>60s) by computing 2D median filters
    over localized 30s overlapping windows with linear crossfading.
    """
    if y is None or len(y) == 0:
        return np.array([]), np.array([])
        
    chunk_len = int(chunk_sec * sr)
    if len(y) <= chunk_len:
        return librosa.effects.hpss(y, margin=margin)

    overlap = int(1.0 * sr)  # 1-second crossfade
    step = max(1, chunk_len - overlap)
    
    y_harm = np.zeros_like(y, dtype=np.float32)
    y_perc = np.zeros_like(y, dtype=np.float32)
    weight = np.zeros_like(y, dtype=np.float32)
    
    fade_in = np.linspace(0.0, 1.0, overlap, dtype=np.float32)
    fade_out = np.linspace(1.0, 0.0, overlap, dtype=np.float32)
    
    for start in range(0, len(y), step):
        end = min(start + chunk_len, len(y))
        y_chunk = y[start:end]
        if len(y_chunk) < int(sr * 0.1):
            break
            
        h_c, p_c = librosa.effects.hpss(y_chunk, margin=margin)
        
        w = np.ones(len(y_chunk), dtype=np.float32)
        if start > 0 and len(w) >= overlap:
            w[:overlap] *= fade_in
        if end < len(y) and len(w) >= overlap:
            w[-overlap:] *= fade_out
            
        y_harm[start:end] += (h_c * w).astype(np.float32)
        y_perc[start:end] += (p_c * w).astype(np.float32)
        weight[start:end] += w
        
    weight = np.maximum(weight, 1e-6)
    y_harm /= weight
    y_perc /= weight
    return y_harm, y_perc


def compute_chroma_entropy(chroma: np.ndarray) -> float:
    """
    Computes the normalized Shannon entropy of a 12-bin chroma representation.
    
    A perfectly focused single pitch class yields an entropy of 0.0.
    A uniform distribution (such as flat white noise) yields an entropy of 1.0.
    """
    if chroma.size == 0:
        return 1.0
        
    chroma_mean = np.mean(chroma, axis=1) if chroma.ndim > 1 else chroma
    sum_val = np.sum(chroma_mean)
    if sum_val <= 1e-9:
        return 1.0
        
    p = chroma_mean / sum_val
    # Add tiny epsilon to prevent log(0)
    p = np.clip(p, 1e-12, 1.0)
    p = p / np.sum(p)
    
    raw_entropy = entropy(p, base=np.e)
    max_entropy = np.log(12.0)  # Maximum possible entropy for 12 uniform bins
    
    normalized_entropy = float(raw_entropy / max_entropy)
    return float(np.clip(normalized_entropy, 0.0, 1.0))


def compute_beat_confidence(y: np.ndarray, sr: int, hop_length: int = 512) -> float:
    """
    Computes an objective beat tracking clarity/periodicity confidence score [0.0, 1.0]
    based on the prominence of the autocorrelation peak of the onset envelope.
    """
    try:
        if len(y) < sr * 0.5:  # Less than 0.5s
            return 0.0
            
        onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)
        if np.max(onset_env) <= 1e-6:
            return 0.0
            
        # Autocorrelation of onset strength
        max_size = int(sr * 3.0 / hop_length)  # up to 3 seconds periodicity
        if len(onset_env) <= max_size:
            max_size = len(onset_env) - 1
            
        if max_size <= 10:
            return 0.0
            
        ac = librosa.autocorrelate(onset_env, max_size=max_size)
        
        # Zero out zero-lag and immediate vicinity (< 0.25s / ~240 BPM limit)
        min_lag = int(0.25 * sr / hop_length)
        if min_lag < len(ac):
            ac_search = ac[min_lag:]
            if len(ac_search) > 0 and ac[0] > 0:
                peak_val = np.max(ac_search)
                conf = peak_val / (ac[0] + 1e-9)
                return float(np.clip(conf, 0.0, 1.0))
        return 0.0
    except Exception:
        return 0.0


def profile_audio(
    y: np.ndarray,
    sr: int,
    channels: int = 1,
    hop_length: int = 512
) -> tuple[AudioProfile, AudioStatus, str]:
    """
    Analyzes an audio waveform and produces an objective AudioProfile
    and an explicit AudioStatus classification.

    Parameters
    ----------
    y : np.ndarray
        Mono or stereo audio waveform array.
    sr : int
        Sample rate in Hz.
    channels : int
        Channel count (1=mono, 2=stereo).
    hop_length : int
        Hop length for STFT and feature extraction.

    Returns
    -------
    tuple[AudioProfile, AudioStatus, str]
        (profile, status, status_diagnostic_message)
    """
    # Guard 1: Empty or non-array input
    if y is None or not isinstance(y, np.ndarray) or y.size == 0:
        profile = AudioProfile(
            duration=0.0,
            sample_rate=sr,
            channels=channels,
            rms=0.0,
            silence_ratio=1.0,
            clipping_ratio=0.0,
            harmonic_energy=0.0,
            pitch_activity=0.0,
            spectral_flatness=1.0,
            chroma_strength=0.0,
            chroma_entropy=1.0,
            beat_confidence=0.0,
        )
        return profile, AudioStatus.EMPTY_AUDIO, "Audio signal is empty or contains no samples."

    # If multidimensional, convert to 1D mono for MIR extraction while noting channels
    if y.ndim > 1:
        if y.shape[0] <= 2 and y.shape[1] > y.shape[0]:
            channels = y.shape[0]
            y_mono = np.mean(y, axis=0)
        else:
            channels = y.shape[1]
            y_mono = np.mean(y, axis=1)
    else:
        y_mono = y

    n_samples = len(y_mono)
    duration = float(n_samples / sr)

    # Guard 2: Extremely short audio (< 0.1s)
    if duration < 0.1:
        profile = AudioProfile(
            duration=round(duration, 3),
            sample_rate=sr,
            channels=channels,
            rms=float(np.sqrt(np.mean(y_mono**2))),
            silence_ratio=1.0,
            clipping_ratio=0.0,
            harmonic_energy=0.0,
            pitch_activity=0.0,
            spectral_flatness=1.0,
            chroma_strength=0.0,
            chroma_entropy=1.0,
            beat_confidence=0.0,
        )
        return profile, AudioStatus.UNSUPPORTED_AUDIO, f"Audio duration ({duration:.2f}s) is too short for harmonic analysis."

    # 1. Physical Loudness & Saturation
    rms_global = float(np.sqrt(np.mean(y_mono**2)))
    clipping_ratio = float(np.mean(np.abs(y_mono) >= 0.999))

    # Frame-wise RMS for silence ratio (-60 dBFS threshold ≈ 0.001 linear amplitude)
    frame_length = min(2048, n_samples)
    rms_frames = librosa.feature.rms(y=y_mono, frame_length=frame_length, hop_length=hop_length)[0]
    silence_threshold = 0.001  # -60 dBFS
    silence_ratio = float(np.mean(rms_frames < silence_threshold)) if len(rms_frames) > 0 else 1.0

    # Guard 3: Completely silent audio
    if rms_global < 1e-5 or silence_ratio >= 0.99:
        profile = AudioProfile(
            duration=round(duration, 3),
            sample_rate=sr,
            channels=channels,
            rms=round(rms_global, 6),
            silence_ratio=round(silence_ratio, 4),
            clipping_ratio=round(clipping_ratio, 6),
            harmonic_energy=0.0,
            pitch_activity=0.0,
            spectral_flatness=1.0,
            chroma_strength=0.0,
            chroma_entropy=1.0,
            beat_confidence=0.0,
        )
        return profile, AudioStatus.EMPTY_AUDIO, "Audio signal is silent (RMS energy below threshold)."

    # 2. Memory-Safe Chunked HPSS & Harmonic Energy Decomposition
    try:
        y_harm, y_perc = compute_chunked_hpss(y_mono, sr=sr, margin=3.0, chunk_sec=30.0)
        e_harm = np.sum(y_harm**2)
        e_perc = np.sum(y_perc**2)
        e_total = e_harm + e_perc + 1e-12
        harmonic_energy_ratio = float(e_harm / e_total)
    except Exception:
        y_harm = y_mono
        harmonic_energy_ratio = 0.5

    # 3. Spectral Flatness (Wiener entropy)
    try:
        flatness_frames = librosa.feature.spectral_flatness(y=y_mono, hop_length=hop_length)[0]
        spectral_flatness = float(np.mean(flatness_frames)) if len(flatness_frames) > 0 else 0.5
    except Exception:
        spectral_flatness = 0.5

    # 4. Chroma & Pitch Class Characteristics
    try:
        # CQT Chroma
        chroma = librosa.feature.chroma_cqt(
            y=y_harm,
            sr=sr,
            hop_length=hop_length,
            bins_per_octave=36
        )
        # Chroma strength: peak-to-average contrast across the 12 pitch classes
        chroma_mean = np.mean(chroma, axis=1)
        max_c = np.max(chroma_mean)
        min_c = np.min(chroma_mean)
        chroma_strength = float(max_c - min_c) if max_c > 0 else 0.0
        
        # Chroma entropy
        chroma_entropy = compute_chroma_entropy(chroma)
    except Exception:
        chroma_strength = 0.0
        chroma_entropy = 1.0

    # 5. Pitch Activity (proportion of frames with prominent pitch energy)
    try:
        # Energy in harmonic component per frame relative to threshold
        harm_rms = librosa.feature.rms(y=y_harm, frame_length=frame_length, hop_length=hop_length)[0]
        pitch_activity = float(np.mean(harm_rms > silence_threshold)) if len(harm_rms) > 0 else 0.0
    except Exception:
        pitch_activity = 0.5

    # 6. Beat Confidence
    beat_conf = compute_beat_confidence(y_mono, sr, hop_length=hop_length)

    profile = AudioProfile(
        duration=round(duration, 3),
        sample_rate=int(sr),
        channels=int(channels),
        rms=round(rms_global, 5),
        silence_ratio=round(silence_ratio, 4),
        clipping_ratio=round(clipping_ratio, 5),
        harmonic_energy=round(harmonic_energy_ratio, 4),
        pitch_activity=round(pitch_activity, 4),
        spectral_flatness=round(spectral_flatness, 4),
        chroma_strength=round(chroma_strength, 4),
        chroma_entropy=round(chroma_entropy, 4),
        beat_confidence=round(beat_conf, 4),
    )

    # 7. Classification of Audio Status
    # Case A: Non-tonal / noise / no harmonic content
    if (harmonic_energy_ratio < 0.08 and spectral_flatness > 0.40) or (chroma_entropy > 0.96 and harmonic_energy_ratio < 0.12):
        status = AudioStatus.NO_HARMONIC_CONTENT
        msg = "Audio contains insufficient tonal or harmonic content (predominantly noise or percussive transients)."
    # Case B: Weak harmonic evidence
    elif harmonic_energy_ratio < 0.18 or pitch_activity < 0.10 or chroma_entropy > 0.92 or chroma_strength < 0.05:
        status = AudioStatus.LOW_CONFIDENCE
        msg = "Audio exhibits weak or dispersed harmonic structure; chord detection confidence is low."
    # Case C: Robust harmonic song
    else:
        status = AudioStatus.SUCCESS
        msg = "Audio exhibits strong harmonic evidence and distinct pitch classes."

    return profile, status, msg
