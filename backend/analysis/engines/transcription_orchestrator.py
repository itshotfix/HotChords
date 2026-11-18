"""
backend/analysis/engines/transcription_orchestrator.py

Multi-engine transcription orchestrator and evidence reconciliation system.
Runs HotChords' native transcription alongside optional neural engines
(e.g., BasicPitchEngine) with independent failure handling
and transparent evidence-based note reconciliation.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional, Callable, Tuple
import numpy as np

from backend.theory.piano_voicing import midi_to_note_name
from backend.analysis.note_transcription import (
    transcribe_polyphonic_accompaniment,
    quantize_notes_to_grid,
)
from .basic_pitch_engine import BasicPitchEngine

logger = logging.getLogger(__name__)


def _notes_match(a: Dict[str, Any], b: Dict[str, Any], onset_tol_sec: float, min_overlap_sec: float) -> bool:
    """Return True if two note events represent the same MIDI pitch and overlapping time span."""
    if int(a["midi"]) != int(b["midi"]):
        return False
    if abs(float(a["start"]) - float(b["start"])) > onset_tol_sec:
        return False
    overlap = min(float(a["end"]), float(b["end"])) - max(float(a["start"]), float(b["start"]))
    union = max(float(a["end"]), float(b["end"])) - min(float(a["start"]), float(b["start"]))
    if overlap >= min_overlap_sec:
        return True
    return union > 0 and (overlap / union) >= 0.25


def reconcile_transcriptions(
    engine_outputs: Dict[str, List[Dict[str, Any]]],
    onset_tol_sec: float = 0.06,
    min_overlap_sec: float = 0.04,
    single_engine_min_conf: float = 0.42,
    octave_suppression_ratio: float = 0.72,
    beat_times: Optional[List[float]] = None,
    source: str = "accompaniment",
) -> List[Dict[str, Any]]:
    """
    Reconcile note events from multiple transcription engines using transparent
    pitch/onset/duration agreement, disagreement preservation, and octave-ghost filtering.
    """
    tagged: List[Dict[str, Any]] = []
    for eng_name, notes in engine_outputs.items():
        if not notes:
            continue
        for n in notes:
            if float(n.get("end", 0.0)) <= float(n.get("start", 0.0)):
                continue
            item = dict(n)
            item["_engine"] = eng_name
            item["confidence"] = float(item.get("confidence", 0.65))
            item["velocity"] = int(item.get("velocity", 68))
            tagged.append(item)

    if not tagged:
        return []

    tagged.sort(key=lambda x: (float(x["start"]), int(x["midi"]), -float(x["confidence"])))

    # Cluster matching notes (same MIDI, close onset, overlapping duration)
    clusters: List[List[Dict[str, Any]]] = []
    for n in tagged:
        placed = False
        for cl in reversed(clusters):
            if float(n["start"]) - float(cl[0]["start"]) > onset_tol_sec * 2.0:
                break
            if any(_notes_match(n, member, onset_tol_sec, min_overlap_sec) for member in cl):
                cl.append(n)
                placed = True
                break
        if not placed:
            clusters.append([n])

    reconciled: List[Dict[str, Any]] = []
    for cl in clusters:
        # Deduplicate multiple hits from the same engine within one cluster (keep highest confidence)
        best_per_engine: Dict[str, Dict[str, Any]] = {}
        for m in cl:
            eng = m["_engine"]
            if eng not in best_per_engine or m["confidence"] > best_per_engine[eng]["confidence"]:
                best_per_engine[eng] = m

        members = list(best_per_engine.values())
        engines = sorted(best_per_engine.keys())
        weights = np.array([max(0.1, m["confidence"]) for m in members], dtype=float)
        weights /= np.sum(weights)

        start = float(np.sum([w * float(m["start"]) for w, m in zip(weights, members)]))
        end = float(np.sum([w * float(m["end"]) for w, m in zip(weights, members)]))
        if end <= start + 0.02:
            end = max(float(m["end"]) for m in members)

        vel = int(round(np.sum([w * int(m["velocity"]) for w, m in zip(weights, members)])))
        mean_conf = float(np.mean([m["confidence"] for m in members]))

        if len(engines) >= 2:
            conf = float(min(0.99, mean_conf + 0.15))
            agreement = "consensus"
        else:
            conf = mean_conf
            agreement = "single_engine"
            if conf < single_engine_min_conf:
                continue

        midi_val = int(members[0]["midi"])
        reconciled.append({
            "midi": midi_val,
            "note": members[0].get("note") or midi_to_note_name(midi_val),
            "start": round(start, 4),
            "end": round(end, 4),
            "velocity": int(np.clip(vel, 1, 127)),
            "confidence": round(conf, 3),
            "source": members[0].get("source") or source,
            "engines": engines,
            "agreement": agreement,
        })

    # Sustained-overlap deduplication: merge same-MIDI notes where one is substantially
    # contained inside another (e.g., Basic Pitch re-onset inside a sustained native note).
    reconciled.sort(key=lambda n: (int(n["midi"]), float(n["start"]), -(float(n["end"]) - float(n["start"]))))
    merged: List[Dict[str, Any]] = []
    for n in reconciled:
        if merged and int(merged[-1]["midi"]) == int(n["midi"]):
            prev = merged[-1]
            overlap = min(prev["end"], n["end"]) - max(prev["start"], n["start"])
            min_dur = max(1e-4, min(prev["end"] - prev["start"], n["end"] - n["start"]))
            diff_engines = set(prev.get("engines", [])) != set(n.get("engines", []))
            close_onset = abs(float(n["start"]) - float(prev["start"])) <= onset_tol_sec * 2.5
            if overlap >= 0.65 * min_dur and (diff_engines or close_onset):
                prev["start"] = round(min(prev["start"], n["start"]), 4)
                prev["end"] = round(max(prev["end"], n["end"]), 4)
                prev["velocity"] = max(int(prev["velocity"]), int(n["velocity"]))
                combined_engines = sorted(set(prev.get("engines", [])) | set(n.get("engines", [])))
                prev["engines"] = combined_engines
                if len(combined_engines) >= 2:
                    prev["agreement"] = "consensus"
                    prev["confidence"] = round(min(0.99, max(prev["confidence"], n["confidence"]) + 0.12), 3)
                else:
                    prev["confidence"] = round(max(prev["confidence"], n["confidence"]), 3)
                continue
        merged.append(n)
    reconciled = merged

    # Octave & 2-octave harmonic ghost mitigation: suppress weak single-engine m+12 / m+24 ghosts
    keep = [True] * len(reconciled)
    for i, cand in enumerate(reconciled):
        if cand["agreement"] == "consensus":
            continue
        c_dur = max(1e-4, cand["end"] - cand["start"])
        for j, anchor in enumerate(reconciled):
            if i == j or not keep[j]:
                continue
            diff = cand["midi"] - anchor["midi"]
            if diff not in (12, -12, 24):
                continue
            overlap = min(cand["end"], anchor["end"]) - max(cand["start"], anchor["start"])
            if diff == 24:
                # 4th harmonic ghost (2 octaves up): strict confidence ratio below 88, wider only for extreme >= 88
                max_ratio = 1.15 if cand["midi"] >= 88 else 0.85
                if overlap >= 0.60 * c_dur and cand["midi"] >= 84 and cand["confidence"] < anchor["confidence"] * max_ratio:
                    keep[i] = False
                    break
            else:
                if abs(cand["start"] - anchor["start"]) <= onset_tol_sec * 1.5 and overlap >= 0.5 * c_dur:
                    if cand["confidence"] < anchor["confidence"] * octave_suppression_ratio:
                        keep[i] = False
                        break

    final_notes = [n for idx, n in enumerate(reconciled) if keep[idx]]
    final_notes.sort(key=lambda n: (n["start"], n["midi"]))

    if beat_times and len(beat_times) >= 2:
        final_notes = quantize_notes_to_grid(final_notes, beat_times, max_snap_sec=0.04)

    return final_notes


class TranscriptionOrchestrator:
    """
    Orchestrates native HotChords transcription and optional neural engines
    (Basic Pitch, etc.) with parallel execution and safe fallback.
    """

    def __init__(
        self,
        basic_pitch_engine: Optional[BasicPitchEngine] = None,
        extra_engines: Optional[Dict[str, Callable[[np.ndarray, int], List[Dict[str, Any]]]]] = None,
        enable_basic_pitch: bool = True,
        parallel: bool = True,
    ):
        self.basic_pitch_engine = basic_pitch_engine or BasicPitchEngine(enabled=enable_basic_pitch)
        self.extra_engines = dict(extra_engines or {})
        self.parallel = parallel
        self.last_engine_status: Dict[str, str] = {}

    def transcribe_accompaniment(
        self,
        y_harm: np.ndarray,
        sr: int = 22050,
        y_bass: Optional[np.ndarray] = None,
        hop_length: int = 512,
        beat_times: Optional[List[float]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Run native accompaniment transcription plus enabled neural engines,
        then reconcile into a unified HotChords note event list.
        """
        self.last_engine_status = {}
        tasks: Dict[str, Callable[[], List[Dict[str, Any]]]] = {
            "hotchords_native": lambda: transcribe_polyphonic_accompaniment(
                y_harm=y_harm,
                sr=sr,
                y_bass=y_bass,
                hop_length=hop_length,
                beat_times=beat_times,
            )
        }

        bp_ok, bp_reason = self.basic_pitch_engine.check_availability()
        if bp_ok:
            tasks["basic_pitch_onnx"] = lambda: self.basic_pitch_engine.transcribe_audio(
                y=y_harm,
                sr=sr,
                source="accompaniment",
            )
        else:
            self.last_engine_status["basic_pitch_onnx"] = f"skipped: {bp_reason}"

        for eng_name, fn in self.extra_engines.items():
            tasks[eng_name] = lambda f=fn: f(y_harm, sr)

        outputs: Dict[str, List[Dict[str, Any]]] = {}

        if self.parallel and len(tasks) > 1:
            with ThreadPoolExecutor(max_workers=min(3, len(tasks))) as pool:
                futures = {name: pool.submit(fn) for name, fn in tasks.items()}
                for name, fut in futures.items():
                    try:
                        outputs[name] = fut.result()
                        self.last_engine_status[name] = f"ok ({len(outputs[name])} notes)"
                    except Exception as e:
                        logger.warning("Transcription engine '%s' failed: %s", name, e)
                        self.last_engine_status[name] = f"error: {e}"
        else:
            for name, fn in tasks.items():
                try:
                    outputs[name] = fn()
                    self.last_engine_status[name] = f"ok ({len(outputs[name])} notes)"
                except Exception as e:
                    logger.warning("Transcription engine '%s' failed: %s", name, e)
                    self.last_engine_status[name] = f"error: {e}"

        if not outputs:
            return []

        if len(outputs) == 1 and "hotchords_native" in outputs:
            return outputs["hotchords_native"]

        return reconcile_transcriptions(outputs, beat_times=beat_times, source="accompaniment")
