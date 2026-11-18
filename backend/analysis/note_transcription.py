"""
backend/analysis/note_transcription.py

Polyphonic Piano & Melodic Note Transcription Engine for HotChords.

Converts mixed songs and separated stems (vocal/lead, harmonic accompaniment, bass)
into high-precision, note-level piano events with onset, offset, MIDI pitch,
dynamic velocity, confidence, and source provenance.

Key Capabilities:
1. Melodic Lead Extraction (Vocal / Lead Stem):
   - Sub-bin harmonic salience pitch tracking with vibrato stabilization (median filter).
   - Onset-envelope syllable re-articulation detection.
   - Dynamic velocity mapping from local RMS envelope.
2. Polyphonic Accompaniment & Bass Transcription:
   - Multi-harmonic comb salience with overtone suppression (2*f0 .. 5*f0).
   - Broadband / percussive transient rejection via Wiener spectral flatness.
   - Dedicated low-register bass line tracker (MIDI 28-55) + mid-register polyphonic tracker (MIDI 48-88).
3. Beat-Aware Micro-Quantization:
   - Preserves natural human phrasing while snapping micro-jitter near beat/sub-beat boundaries.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import librosa
from scipy.ndimage import median_filter

from backend.analysis.realtime_pitch import (
    PolyphonicPitchDetector,
    midi_to_freq_exact,
    freq_to_midi_exact,
)
from backend.theory.piano_voicing import midi_to_note_name, PITCH_CLASS_MAP


def _rms_to_velocity(rms_val: float, ref_rms: float, base_min: int = 48, base_max: int = 112) -> int:
    """Maps local RMS amplitude relative to reference RMS into MIDI velocity [1, 127]."""
    if ref_rms <= 1e-9 or rms_val <= 1e-9:
        return int((base_min + base_max) // 2)
    ratio = np.clip(rms_val / (ref_rms * 1.6), 0.15, 1.25)
    norm = (ratio - 0.15) / 1.10
    vel = int(round(base_min + norm * (base_max - base_min)))
    return int(np.clip(vel, 1, 127))


def transcribe_melody_notes(
    y: np.ndarray,
    sr: int = 22050,
    hop_length: int = 512,
    min_midi: int = 52,
    max_midi: int = 92,
    min_note_duration: float = 0.07,
    beat_times: Optional[List[float]] = None,
    scale_pcs: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    """
    Extracts monophonic lead melody notes from a vocal or harmonic lead signal.

    Returns a list of note dictionaries:
        {
            "midi": int,
            "note": str,
            "start": float,
            "end": float,
            "velocity": int,
            "confidence": float,
            "source": "melody"
        }
    """
    if y is None or len(y) < sr * 0.1:
        return []

    frame_dt = float(hop_length) / float(sr)
    n_fft = 2048

    # Compute RMS energy per frame
    rms = librosa.feature.rms(y=y, frame_length=n_fft, hop_length=hop_length)[0]
    active_rms = rms[rms > 1e-4]
    if len(active_rms) == 0:
        return []

    ref_rms = float(np.percentile(active_rms, 75))
    energy_gate = max(1e-4, float(np.percentile(active_rms, 15)) * 0.40)

    # Compute onset strength envelope for syllable / re-strike segmentation
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)
    onset_frames = set(
        librosa.onset.onset_detect(
            onset_envelope=onset_env,
            sr=sr,
            hop_length=hop_length,
            backtrack=False,
            delta=0.18,
            wait=3,
        ).tolist()
    )

    # Track fundamental pitch using harmonic salience over CQT / YIN
    fmin = float(midi_to_freq_exact(min_midi))
    fmax = float(midi_to_freq_exact(max_midi))
    try:
        f0 = librosa.yin(y, fmin=fmin, fmax=fmax, sr=sr, frame_length=n_fft, hop_length=hop_length)
    except Exception:
        return []

    n_frames = min(len(f0), len(rms), len(onset_env))
    if n_frames == 0:
        return []

    f0 = f0[:n_frames]
    rms = rms[:n_frames]

    # Convert valid frequencies to MIDI float and apply median filter to stabilize vocal vibrato
    raw_midi = np.zeros(n_frames, dtype=np.float32)
    voiced = np.zeros(n_frames, dtype=bool)

    # Compute spectral flatness to reject unvoiced consonants / breath / sibilance
    flatness = librosa.feature.spectral_flatness(y=y, n_fft=n_fft, hop_length=hop_length)[0][:n_frames]

    for i in range(n_frames):
        freq = f0[i]
        if rms[i] >= energy_gate and flatness[i] < 0.22 and fmin <= freq <= fmax:
            m_val = freq_to_midi_exact(freq)
            if min_midi <= m_val <= max_midi:
                raw_midi[i] = m_val
                voiced[i] = True

    # Smooth vibrato over ~5 frames (~115ms) while preserving step transitions
    quant_midi = np.round(raw_midi).astype(np.int32)
    smoothed_midi = median_filter(quant_midi, size=5)
    smoothed_midi[~voiced] = 0

    # Snap out-of-scale semitone glitches if neighbor is in scale and duration is 1-2 frames
    if scale_pcs:
        scale_set = set(int(pc) % 12 for pc in scale_pcs)
        for i in range(1, n_frames - 1):
            m = int(smoothed_midi[i])
            if m > 0 and (m % 12) not in scale_set:
                prev_m = int(smoothed_midi[i - 1])
                next_m = int(smoothed_midi[i + 1])
                if prev_m > 0 and (prev_m % 12) in scale_set and abs(prev_m - m) == 1:
                    smoothed_midi[i] = prev_m
                elif next_m > 0 and (next_m % 12) in scale_set and abs(next_m - m) == 1:
                    smoothed_midi[i] = next_m

    # Segment frame sequence into discrete note events
    notes: List[Dict[str, Any]] = []
    cur_midi = 0
    start_frame = 0
    frame_rms_vals: List[float] = []

    def _commit_note(m_val: int, s_idx: int, e_idx: int, r_vals: List[float]):
        if m_val <= 0:
            return
        t_start = round(s_idx * frame_dt, 4)
        t_end = round(e_idx * frame_dt, 4)
        dur = t_end - t_start
        if dur < min_note_duration:
            return
        mean_r = float(np.mean(r_vals)) if r_vals else ref_rms
        vel = _rms_to_velocity(mean_r, ref_rms, base_min=78, base_max=108)
        conf = float(np.clip(mean_r / (ref_rms + 1e-9), 0.55, 0.98))
        notes.append({
            "midi": int(m_val),
            "note": midi_to_note_name(int(m_val)),
            "start": t_start,
            "end": t_end,
            "velocity": vel,
            "confidence": round(conf, 3),
            "source": "melody",
        })

    for i in range(n_frames):
        m = int(smoothed_midi[i])
        is_rearticulation = (i in onset_frames) and (i - start_frame >= 4)
        if m != cur_midi or (m > 0 and is_rearticulation):
            if cur_midi > 0:
                _commit_note(cur_midi, start_frame, i, frame_rms_vals)
            cur_midi = m
            start_frame = i
            frame_rms_vals = [float(rms[i])] if m > 0 else []
        else:
            if m > 0:
                frame_rms_vals.append(float(rms[i]))

    if cur_midi > 0:
        _commit_note(cur_midi, start_frame, n_frames, frame_rms_vals)

    # Merge micro-gaps (< 45ms) between identical consecutive pitches caused by brief consonant dips
    merged: List[Dict[str, Any]] = []
    for n in notes:
        if (
            merged
            and merged[-1]["midi"] == n["midi"]
            and (n["start"] - merged[-1]["end"]) < 0.055
            and (n["end"] - merged[-1]["start"]) <= 2.5
        ):
            merged[-1]["end"] = n["end"]
            merged[-1]["velocity"] = max(merged[-1]["velocity"], n["velocity"])
        else:
            merged.append(n)

    if beat_times and len(beat_times) >= 2:
        merged = quantize_notes_to_grid(merged, beat_times, max_snap_sec=0.035)

    return merged


def transcribe_polyphonic_accompaniment(
    y_harm: np.ndarray,
    sr: int = 22050,
    y_bass: Optional[np.ndarray] = None,
    hop_length: int = 512,
    min_midi: int = 28,
    max_midi: int = 88,
    max_polyphony: int = 4,
    min_note_duration: float = 0.09,
    beat_times: Optional[List[float]] = None,
) -> List[Dict[str, Any]]:
    """
    Extracts polyphonic accompaniment and bass notes from harmonic and bass audio signals.

    Uses multi-harmonic comb salience (`PolyphonicPitchDetector`) with temporal hysteresis
    and onset re-articulation detection.
    """
    if y_harm is None or len(y_harm) < sr * 0.1:
        return []

    n_fft = 4096
    step_hop = hop_length * 2  # ~46ms step for fast, clean polyphonic tracking
    frame_dt = float(step_hop) / float(sr)

    detector = PolyphonicPitchDetector(
        sample_rate=sr,
        n_fft=n_fft,
        hop_size=step_hop,
        min_midi=min_midi,
        max_midi=max_midi,
        energy_threshold=0.006,
        peak_threshold=0.13,
        max_polyphony=max_polyphony,
    )

    onset_env = librosa.onset.onset_strength(y=y_harm, sr=sr, hop_length=step_hop)
    onset_frames = set(
        librosa.onset.onset_detect(
            onset_envelope=onset_env,
            sr=sr,
            hop_length=step_hop,
            backtrack=False,
            delta=0.16,
            wait=2,
        ).tolist()
    )

    total_samples = len(y_harm)
    n_frames = max(1, (total_samples - n_fft) // step_hop + 1)

    # Track active note spans: midi -> {start_frame, last_frame, confs, rms_vals, missing}
    active_tracks: Dict[int, Dict[str, Any]] = {}
    completed_notes: List[Dict[str, Any]] = []
    all_rms: List[float] = []

    for f_idx in range(n_frames):
        sample_start = f_idx * step_hop
        frame = y_harm[sample_start : sample_start + n_fft]
        res = detector.detect_frame(frame)
        f_rms = float(res.get("rms", 0.0))
        if f_rms > 1e-4:
            all_rms.append(f_rms)

        detected_map = {n.midi: n for n in res.get("notes", [])}
        is_onset = f_idx in onset_frames

        # Update existing tracks
        for midi in list(active_tracks.keys()):
            trk = active_tracks[midi]
            if midi in detected_map:
                # If a sharp onset occurs after note has been ringing for >= 3 frames, re-articulate
                if is_onset and (f_idx - trk["start_frame"]) >= 3 and f_rms > trk["rms_vals"][-1] * 1.25:
                    completed_notes.append(trk)
                    active_tracks[midi] = {
                        "midi": midi,
                        "start_frame": f_idx,
                        "last_frame": f_idx + 1,
                        "confs": [detected_map[midi].confidence],
                        "rms_vals": [f_rms],
                        "missing": 0,
                        "source": "accompaniment",
                    }
                else:
                    trk["last_frame"] = f_idx + 1
                    trk["confs"].append(detected_map[midi].confidence)
                    trk["rms_vals"].append(f_rms)
                    trk["missing"] = 0
            else:
                trk["missing"] += 1
                if trk["missing"] >= 2:
                    completed_notes.append(trk)
                    del active_tracks[midi]

        # Start new tracks for newly detected notes
        for midi, det_note in detected_map.items():
            if midi not in active_tracks:
                active_tracks[midi] = {
                    "midi": midi,
                    "start_frame": f_idx,
                    "last_frame": f_idx + 1,
                    "confs": [det_note.confidence],
                    "rms_vals": [f_rms],
                    "missing": 0,
                    "source": "accompaniment",
                }

    for trk in active_tracks.values():
        completed_notes.append(trk)

    # Optional dedicated bass stem extraction (MIDI 28 to 55)
    if y_bass is not None and len(y_bass) >= sr * 0.1:
        bass_notes = _extract_bass_stem_notes(y_bass, sr=sr, hop_length=hop_length)
        completed_notes.extend(bass_notes)

    ref_rms = float(np.percentile(all_rms, 75)) if all_rms else 0.05

    output_notes: List[Dict[str, Any]] = []
    for trk in completed_notes:
        if "start" in trk and "end" in trk:
            # Already formatted from bass tracker
            if (trk["end"] - trk["start"]) >= min_note_duration:
                output_notes.append(trk)
            continue

        t_start = round(trk["start_frame"] * frame_dt, 4)
        t_end = round(trk["last_frame"] * frame_dt, 4)
        dur = t_end - t_start
        if dur < max(min_note_duration, 0.11):
            continue

        mean_rms = float(np.mean(trk["rms_vals"])) if trk["rms_vals"] else ref_rms
        vel = _rms_to_velocity(mean_rms, ref_rms, base_min=52, base_max=76)
        mean_conf = float(np.mean(trk["confs"])) if trk["confs"] else 0.7
        if mean_conf < 0.45:
            continue

        output_notes.append({
            "midi": int(trk["midi"]),
            "note": midi_to_note_name(int(trk["midi"])),
            "start": t_start,
            "end": t_end,
            "velocity": vel,
            "confidence": round(mean_conf, 3),
            "source": trk.get("source", "accompaniment"),
        })

    output_notes = _suppress_octave_ghosts_and_merge(output_notes)
    output_notes.sort(key=lambda n: (n["start"], n["midi"]))

    if beat_times and len(beat_times) >= 2:
        output_notes = quantize_notes_to_grid(output_notes, beat_times, max_snap_sec=0.04)

    return output_notes


def _suppress_octave_ghosts_and_merge(
    notes: List[Dict[str, Any]],
    gap_threshold: float = 0.05,
    max_merged_dur: float = 3.0,
) -> List[Dict[str, Any]]:
    """
    Merge micro-gapped identical pitches and suppress weak m+12 harmonic octave ghosts.
    """
    if not notes:
        return []

    # 1. Merge micro-gapped identical pitches per MIDI key
    by_midi: Dict[int, List[Dict[str, Any]]] = {}
    for n in sorted(notes, key=lambda x: (x["midi"], x["start"])):
        bucket = by_midi.setdefault(n["midi"], [])
        if (
            bucket
            and (n["start"] - bucket[-1]["end"]) < gap_threshold
            and (n["end"] - bucket[-1]["start"]) <= max_merged_dur
        ):
            prev = bucket[-1]
            prev["end"] = max(prev["end"], n["end"])
            prev["velocity"] = max(prev["velocity"], n["velocity"])
            prev["confidence"] = round(max(prev["confidence"], n["confidence"]), 3)
        else:
            bucket.append(dict(n))

    merged: List[Dict[str, Any]] = []
    for bucket in by_midi.values():
        merged.extend(bucket)
    merged.sort(key=lambda x: (x["start"], x["midi"]))

    # 2. Suppress simultaneous m+12 harmonic ghosts with noticeably lower confidence
    keep = [True] * len(merged)
    for i, upper in enumerate(merged):
        u_dur = max(1e-4, upper["end"] - upper["start"])
        u_midi = upper["midi"]
        for j, lower in enumerate(merged):
            if i == j or not keep[j]:
                continue
            if lower["start"] >= upper["end"]:
                break
            if lower["midi"] != u_midi - 12:
                continue
            overlap = min(upper["end"], lower["end"]) - max(upper["start"], lower["start"])
            if overlap >= 0.5 * u_dur and upper["confidence"] < lower["confidence"] * 0.78:
                keep[i] = False
                break

    return [n for idx, n in enumerate(merged) if keep[idx]]


def _extract_bass_stem_notes(
    y_bass: np.ndarray,
    sr: int = 22050,
    hop_length: int = 512,
    min_midi: int = 28,
    max_midi: int = 55,
) -> List[Dict[str, Any]]:
    """Extracts clean low-register bass notes from an isolated bass stem."""
    frame_dt = float(hop_length) / float(sr)
    n_fft = 2048
    rms = librosa.feature.rms(y=y_bass, frame_length=n_fft, hop_length=hop_length)[0]
    active_rms = rms[rms > 1e-4]
    if len(active_rms) == 0:
        return []

    ref_rms = float(np.percentile(active_rms, 75))
    gate = max(1e-4, float(np.percentile(active_rms, 25)) * 0.5)

    fmin = float(midi_to_freq_exact(min_midi))
    fmax = float(midi_to_freq_exact(max_midi))
    try:
        f0 = librosa.yin(y_bass, fmin=fmin, fmax=fmax, sr=sr, frame_length=n_fft, hop_length=hop_length)
    except Exception:
        return []

    n_frames = min(len(f0), len(rms))
    quant_midi = np.zeros(n_frames, dtype=np.int32)
    for i in range(n_frames):
        if rms[i] >= gate and fmin <= f0[i] <= fmax:
            m = int(round(freq_to_midi_exact(f0[i])))
            if min_midi <= m <= max_midi:
                quant_midi[i] = m

    smoothed = median_filter(quant_midi, size=5)
    smoothed[quant_midi == 0] = 0

    bass_notes: List[Dict[str, Any]] = []
    cur_m = 0
    s_frame = 0
    r_vals: List[float] = []

    for i in range(n_frames):
        m = int(smoothed[i])
        if m != cur_m:
            if cur_m > 0 and (i - s_frame) * frame_dt >= 0.12:
                mean_r = float(np.mean(r_vals)) if r_vals else ref_rms
                bass_notes.append({
                    "midi": cur_m,
                    "note": midi_to_note_name(cur_m),
                    "start": round(s_frame * frame_dt, 4),
                    "end": round(i * frame_dt, 4),
                    "velocity": _rms_to_velocity(mean_r, ref_rms, base_min=56, base_max=78),
                    "confidence": 0.82,
                    "source": "accompaniment",
                })
            cur_m = m
            s_frame = i
            r_vals = [float(rms[i])] if m > 0 else []
        elif m > 0:
            r_vals.append(float(rms[i]))

    if cur_m > 0 and (n_frames - s_frame) * frame_dt >= 0.12:
        mean_r = float(np.mean(r_vals)) if r_vals else ref_rms
        bass_notes.append({
            "midi": cur_m,
            "note": midi_to_note_name(cur_m),
            "start": round(s_frame * frame_dt, 4),
            "end": round(n_frames * frame_dt, 4),
            "velocity": _rms_to_velocity(mean_r, ref_rms, base_min=56, base_max=78),
            "confidence": 0.82,
            "source": "accompaniment",
        })

    # Merge consecutive identical-pitch bass notes separated by micro-gaps (< 0.06s)
    merged_bass: List[Dict[str, Any]] = []
    for n in bass_notes:
        if (
            merged_bass
            and merged_bass[-1]["midi"] == n["midi"]
            and (n["start"] - merged_bass[-1]["end"]) < 0.06
            and (n["end"] - merged_bass[-1]["start"]) <= 3.5
        ):
            merged_bass[-1]["end"] = max(merged_bass[-1]["end"], n["end"])
            merged_bass[-1]["velocity"] = max(merged_bass[-1]["velocity"], n["velocity"])
        else:
            merged_bass.append(n)

    return merged_bass


def quantize_notes_to_grid(
    notes: List[Dict[str, Any]],
    beat_times: List[float],
    subdivisions: int = 4,
    max_snap_sec: float = 0.04,
) -> List[Dict[str, Any]]:
    """
    Gently snaps note onsets and offsets to a subdivision grid (e.g., 16th notes)
    when within `max_snap_sec`, preserving intentional syncopation and human feel.
    """
    if not notes or not beat_times or len(beat_times) < 2:
        return notes

    # Build 16th-note subdivision grid from beat times
    grid: List[float] = []
    for i in range(len(beat_times) - 1):
        b0 = float(beat_times[i])
        b1 = float(beat_times[i + 1])
        step = (b1 - b0) / subdivisions
        for s in range(subdivisions):
            grid.append(b0 + s * step)
    grid.append(float(beat_times[-1]))
    grid_arr = np.array(grid, dtype=np.float64)

    quantized: List[Dict[str, Any]] = []
    for n in notes:
        n_copy = dict(n)
        s = float(n_copy["start"])
        e = float(n_copy["end"])
        orig_dur = max(0.08, e - s)

        idx = int(np.searchsorted(grid_arr, s))
        candidates = []
        if idx > 0:
            candidates.append(grid_arr[idx - 1])
        if idx < len(grid_arr):
            candidates.append(grid_arr[idx])

        if candidates:
            closest_s = min(candidates, key=lambda g: abs(g - s))
            if abs(closest_s - s) <= max_snap_sec:
                s = round(float(closest_s), 4)

        # Snap end or preserve duration
        e_target = s + orig_dur
        idx_e = int(np.searchsorted(grid_arr, e_target))
        e_cands = []
        if idx_e > 0:
            e_cands.append(grid_arr[idx_e - 1])
        if idx_e < len(grid_arr):
            e_cands.append(grid_arr[idx_e])
        if e_cands:
            closest_e = min(e_cands, key=lambda g: abs(g - e_target))
            if abs(closest_e - e_target) <= max_snap_sec and (closest_e - s) >= 0.08:
                e_target = float(closest_e)

        n_copy["start"] = round(s, 4)
        n_copy["end"] = round(max(s + 0.08, e_target), 4)
        quantized.append(n_copy)

    return quantized
