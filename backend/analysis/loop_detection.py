"""
backend/analysis/loop_detection.py

Automatic 4-Chord Loop & Progression Detection Engine for HotChords.

Identifies the strongest, most musically meaningful repeating 4-chord cycle in a song:
  1. Filters and extracts discrete harmonic change events (rejecting sustained slices & NO_CHORD).
  2. Generates candidate 4-chord windows across the song timeline and repeating sections.
  3. Performs transposition-aware progression matching across relative root delta cycles.
  4. Ranks candidates via transparent objective scoring (repetition, confidence, temporal regularity, structural placement, harmonic diversity).
  5. Preserves both raw detected chords and beginner-friendly simplified chord symbols.
  6. Strictly returns available=False when no reliable progression exists (never fabricates fake defaults).
"""

from typing import List, Dict, Optional, Any, Tuple
import numpy as np

from backend.models.analysis_types import (
    FourChordLoopResult,
    StructureAnalysisResult,
    TimingData,
)
from backend.analysis.source_agreement import parse_chord_root_and_quality
from backend.theory.simplification import reduce_chord_harmony

PITCH_CLASS_MAP = {
    "C": 0, "B#": 0,
    "C#": 1, "DB": 1,
    "D": 2,
    "D#": 3, "EB": 3,
    "E": 4, "FB": 4,
    "F": 5, "E#": 5,
    "F#": 6, "GB": 6,
    "G": 7,
    "G#": 8, "AB": 8,
    "A": 9,
    "A#": 10, "BB": 10,
    "B": 11, "CB": 11,
}


def _get_root_semitone(root: str) -> Optional[int]:
    """Parses root note name to pitch class integer 0-11."""
    if not root:
        return None
    cleaned = root.upper().strip()
    return PITCH_CLASS_MAP.get(cleaned)


def _get_simplified_triad(chord_name: str) -> str:
    """Simplifies complex chords to basic musician-friendly triads for comparison."""
    if not chord_name or chord_name.upper() in ("N", "NO_CHORD", "NONE", ""):
        return "N"
    clean = chord_name.strip()
    if ":" in clean:
        parts = clean.split(":")
        r = parts[0]
        q = parts[1].split("/")[0].lower()
        if q in ("min", "min7", "m", "m7", "m9", "min9"):
            return f"{r}m"
        elif q in ("maj", "maj7", "7", "maj9", "9", "5", "6"):
            return r
        elif q in ("sus2", "sus4", "dim", "aug"):
            return f"{r}{q}"
    res = reduce_chord_harmony(chord_name)
    return res if res else chord_name


