"""
backend/analysis/temporal_postprocessing.py

Temporal Post-Processing & Beat Alignment for Chord Recognizers.
Refines raw frame-level and segment-level chord detections into musically coherent
progressions:
- Adjacent identical chord merging
- Micro-jitter / short spike suppression (< 0.15s)
- Musical beat grid alignment (snapping to TimingData beats)
- Explicit NO_CHORD ('N') region preservation
"""

from typing import List, Dict, Any, Optional
import numpy as np
from backend.models.analysis_types import TimingData


def merge_adjacent_identical_chords(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merges consecutive chord events with the exact same chord name."""
    if not events:
        return []

    merged = []
    current = dict(events[0])

    for nxt in events[1:]:
        if nxt['chord'] == current['chord']:
            # Extend end time and update confidence (weighted average)
            c_dur = max(0.01, current['end'] - current['time'])
            n_dur = max(0.01, nxt['end'] - nxt['time'])
            tot_dur = c_dur + n_dur
            c_conf = current.get('confidence', 1.0)
            n_conf = nxt.get('confidence', 1.0)
            avg_conf = (c_conf * c_dur + n_conf * n_dur) / tot_dur

            current['end'] = round(float(nxt['end']), 3)
            current['confidence'] = round(float(avg_conf), 3)
        else:
            merged.append(current)
            current = dict(nxt)

    merged.append(current)
    return merged


def remove_short_spikes(events: List[Dict[str, Any]], min_duration: float = 0.15) -> List[Dict[str, Any]]:
    """
    Absorbs transient single-frame prediction spikes (< min_duration) into surrounding chords.
    Legitimate musical changes with sufficient duration are preserved.
    """
    if len(events) <= 1:
        return events

    cleaned = []
    for i, ev in enumerate(events):
        dur = float(ev['end']) - float(ev['time'])
        # If very short and not the only event, absorb
        if dur < min_duration and len(events) > 2:
            if i > 0:
                # Merge into previous event
                cleaned[-1]['end'] = ev['end']
            elif i + 1 < len(events):
                # Adjust next event start time
                events[i + 1]['time'] = ev['time']
        else:
            cleaned.append(dict(ev))

    return merge_adjacent_identical_chords(cleaned)


def snap_chord_boundaries_to_beats(
    events: List[Dict[str, Any]],
    beat_times: List[float],
    tolerance: float = 0.18
) -> List[Dict[str, Any]]:
    """
    Snaps chord transition boundaries to the nearest beat timestamp from TimingAnalyzer
    if within tolerance (e.g. ~180ms), aligning harmonic changes to the musical grid.
    """
    if not events or not beat_times:
        return events

    beats = np.array(beat_times)
    snapped = [dict(ev) for ev in events]

    for i in range(len(snapped) - 1):
        boundary = snapped[i]['end']
        diffs = np.abs(beats - boundary)
        min_idx = int(np.argmin(diffs))
        min_diff = diffs[min_idx]

        if min_diff <= tolerance:
            closest_beat = round(float(beats[min_idx]), 3)
            # Ensure boundary remains strictly between start of current and end of next
            if closest_beat > snapped[i]['time'] + 0.05 and closest_beat < snapped[i + 1]['end'] - 0.05:
                snapped[i]['end'] = closest_beat
                snapped[i + 1]['time'] = closest_beat

    return snapped


def postprocess_chord_progression(
    events: List[Dict[str, Any]],
    timing_data: Optional[TimingData] = None,
    min_duration: float = 0.15,
    snap_to_beats: bool = True
) -> List[Dict[str, Any]]:
    """
    Executes the full temporal post-processing pipeline on recognized chords.
    """
    if not events:
        return []

    # 1. Merge contiguous identical predictions
    events = merge_adjacent_identical_chords(events)

    # 2. Suppress transient prediction spikes
    events = remove_short_spikes(events, min_duration=min_duration)

    # 3. Align boundaries to musical beat grid
    if snap_to_beats and timing_data and timing_data.beat_times:
        events = snap_chord_boundaries_to_beats(events, timing_data.beat_times)
        events = merge_adjacent_identical_chords(events)

    return events
