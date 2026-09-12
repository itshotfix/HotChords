"""
backend/analysis/harmonic_evidence.py

Harmonic Evidence Router & Multi-Source Selection Engine for HotChords.
Dynamically registers candidate audio sources (Original Mix, HPSS Harmonic, Stems),
computes objective spectral/chroma evidence metrics, filters non-harmonic sources,
runs multi-source chord recognition, and selects the best evidence with explainable reasoning.
"""

import os
from typing import Dict, List, Optional, Any, Tuple
import logging
import numpy as np
import librosa

from backend.models.analysis_types import (
    CandidateSourceEvidence,
    SourceSelectionResult,
    AudioStatus,
    TimingData
)
from backend.analysis.profiling import compute_chunked_hpss
from backend.analysis.source_agreement import compute_source_agreement, fuse_bass_evidence

logger = logging.getLogger(__name__)


class HarmonicEvidenceRouter:
    """
    Multi-source Harmonic Evidence Router and Selection Engine.
    
    Evaluates candidate audio sources (Mix, HPSS Harmonic, Other/Harmonic Stem, Bass Stem),
    computes objective harmonic metrics, filters unsuitable candidates (vocals, drums, silence),
    orchestrates chord recognition on qualified candidates, and selects the optimal progression.
    """

    EXCLUDED_STEMS = {"drums", "vocals"}

    def __init__(self, sr: int = 22050, hop_length: int = 512):
        self.sr = sr
        self.hop_length = hop_length
        self._sources: Dict[str, np.ndarray] = {}
        self._source_paths: Dict[str, str] = {}
        self._evidence: Dict[str, CandidateSourceEvidence] = {}
        self._chord_results: Dict[str, List[Dict[str, Any]]] = {}
        self._source_confidences: Dict[str, float] = {}

    def register_source(
        self,
        source_name: str,
        y: Optional[np.ndarray] = None,
        audio_path: Optional[str] = None
    ) -> "HarmonicEvidenceRouter":
        """Registers a candidate audio waveform and/or path."""
        if y is not None and isinstance(y, np.ndarray) and y.size > 0:
            if y.ndim > 1:
                y = np.mean(y, axis=0) if y.shape[0] <= 2 else np.mean(y, axis=1)
            self._sources[source_name] = y
        if audio_path:
            self._source_paths[source_name] = audio_path
        return self

    def extract_evidence(self) -> Dict[str, CandidateSourceEvidence]:
        """
        Computes objective harmonic and spectral metrics across registered candidate sources.
        Uses memory-safe chunked HPSS and avoids redundant HPSS on already separated stems.
        """
        self._evidence = {}

        for source_name, y in self._sources.items():
            if len(y) < self.sr * 0.1:
                self._evidence[source_name] = CandidateSourceEvidence(
                    sourceName=source_name,
                    sourceType="stem" if source_name in ["bass", "other", "drums", "vocals", "inst"] else "mix",
                    isAvailable=False,
                    rejectionReason="Audio duration too short or empty"
                )
                continue

            try:
                # 1. Harmonic Energy Ratio via Chunked HPSS or Stem Prior
                if source_name in ["harmonic_hpss", "other", "bass", "guitar", "piano"]:
                    y_harm = y
                    harm_ratio = 0.95 if source_name != "bass" else 0.85
                elif source_name in ["drums", "vocals"]:
                    y_harm = y
                    harm_ratio = 0.05 if source_name == "drums" else 0.40
                else:
                    # 'mix' or 'inst': run memory-safe chunked HPSS
                    y_harm, y_perc = compute_chunked_hpss(y, sr=self.sr, margin=3.0, chunk_sec=30.0)
                    e_harm = float(np.sum(y_harm**2))
                    e_perc = float(np.sum(y_perc**2))
                    e_total = e_harm + e_perc + 1e-12
                    harm_ratio = float(np.clip(e_harm / e_total, 0.0, 1.0))

                # 2. Chroma Prominence & Entropy
                chroma = librosa.feature.chroma_cqt(
                    y=y_harm,
                    sr=self.sr,
                    hop_length=self.hop_length,
                    bins_per_octave=36
                )
                chroma_mean = np.mean(chroma, axis=1)
                max_c = float(np.max(chroma_mean))
                min_c = float(np.min(chroma_mean))
                chroma_strength = float(max_c - min_c) if max_c > 0 else 0.0

                # Shannon entropy of normalized chroma distribution
                c_sum = np.sum(chroma_mean)
                if c_sum > 1e-9:
                    p = chroma_mean / c_sum
                    entropy = -float(np.sum([pi * np.log2(pi) for pi in p if pi > 1e-12]))
                    norm_entropy = float(np.clip(entropy / np.log2(12.0), 0.0, 1.0))
                else:
                    norm_entropy = 1.0

                # 3. Spectral Flatness (Wiener entropy: 0=pure tone, 1=white noise)
                flatness = float(np.mean(librosa.feature.spectral_flatness(y=y_harm)))
                flatness = float(np.clip(flatness, 0.0, 1.0))

                # 4. Pitch Activity (Frames with significant harmonic RMS)
                frame_rms = librosa.feature.rms(y=y_harm, hop_length=self.hop_length)[0]
                pitch_act = float(np.mean(frame_rms > 0.001)) if len(frame_rms) > 0 else 0.0

                # 5. Temporal Stability (Chroma correlation across adjacent frames)
                if chroma.shape[1] > 2:
                    frame_corrs = [
                        float(np.corrcoef(chroma[:, i], chroma[:, i + 1])[0, 1])
                        for i in range(min(100, chroma.shape[1] - 1))
                        if np.std(chroma[:, i]) > 1e-6 and np.std(chroma[:, i + 1]) > 1e-6
                    ]
                    temp_stab = float(np.mean(frame_corrs)) if frame_corrs else 0.5
                    if np.isnan(temp_stab):
                        temp_stab = 0.5
                else:
                    temp_stab = 0.5

                # 6. Composite Harmonic Score
                composite = (
                    0.30 * harm_ratio +
                    0.25 * min(chroma_strength * 2.5, 1.0) +
                    0.20 * (1.0 - flatness) +
                    0.15 * (1.0 - norm_entropy) +
                    0.10 * temp_stab
                )
                composite = float(np.clip(composite, 0.0, 1.0))

                # Determine candidate rejection reasons
                rejection_reason = None
                if source_name in self.EXCLUDED_STEMS:
                    rejection_reason = f"Excluded source stem: {source_name}"
                elif harm_ratio < 0.15 and pitch_act < 0.05:
                    rejection_reason = "Insufficient harmonic energy and pitch activity"

                source_type = "stem" if source_name in ["bass", "other", "drums", "vocals", "inst"] else ("hpss" if "hpss" in source_name else "mix")

                self._evidence[source_name] = CandidateSourceEvidence(
                    sourceName=source_name,
                    sourceType=source_type,
                    instrument=source_name if source_name in ["bass", "guitar", "piano"] else None,
                    isAvailable=True,
                    harmonicEnergy=round(harm_ratio, 4),
                    pitchActivity=round(pitch_act, 4),
                    chromaStrength=round(chroma_strength, 4),
                    chromaEntropy=round(norm_entropy, 4),
                    spectralFlatness=round(flatness, 4),
                    temporalStability=round(temp_stab, 4),
                    compositeScore=round(composite, 4),
                    rejectionReason=rejection_reason,
                    chordConfidence=None,
                    isSelected=False
                )

            except Exception as e:
                logger.warning(f"Error computing evidence for candidate {source_name}: {e}")
        # 7. Register unextracted standard candidates as unavailable
        STANDARD_CANDIDATES = ["mix", "harmonic_hpss", "other", "bass", "guitar", "piano", "vocals", "drums"]
        for key in STANDARD_CANDIDATES:
            if key not in self._evidence:
                source_type = "stem" if key in ["bass", "other", "drums", "vocals", "guitar", "piano"] else ("hpss" if "hpss" in key else "mix")
                self._evidence[key] = CandidateSourceEvidence(
                    sourceName=key,
                    sourceType=source_type,
                    isAvailable=False,
                    rejectionReason="Candidate source not available or not extracted"
                )

        return self._evidence

    def filter_promising_candidates(self) -> List[str]:
        """
        Returns list of source names qualified for expensive chord recognition inference.
        Discards excluded stems (drums, vocals) and low-energy/noisy audio.
        """
        if not self._evidence:
            self.extract_evidence()

        promising = []
        for name, ev in self._evidence.items():
            if not ev.is_available or ev.rejection_reason:
                continue
            if ev.composite_score is not None and ev.composite_score >= 0.20:
                promising.append(name)

        # Ensure at least 'mix' or 'other' is considered if available
        if not promising:
            for fallback_name in ["other", "mix", "harmonic_hpss"]:
                if fallback_name in self._evidence and self._evidence[fallback_name].is_available:
                    promising.append(fallback_name)
                    break

        return promising

    def analyze_candidate_chords(
        self,
        engine_manager: Any,
        timing_data: Optional[TimingData] = None,
        duration: Optional[float] = None,
        key: Optional[str] = None,
        scale: Optional[str] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Runs chord recognition on all qualifying candidate sources.
        """
        qualified = self.filter_promising_candidates()
        self._chord_results = {}
        self._source_confidences = {}

        for src_name in qualified:
            audio_path = self._source_paths.get(src_name)
            if not audio_path or not os.path.isfile(audio_path):
                continue

            try:
                res = engine_manager.recognize_chords(
                    audio_path=audio_path,
                    timing_data=timing_data,
                    duration=duration,
                    key=key,
                    scale=scale
                )
                self._chord_results[src_name] = res.events
                self._source_confidences[src_name] = float(res.confidence) if res.confidence is not None else 0.85
                if src_name in self._evidence:
                    self._evidence[src_name].chord_confidence = round(self._source_confidences[src_name], 3)
            except Exception as e:
                logger.warning(f"Chord recognition failed on candidate {src_name}: {e}")

        return self._chord_results

    def select_best_evidence(
        self,
        duration: float,
        y_bass: Optional[np.ndarray] = None,
        instruments: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Dict[str, Any]], SourceSelectionResult, AudioStatus]:
        """
        Selects the best harmonic evidence across candidate sources and synthesizes
        cross-source agreement, bass root/inversion fusion, and explainable diagnostic reasoning.

        Returns
        -------
        Tuple[List[Dict[str, Any]], SourceSelectionResult, AudioStatus]
            (final_chords, selection_result, audio_status)
        """
        if not self._chord_results:
            # Check if any evidence exists at all
            max_comp = max([ev.composite_score or 0.0 for ev in self._evidence.values()], default=0.0)
            if max_comp < 0.10:
                status = AudioStatus.NO_HARMONIC_CONTENT
            else:
                status = AudioStatus.LOW_CONFIDENCE

            selection_res = SourceSelectionResult(
                selectedSource="none",
                selectedInstrument=None,
                selectionConfidence=0.0,
                reason="No candidate sources provided sufficient harmonic evidence.",
                candidateScores={k: v.composite_score or 0.0 for k, v in self._evidence.items()},
                sourceAgreement=None
            )
            return [], selection_res, status

        # 1. Compute cross-source musical agreement
        source_agreement = compute_source_agreement(self._chord_results, duration=duration)

        # 2. Score candidate progressions
        candidate_scores: Dict[str, float] = {}
        for src_name, chords in self._chord_results.items():
            ev = self._evidence.get(src_name)
            comp = ev.composite_score if ev and ev.composite_score is not None else 0.5
            c_conf = self._source_confidences.get(src_name, 0.85)
            
            # Penalize sequences with pure 'N' (no chord) content
            active_ratio = np.mean([1.0 if c.get("chord", "N") != "N" else 0.2 for c in chords]) if chords else 0.0

            # Source preference heuristic: isolated harmonic stem ('other') receives slight clarity bonus
            stem_clarity_bonus = 0.08 if src_name == "other" else (0.04 if src_name == "harmonic_hpss" else 0.0)

            # Agreement boost
            agr_boost = (source_agreement * 0.15) if source_agreement is not None else 0.0

            final_score = (
                0.40 * comp +
                0.30 * c_conf +
                0.20 * active_ratio +
                stem_clarity_bonus +
                agr_boost
            )
            candidate_scores[src_name] = round(float(np.clip(final_score, 0.0, 1.0)), 4)

        # 3. Select optimal candidate
        best_source = max(candidate_scores, key=lambda k: candidate_scores[k])
        best_score = candidate_scores[best_source]
        selected_chords = list(self._chord_results[best_source])

        # Mark selected in evidence registry
        for name, ev in self._evidence.items():
            ev.is_selected = (name == best_source)

        # 4. Integrate Bass Evidence (Slash Chords & Root Reinforcement)
        bass_chords = self._chord_results.get("bass")
        effective_bass_y = y_bass if y_bass is not None else self._sources.get("bass")
        fused_chords = fuse_bass_evidence(
            chords=selected_chords,
            y_bass=effective_bass_y,
            bass_chords=bass_chords,
            sr=self.sr
        )

        # 5. Construct explainable reasoning string from actual measurements
        best_ev = self._evidence.get(best_source)
        harm_str = f"harmonic energy={best_ev.harmonic_energy}" if best_ev and best_ev.harmonic_energy is not None else "clear harmony"
        chroma_str = f"chroma strength={best_ev.chroma_strength}" if best_ev and best_ev.chroma_strength is not None else "tonal clarity"
        agr_str = f"{int(source_agreement * 100)}% agreement across sources" if source_agreement is not None else "independent source clarity"
        
        reason = f"{best_source} selected based on {harm_str}, {chroma_str}, and {agr_str}."

        # Inferred instrument
        inferred_inst = None
        if best_source == "other":
            inferred_inst = "harmonic_mix"
        elif best_source in ["guitar", "piano", "synth", "bass"]:
            inferred_inst = best_source
        elif best_source == "mix":
            inferred_inst = "mix"

        selection_res = SourceSelectionResult(
            selectedSource=best_source,
            selectedInstrument=inferred_inst,
            selectionConfidence=round(best_score, 3),
            reason=reason,
            candidateScores=candidate_scores,
            sourceAgreement=source_agreement
        )

        # Check if selection results in active chords
        has_active_chords = any(c.get("chord", "N") != "N" for c in fused_chords)
        if not has_active_chords:
            status = AudioStatus.NO_HARMONIC_CONTENT if best_score < 0.3 else AudioStatus.LOW_CONFIDENCE
        else:
            status = AudioStatus.SUCCESS if best_score >= 0.60 else AudioStatus.LOW_CONFIDENCE

        return fused_chords, selection_res, status