class FourChordLoopDetector:
    """
    Automatic four-chord loop detector and progression ranker.
    """

    def __init__(
        self,
        min_repetition_count: int = 1,
        min_loop_confidence: float = 0.55,
        min_chord_confidence: float = 0.50,
        min_distinct_chords: int = 2,
    ):
        self.min_repetition_count = min_repetition_count
        self.min_loop_confidence = min_loop_confidence
        self.min_chord_confidence = min_chord_confidence
        self.min_distinct_chords = min_distinct_chords

    def detect(
        self,
        chords: List[Dict[str, Any]],
        duration: float,
        structure: Optional[StructureAnalysisResult] = None,
        timing_data: Optional[TimingData] = None,
    ) -> FourChordLoopResult:
        """
        Detects the best 4-chord loop progression in the song.
        """
        if not chords or duration <= 0:
            return FourChordLoopResult(
                available=False,
                reason="INSUFFICIENT_HARMONIC_INFORMATION",
            )

        # 1. Extract discrete harmonic change events
        harmonic_events = self._extract_harmonic_events(chords)
        if len(harmonic_events) < 4:
            return FourChordLoopResult(
                available=False,
                reason="INSUFFICIENT_DISTINCT_CHORDS",
            )

        # 2. Extract all contiguous 4-chord candidate windows
        candidates = self._generate_4chord_candidates(harmonic_events, structure)
        if not candidates:
            return FourChordLoopResult(
                available=False,
                reason="NO_VALID_FOUR_CHORD_WINDOWS",
            )

        # 3. Score and rank candidates
        scored_candidates = self._score_candidates(candidates, harmonic_events, duration, structure)
        if not scored_candidates:
            return FourChordLoopResult(
                available=False,
                reason="NO_RELIABLE_FOUR_CHORD_LOOP",
            )

        # 4. Select top-ranked candidate
        best = scored_candidates[0]
        if best["score"] < self.min_loop_confidence or best["confidence"] < self.min_chord_confidence:
            return FourChordLoopResult(
                available=False,
                confidence=round(best["score"], 3),
                reason="LOW_CONFIDENCE_PROGRESSION",
            )

        # In through-composed music (more than 4 harmonic events in total), require actual recurrence (repetition_count >= 2)
        if len(harmonic_events) > 4 and best["repetition_count"] < 2:
            return FourChordLoopResult(
                available=False,
                confidence=round(best["score"], 3),
                reason="NO_REPEATING_PROGRESSION_IN_THROUGH_COMPOSED_SONG",
            )

        # Generate voice-led piano voicings and beginner playability score (Phase 8)
        from backend.theory.piano_voicing import voice_four_chord_loop, evaluate_loop_beginner_playability
        loop_voicings = voice_four_chord_loop(best["simplified_chords"])
        playability = evaluate_loop_beginner_playability(best["simplified_chords"])

        # Build clean structured output
        return FourChordLoopResult(
            available=True,
            chords=best["chords"],
            rawChords=best["raw_chords"],
            simplifiedChords=best["simplified_chords"],
            voicings=loop_voicings,
            playabilityScore=playability,
            section=best["section"],
            start=round(best["start"], 3),
            end=round(best["end"], 3),
            duration=round(best["duration"], 3),
            confidence=round(best["score"], 3),
            occurrences=[round(t, 3) for t in best["occurrences"]],
            repetitionCount=best["repetition_count"],
            reason=best["reason"],
        )

    def _extract_harmonic_events(self, chords: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Collapses consecutive identical chords (preventing sustained C | C | C | C from becoming 4 chords)
        and filters out NO_CHORD ('N') events.
        """
        events: List[Dict[str, Any]] = []

        for c in chords:
            name = c.get("chord") or c.get("chordName") or c.get("name") or "N"
            start = float(c.get("time", c.get("startTime", c.get("start", 0.0))))
            end = float(c.get("end", c.get("endTime", start + 2.0)))
            conf = float(c.get("confidence", 0.9))
            raw = c.get("raw_chord") or c.get("rawChord") or name

            # Reject NO_CHORD
            if name.upper() in ("N", "NO_CHORD", "NONE", "X", ""):
                continue

            simplified = _get_simplified_triad(name)
            root, quality, _ = parse_chord_root_and_quality(name)
            root_semitone = _get_root_semitone(root) if root else None

            # Check if this chord continues the previous chord
            if events and events[-1]["chord"] == name and abs(events[-1]["end"] - start) < 0.25:
                # Extend duration of previous event
                events[-1]["end"] = max(events[-1]["end"], end)
                events[-1]["duration"] = events[-1]["end"] - events[-1]["start"]
                events[-1]["confidence"] = (events[-1]["confidence"] + conf) / 2.0
            else:
                events.append({
                    "chord": name,
                    "raw_chord": raw,
                    "simplified": simplified,
                    "root": root,
                    "quality": quality,
                    "root_semitone": root_semitone,
                    "start": start,
                    "end": end,
                    "duration": end - start,
                    "confidence": conf,
                })

        return events

    def _generate_4chord_candidates(
        self,
        events: List[Dict[str, Any]],
        structure: Optional[StructureAnalysisResult],
    ) -> List[Dict[str, Any]]:
        """
        Generates 4-chord sliding windows and computes relative root delta signatures.
        """
        candidates: List[Dict[str, Any]] = []
        n = len(events)
        if n < 4:
            return []

        for i in range(n - 3):
            window = events[i : i + 4]
            chord_names = [w["chord"] for w in window]
            raw_names = [w["raw_chord"] for w in window]
            simp_names = [w["simplified"] for w in window]
            roots = [w["root_semitone"] for w in window]
            qualities = [w["quality"] for w in window]

            # Require at least min_distinct_chords (e.g. at least 2 distinct chords in the 4-chord window)
            distinct_count = len(set(simp_names))
            if distinct_count < self.min_distinct_chords:
                continue

            # Compute transposition-invariant root delta signature:
            # delta = [(r2 - r1)%12, (r3 - r2)%12, (r4 - r3)%12, (r1 - r4)%12]
            if all(r is not None for r in roots):
                deltas = (
                    (roots[1] - roots[0]) % 12,
                    (roots[2] - roots[1]) % 12,
                    (roots[3] - roots[2]) % 12,
                    (roots[0] - roots[3]) % 12,
                )
                signature = (deltas, tuple(qualities))
            else:
                signature = (tuple(simp_names),)

            start_t = window[0]["start"]
            end_t = window[3]["end"]
            dur = end_t - start_t
            avg_conf = float(np.mean([w["confidence"] for w in window]))

            # Determine section context
            section_label = "REPEATING_SECTION"
            if structure and structure.sections:
                for sec in structure.sections:
                    if sec.start <= start_t <= sec.end:
                        section_label = sec.label
                        break

            candidates.append({
                "window_index": i,
                "chords": chord_names,
                "raw_chords": raw_names,
                "simplified_chords": simp_names,
                "signature": signature,
                "roots": roots,
                "qualities": qualities,
                "start": start_t,
                "end": end_t,
                "duration": dur,
                "confidence": avg_conf,
                "section": section_label,
                "distinct_count": distinct_count,
                "durations": [w["duration"] for w in window],
            })

        return candidates

    def _score_candidates(
        self,
        candidates: List[Dict[str, Any]],
        all_events: List[Dict[str, Any]],
        total_duration: float,
        structure: Optional[StructureAnalysisResult],
    ) -> List[Dict[str, Any]]:
        """
        Evaluates candidate windows across repetition, confidence, stability,
        structural importance, and harmonic richness.
        """
        sig_groups: Dict[Any, List[Dict[str, Any]]] = {}
        for c in candidates:
            sig = c["signature"]
            if sig not in sig_groups:
                sig_groups[sig] = []
            sig_groups[sig].append(c)

        scored = []
        seen_chord_progressions = set()

        for sig, group in sig_groups.items():
            primary = group[0]
            # Filter candidates with low chord detection confidence
            if primary["confidence"] < self.min_chord_confidence:
                continue

            occurrences = []
            last_end = -1.0
            for g in group:
                if g["start"] >= (last_end - 0.5):
                    occurrences.append(g["start"])
                    last_end = g["end"]

            rep_count = len(occurrences)

            prog_tuple = tuple(primary["simplified_chords"])
            if prog_tuple in seen_chord_progressions:
                continue
            seen_chord_progressions.add(prog_tuple)

            # 1. Repetition Score (0.0 - 1.0)
            if rep_count >= 2:
                rep_score = min(1.0, (rep_count - 1) * 0.35 + 0.30)
            elif len(all_events) > 4:
                # Occurs only 1 time in a multi-chord song: through-composed non-repeating passage
                rep_score = 0.05
            else:
                # Isolated 4-chord clip
                rep_score = 0.40

            # 2. Confidence Score (0.0 - 1.0)
            conf_score = primary["confidence"]

            # 3. Temporal Stability / Regularity Score (0.0 - 1.0)
            durs = primary["durations"]
            if durs and len(durs) == 4 and all(d > 0.1 for d in durs):
                mean_dur = float(np.mean(durs))
                std_dur = float(np.std(durs))
                cv = std_dur / max(0.1, mean_dur)
                temporal_stability = max(0.2, 1.0 - min(1.0, cv * 0.7))
            else:
                temporal_stability = 0.5

            # 4. Structural Placement Score (0.0 - 1.0)
            sec_label = primary["section"]
            if "REPEATING" in sec_label.upper():
                struct_score = 0.95
            elif "VERSE" in sec_label.upper() or "CHORUS" in sec_label.upper() or "SECTION" in sec_label.upper():
                struct_score = 0.80
            elif "INTRO" in sec_label.upper() or "OUTRO" in sec_label.upper():
                struct_score = 0.50
            else:
                struct_score = 0.70

            # 5. Harmonic Diversity Score (0.0 - 1.0)
            distinct_cnt = primary["distinct_count"]
            if distinct_cnt == 4:
                diversity_score = 1.0
            elif distinct_cnt == 3:
                diversity_score = 0.85
            else:
                diversity_score = 0.60

            # Composite Ranking Formula
            final_score = (
                0.35 * rep_score
                + 0.25 * conf_score
                + 0.15 * temporal_stability
                + 0.15 * struct_score
                + 0.10 * diversity_score
            )

            chords_str = " → ".join(primary["simplified_chords"])
            reason = (
                f"Progression '{chords_str}' repeats {rep_count}x with "
                f"confidence {round(conf_score, 2)} and high temporal stability ({round(temporal_stability, 2)})"
            )

            scored.append({
                "chords": primary["chords"],
                "raw_chords": primary["raw_chords"],
                "simplified_chords": primary["simplified_chords"],
                "section": primary["section"],
                "start": primary["start"],
                "end": primary["end"],
                "duration": primary["duration"],
                "confidence": primary["confidence"],
                "score": float(final_score),
                "occurrences": occurrences,
                "repetition_count": rep_count,
                "reason": reason,
            })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored


def detect_four_chord_loop(
    chords: List[Dict[str, Any]],
    duration: float,
    structure: Optional[StructureAnalysisResult] = None,
    timing_data: Optional[TimingData] = None,
) -> FourChordLoopResult:
    """
    Convenience functional interface for 4-chord loop detection.
    """
    detector = FourChordLoopDetector()
    return detector.detect(
        chords=chords,
        duration=duration,
        structure=structure,
        timing_data=timing_data,
    )
