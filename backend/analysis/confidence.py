"""
backend/analysis/confidence.py

Confidence & Reliability Evaluation Engine for HotChords.
Evaluates multi-dimensional reliability indicators (harmonic strength,
temporal stability, beat alignment) without arbitrary claims of ground-truth accuracy.
"""

from typing import List, Dict, Any, Optional
import numpy as np
from backend.models.analysis_types import DetectionReliability, AudioProfile


def evaluate_temporal_stability(chords: List[Dict[str, Any]]) -> Optional[float]:
    """
    Evaluates temporal chord stability based on the average duration of contiguous chord blocks.
    
    In real songs, chords typically sustain over 1 to 4 beats (e.g., 1.0 to 4.0 seconds).
    Rapid fluttering (e.g., jittering every 0.1 - 0.3s) is heavily penalized.
    """
    if not chords:
        return 0.0
    if len(chords) == 1:
        return 1.0

    # Calculate durations of distinct contiguous chord blocks
    blocks = []
    current_chord = None
    block_start = 0.0
    block_end = 0.0

    for c in chords:
        name = c.get("chord", c.get("chordName", "N"))
        t0 = float(c.get("time", c.get("startTime", 0.0)))
        t1 = float(c.get("end", c.get("endTime", t0 + 0.5)))
        if current_chord is None:
            current_chord = name
            block_start = t0
            block_end = t1
        elif name == current_chord:
            block_end = t1
        else:
            blocks.append((current_chord, max(0.01, block_end - block_start)))
            current_chord = name
            block_start = t0
            block_end = t1
    if current_chord is not None:
        blocks.append((current_chord, max(0.01, block_end - block_start)))

    if not blocks:
        return 1.0

    durations = [d for _, d in blocks]
    avg_duration = float(np.mean(durations))

    # Chords averaging >= 1.5s -> stability = 1.0
    # Chords averaging <= 0.2s -> stability = 0.1
    if avg_duration >= 1.5:
        stability = 1.0
    elif avg_duration <= 0.2:
        stability = 0.1
    else:
        stability = 0.1 + 0.9 * ((avg_duration - 0.2) / 1.3)

    return float(np.clip(stability, 0.0, 1.0))


def evaluate_harmonic_strength(profile: Optional[AudioProfile]) -> Optional[float]:
    """
    Evaluates harmonic strength from the AudioProfile.
    Combines harmonic energy ratio, inverse spectral flatness, and inverse chroma entropy.
    """
    if profile is None:
        return None

    # High harmonic energy -> high score
    h_score = float(profile.harmonic_energy)
    # Low spectral flatness (tonal) -> high score
    f_score = float(1.0 - profile.spectral_flatness)
    # Low chroma entropy (focused pitch classes) -> high score
    e_score = float(1.0 - profile.chroma_entropy)

    combined = (0.4 * h_score) + (0.3 * f_score) + (0.3 * e_score)
    return float(np.clip(combined, 0.0, 1.0))


def evaluate_detection_reliability(
    profile: Optional[AudioProfile],
    chords: List[Dict[str, Any]],
    beat_confidence: Optional[float] = None,
    source_agreement: Optional[float] = None
) -> DetectionReliability:
    """
    Synthesizes measurable reliability indicators into DetectionReliability.
    Incorporates source_agreement when multi-candidate separation is active.
    """
    if not chords:
        return DetectionReliability(
            overall=0.0,
            harmonicStrength=0.0,
            temporalStability=0.0,
            beatAlignment=0.0,
            sourceAgreement=round(source_agreement, 3) if source_agreement is not None else None,
            engineAgreement=None
        )

    harm_strength = evaluate_harmonic_strength(profile)
    temp_stability = evaluate_temporal_stability(chords)
    beat_alignment = float(beat_confidence) if beat_confidence is not None else 0.5

    # Compute overall weighted reliability from active measurable components
    weights = []
    scores = []

    if source_agreement is not None:
        if harm_strength is not None:
            scores.append(harm_strength)
            weights.append(0.35)
        if temp_stability is not None:
            scores.append(temp_stability)
            weights.append(0.25)
        if beat_alignment is not None:
            scores.append(beat_alignment)
            weights.append(0.15)
        scores.append(source_agreement)
        weights.append(0.25)
    else:
        if harm_strength is not None:
            scores.append(harm_strength)
            weights.append(0.45)
        if temp_stability is not None:
            scores.append(temp_stability)
            weights.append(0.35)
        if beat_alignment is not None:
            scores.append(beat_alignment)
            weights.append(0.20)

    if weights:
        overall = float(np.sum(np.array(scores) * np.array(weights)) / np.sum(weights))
        overall = float(np.clip(overall, 0.0, 1.0))
    else:
        overall = None

    return DetectionReliability(
        overall=round(overall, 3) if overall is not None else None,
        harmonicStrength=round(harm_strength, 3) if harm_strength is not None else None,
        temporalStability=round(temp_stability, 3) if temp_stability is not None else None,
        beatAlignment=round(beat_alignment, 3) if beat_alignment is not None else None,
        sourceAgreement=round(source_agreement, 3) if source_agreement is not None else None,
        engineAgreement=None
    )
