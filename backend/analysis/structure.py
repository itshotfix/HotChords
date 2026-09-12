"""
backend/analysis/structure.py

Objective Music Structure and Repeating-Section Analysis for HotChords.

Architecture:
  1. Beat-synchronous chroma feature aggregation.
  2. Structural boundary detection via smoothed chroma novelty / flux curves.
  3. Pairwise segment harmonic recurrence & clustering via cosine similarity.
  4. Repeating-section identification and evidence-based non-fabricated labeling.
  5. Diagnostic reporting with structure confidence and repetition groups.
"""

from typing import List, Dict, Optional, Any, Tuple
import numpy as np
import librosa
from scipy.signal import find_peaks

from backend.models.analysis_types import (
    StructureSection,
    StructureAnalysisResult,
    TimingData,
)


class StructureAnalyzer:
    """
    Objective musical structure analyzer.
    Identifies section boundaries and repeating harmonic passages.
    """

    def __init__(
        self,
        min_section_duration: float = 6.0,
        similarity_threshold: float = 0.72,
        novelty_smooth_sec: float = 4.0,
    ):
        self.min_section_duration = min_section_duration
        self.similarity_threshold = similarity_threshold
        self.novelty_smooth_sec = novelty_smooth_sec

    def analyze(
        self,
        chroma: np.ndarray,
        sr: int,
        hop_length: int,
        duration: float,
        timing_data: Optional[TimingData] = None,
    ) -> StructureAnalysisResult:
        """
        Executes structural segmentation and repeating section detection.
        """
        if duration <= 0 or chroma is None or chroma.size == 0 or chroma.shape[1] < 10:
            return self._fallback_single_section(duration)

        try:
            # 1. Detect candidate boundary timestamps
            boundaries = self._detect_boundaries(chroma, sr, hop_length, duration, timing_data)

            # 2. Extract segment harmonic profiles
            segments = self._extract_segment_profiles(chroma, sr, hop_length, boundaries)

            # 3. Cluster repeating segments via harmonic similarity
            sections, repeating_sections, structure_conf, has_repeats = self._cluster_and_label_sections(
                segments, duration
            )

            return StructureAnalysisResult(
                sections=sections,
                repeating_sections=repeating_sections,
                structure_confidence=round(float(structure_conf), 3),
                total_sections=len(sections),
                has_repeating_patterns=has_repeats,
            )

        except Exception as err:
            # Fall back safely without crashing
            return self._fallback_single_section(duration)

    def _detect_boundaries(
        self,
        chroma: np.ndarray,
        sr: int,
        hop_length: int,
        duration: float,
        timing_data: Optional[TimingData],
    ) -> List[float]:
        """
        Detects structural boundary timestamps in seconds.
        """
        n_frames = chroma.shape[1]
        frames_per_sec = sr / float(hop_length)

        # Chroma flux / novelty signal across pitch classes
        diff = np.diff(chroma, axis=1)
        novelty = np.sum(np.maximum(0, diff), axis=0)  # Half-wave rectified flux
        novelty = np.pad(novelty, (1, 0), mode="edge")

        # Smooth novelty curve with moving average window
        win_size = max(3, int(self.novelty_smooth_sec * frames_per_sec))
        if win_size % 2 == 0:
            win_size += 1
        smoothed = np.convolve(novelty, np.hanning(win_size) / np.sum(np.hanning(win_size)), mode="same")

        # Normalize smoothed novelty
        s_max = np.max(smoothed)
        if s_max > 1e-8:
            smoothed = smoothed / s_max

        # Distance between peaks based on min_section_duration
        min_dist_frames = max(1, int(self.min_section_duration * frames_per_sec))
        peaks, props = find_peaks(smoothed, distance=min_dist_frames, prominence=0.08)

        # Convert peak frames to timestamps
        peak_times = librosa.frames_to_time(peaks, sr=sr, hop_length=hop_length).tolist()

        # If timing_data has downbeats, snap peak timestamps to nearest downbeats / beats
        if timing_data and (timing_data.downbeat_times or timing_data.beat_times):
            grid = timing_data.downbeat_times if timing_data.downbeat_times else timing_data.beat_times
            snapped_times = []
            for pt in peak_times:
                nearest = min(grid, key=lambda b: abs(b - pt))
                if abs(nearest - pt) <= 2.0:
                    snapped_times.append(nearest)
                else:
                    snapped_times.append(pt)
            peak_times = snapped_times

        # Build clean sorted boundary list [0.0, ..., duration]
        raw_bounds = [0.0] + [t for t in peak_times if 1.5 <= t <= (duration - 1.5)] + [duration]
        raw_bounds = sorted(list(set(raw_bounds)))

        # Merge boundaries that are closer than min_section_duration
        merged_bounds = [0.0]
        for b in raw_bounds[1:]:
            if (b - merged_bounds[-1]) >= self.min_section_duration or b == duration:
                merged_bounds.append(b)
            elif b == duration and len(merged_bounds) > 1:
                merged_bounds[-1] = duration

        if merged_bounds[-1] < duration:
            merged_bounds.append(duration)

        return merged_bounds

    def _extract_segment_profiles(
        self,
        chroma: np.ndarray,
        sr: int,
        hop_length: int,
        boundaries: List[float],
    ) -> List[Dict[str, Any]]:
        """
        Computes 12-D mean chroma vector and energy for each segment.
        """
        segments = []
        n_frames = chroma.shape[1]

        for i in range(len(boundaries) - 1):
            t_start = boundaries[i]
            t_end = boundaries[i + 1]
            f_start = min(n_frames - 1, max(0, librosa.time_to_frames(t_start, sr=sr, hop_length=hop_length)))
            f_end = min(n_frames, max(f_start + 1, librosa.time_to_frames(t_end, sr=sr, hop_length=hop_length)))

            seg_chroma = chroma[:, f_start:f_end]
            if seg_chroma.size > 0:
                mean_profile = np.mean(seg_chroma, axis=1)
                norm = np.linalg.norm(mean_profile)
                if norm > 1e-6:
                    norm_profile = mean_profile / norm
                else:
                    norm_profile = np.zeros(12)
                energy = float(np.mean(seg_chroma))
            else:
                norm_profile = np.zeros(12)
                energy = 0.0

            segments.append({
                "start": float(t_start),
                "end": float(t_end),
                "duration": float(t_end - t_start),
                "profile": norm_profile,
                "energy": energy,
                "index": i,
            })

        return segments

    def _cluster_and_label_sections(
        self,
        segments: List[Dict[str, Any]],
        total_duration: float,
    ) -> Tuple[List[StructureSection], List[StructureSection], float, bool]:
        """
        Calculates pairwise segment similarity, identifies repeating groups,
        and applies evidence-based non-fabricated labels.
        """
        n = len(segments)
        if n == 0:
            return [], [], 0.0, False

        if n == 1:
            sec = StructureSection(
                label="SECTION_1",
                start=0.0,
                end=round(total_duration, 3),
                duration=round(total_duration, 3),
                repetitionGroup=None,
                similarityScore=None,
            )
            return [sec], [], 0.5, False

        # Compute pairwise cosine similarity matrix
        sim_matrix = np.zeros((n, n), dtype=float)
        for i in range(n):
            for j in range(n):
                p_i = segments[i]["profile"]
                p_j = segments[j]["profile"]
                norm_i = np.linalg.norm(p_i)
                norm_j = np.linalg.norm(p_j)
                if norm_i > 1e-6 and norm_j > 1e-6:
                    sim_matrix[i, j] = float(np.dot(p_i, p_j) / (norm_i * norm_j))
                else:
                    sim_matrix[i, j] = 0.0

        # Cluster repeating segments
        cluster_map: Dict[int, str] = {}
        cluster_members: Dict[str, List[int]] = {}
        cluster_similarities: Dict[int, float] = {}
        cluster_char = "A"

        for i in range(n):
            if i in cluster_map:
                continue

            matches = [i]
            sims = []
            for j in range(i + 1, n):
                if j not in cluster_map and sim_matrix[i, j] >= self.similarity_threshold:
                    matches.append(j)
                    sims.append(sim_matrix[i, j])

            if len(matches) > 1:
                group_name = f"REPEATING_SECTION_{cluster_char}"
                cluster_char = chr(ord(cluster_char) + 1)
                cluster_members[group_name] = matches
                mean_sim = float(np.mean(sims)) if sims else 1.0

                for m in matches:
                    cluster_map[m] = group_name
                    cluster_similarities[m] = mean_sim

        # Generate evidence-driven labels
        sections: List[StructureSection] = []
        repeating_sections: List[StructureSection] = []
        unique_sec_counter = 1

        for i, seg in enumerate(segments):
            start = round(seg["start"], 3)
            end = round(seg["end"], 3)
            dur = round(seg["duration"], 3)

            if i in cluster_map:
                group_id = cluster_map[i]
                sim_score = round(cluster_similarities.get(i, 0.85), 3)
                label = group_id
                sec = StructureSection(
                    label=label,
                    start=start,
                    end=end,
                    duration=dur,
                    repetitionGroup=group_id,
                    similarityScore=sim_score,
                )
                repeating_sections.append(sec)
            else:
                # Contextual non-fabricated labels for non-repeating segments
                if i == 0 and seg["duration"] <= 20.0 and seg["energy"] < 0.6 * np.mean([s["energy"] for s in segments]):
                    label = "INTRO"
                elif i == n - 1 and (total_duration - seg["start"]) <= 25.0:
                    label = "OUTRO"
                else:
                    label = f"SECTION_{unique_sec_counter}"
                    unique_sec_counter += 1

                sec = StructureSection(
                    label=label,
                    start=start,
                    end=end,
                    duration=dur,
                    repetitionGroup=None,
                    similarityScore=None,
                )

            sections.append(sec)

        has_repeats = len(repeating_sections) > 0
        conf = 0.85 if has_repeats else 0.60
        if n >= 2:
            conf = min(0.95, conf + 0.05 * min(3, len(cluster_members)))

        return sections, repeating_sections, conf, has_repeats

    def _fallback_single_section(self, duration: float) -> StructureAnalysisResult:
        dur = max(0.0, round(float(duration), 3))
        sec = StructureSection(
            label="SECTION_1",
            start=0.0,
            end=dur,
            duration=dur,
            repetitionGroup=None,
            similarityScore=None,
        )
        return StructureAnalysisResult(
            sections=[sec],
            repeating_sections=[],
            structure_confidence=0.5,
            total_sections=1,
            has_repeating_patterns=False,
        )


def detect_structure(chroma: np.ndarray, sr: int, hop: int, duration: float) -> List[Dict[str, Any]]:
    """
    Legacy backward-compatible adapter function.
    Returns list of dicts: [{'label': '...', 'start': 0.0, 'end': 15.0}, ...]
    """
    analyzer = StructureAnalyzer()
    res = analyzer.analyze(chroma=chroma, sr=sr, hop_length=hop, duration=duration)
    return [
        {
            "label": s.label,
            "start": round(s.start, 3),
            "end": round(s.end, 3),
        }
        for s in res.sections
    ]


def detect_structure_and_repeats(
    chroma: np.ndarray,
    sr: int,
    hop_length: int,
    duration: float,
    timing_data: Optional[TimingData] = None,
) -> StructureAnalysisResult:
    """
    Primary Phase 4 functional entry point for structure analysis.
    """
    analyzer = StructureAnalyzer()
    return analyzer.analyze(
        chroma=chroma,
        sr=sr,
        hop_length=hop_length,
        duration=duration,
        timing_data=timing_data,
    )
