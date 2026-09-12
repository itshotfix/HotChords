"""
backend/analysis/instrument_evidence.py

Objective Instrument Evidence Analysis for HotChords.
Evaluates spectral and temporal characteristics across candidate sources and stems
to estimate instrument presence without fabricating unmeasured instrument labels.
"""

from typing import Dict, Optional, Any
import numpy as np
import librosa
from backend.models.analysis_types import InstrumentEvidence


STANDARD_INSTRUMENT_TARGETS = [
    "piano",
    "guitar",
    "bass",
    "synthesizer",
    "strings",
    "organ",
    "drums",
    "vocals"
]


def classify_source_timbre(y: np.ndarray, sr: int = 22050, source_hint: Optional[str] = None) -> tuple[Optional[str], Optional[float]]:
    """
    Estimates likely instrument family from acoustic spectral properties and stem hint.
    
    Parameters
    ----------
    y : np.ndarray
        Mono audio signal.
    sr : int
        Sample rate.
    source_hint : str, optional
        Stem identifier ('bass', 'other', 'drums', 'vocals', 'mix').

    Returns
    -------
    tuple[Optional[str], Optional[float]]
        (inferred_instrument, confidence)
        Returns (None, None) or ("uncertain", None) if evidence is inconclusive.
    """
    if y is None or len(y) < sr * 0.2:
        return None, None

    try:
        # 1. Evaluate RMS energy
        rms = librosa.feature.rms(y=y)[0]
        if np.mean(rms) < 0.005:
            return None, None

        # 2. Spectral Centroid and Rolloff
        cent = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        mean_cent = float(np.mean(cent))

        rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, roll_percent=0.85)[0]
        mean_rolloff = float(np.mean(rolloff))

        # 3. Harmonic vs Percussive ratio
        y_harm, y_perc = librosa.effects.hpss(y, margin=2.5)
        e_harm = float(np.sum(y_harm**2))
        e_perc = float(np.sum(y_perc**2))
        e_total = e_harm + e_perc + 1e-12
        harm_ratio = e_harm / e_total

        # 4. Spectral Flatness (Wiener entropy)
        flatness = float(np.mean(librosa.feature.spectral_flatness(y=y_harm)))

        # Rule-based acoustic MIR evidence evaluation
        # A. Bass Stem / Low Frequency dominance
        if source_hint == "bass" or (mean_cent < 400 and mean_rolloff < 800 and harm_ratio > 0.4):
            conf = min(0.95, max(0.60, float(0.5 + 0.5 * harm_ratio * (1.0 - min(mean_cent / 500.0, 1.0)))))
            return "bass", round(conf, 3)

        # B. Drums / Percussion
        if source_hint == "drums" or (harm_ratio < 0.30 and mean_cent > 1500):
            conf = min(0.95, max(0.60, float(1.0 - harm_ratio)))
            return "drums", round(conf, 3)

        # C. Vocals
        if source_hint == "vocals":
            conf = min(0.92, max(0.60, float(harm_ratio * (1.0 - flatness))))
            return "vocals", round(conf, 3)

        # D. Harmonic Stems ('other' or 'mix' with high harmonic energy)
        if harm_ratio > 0.60 and flatness < 0.15:
            # Check envelope decay: Piano exhibits sharp onset followed by smooth decay;
            # Synth/Organ exhibits sustained flat envelope; Guitar exhibits pluck onset.
            onset_env = librosa.onset.onset_strength(y=y_harm, sr=sr)
            mean_onset = float(np.mean(onset_env))
            
            # Check spectral bandwidth
            spec_bw = float(np.mean(librosa.feature.spectral_bandwidth(y=y_harm, sr=sr)))

            if mean_cent > 1200 and spec_bw > 1500:
                if mean_onset > 0.6:
                    return "guitar", round(min(0.88, float(0.55 + 0.3 * harm_ratio)), 3)
                else:
                    return "synthesizer", round(min(0.85, float(0.50 + 0.3 * harm_ratio)), 3)
            elif mean_cent >= 500 and mean_cent <= 1800:
                return "piano", round(min(0.88, float(0.55 + 0.3 * harm_ratio)), 3)
            else:
                return "harmonic_mix", round(min(0.85, float(0.50 + 0.3 * harm_ratio)), 3)

        return None, None

    except Exception:
        return None, None


def build_instrument_evidence_registry(
    sources: Optional[Dict[str, np.ndarray]] = None,
    sr: int = 22050
) -> Dict[str, InstrumentEvidence]:
    """
    Builds the instrument evidence registry from active audio signals.
    Unclassified or absent instruments are explicitly marked is_available=False with confidence=None.
    """
    registry = {}
    
    # Initialize all standard targets as unavailable
    for inst in STANDARD_INSTRUMENT_TARGETS:
        registry[inst] = InstrumentEvidence(
            instrument=inst,
            confidence=None,
            source=None,
            isAvailable=False
        )

    if not sources:
        return registry

    for src_name, y_sig in sources.items():
        if y_sig is None or len(y_sig) == 0:
            continue
        
        inst_name, conf = classify_source_timbre(y_sig, sr=sr, source_hint=src_name)
        if inst_name and conf is not None:
            # Map into target key
            target_key = inst_name
            if target_key in registry:
                registry[target_key] = InstrumentEvidence(
                    instrument=target_key,
                    confidence=conf,
                    source=src_name,
                    isAvailable=True
                )
            else:
                # Custom harmonic instrument family
                registry[target_key] = InstrumentEvidence(
                    instrument=target_key,
                    confidence=conf,
                    source=src_name,
                    isAvailable=True
                )

    return registry


def build_unclassified_instrument_registry() -> Dict[str, InstrumentEvidence]:
    """Backward compatible builder for empty/unclassified instrument registry."""
    return build_instrument_evidence_registry(sources=None)
