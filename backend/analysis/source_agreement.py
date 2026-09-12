"""
backend/analysis/source_agreement.py

Musical Source Agreement & Bass Fusion Engine for HotChords.
Evaluates cross-source harmonic consistency across candidate chord sequences
and performs musically informed bass root and slash-chord inversion fusion.
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import librosa
from backend.theory.theory import NOTE_NAMES, NOTE_FLAT, get_pitch_class, chord_note_indices, musician_friendly_name


def parse_chord_root_and_quality(chord_str: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Parses a chord symbol into (root, quality, bass).
    e.g. 'C' -> ('C', 'maj', None)
         'Am7' -> ('A', 'min7', None)
         'C/E' -> ('C', 'maj', 'E')
         'N' -> (None, 'N', None)
    """
    if not chord_str or chord_str == "N":
        return None, "N", None

    slash_parts = chord_str.split("/")
    main_chord = slash_parts[0].strip()
    bass = slash_parts[1].strip() if len(slash_parts) > 1 else None

    # Identify root note
    root = None
    quality = ""
    if len(main_chord) >= 2 and main_chord[1] in ["#", "b"]:
        root = main_chord[:2]
        quality = main_chord[2:]
    elif len(main_chord) >= 1:
        root = main_chord[:1]
        quality = main_chord[1:]

    return root, quality, bass


def evaluate_chord_compatibility(c1_str: Optional[str], c2_str: Optional[str]) -> float:
    """
    Computes musical compatibility score [0.0, 1.0] between two chord symbols.
    
    Scoring:
    - 1.00: Exact chord match or both 'N'
    - 0.90: Matching root and primary triad type (e.g. C vs C7, Am vs Am7)
    - 0.85: Slash chord inversion match (e.g. C vs C/E)
    - 0.70: Root match with different quality (e.g. C vs Cm)
    - 0.50: Common diatonic neighbor (e.g. relative major/minor or 4th/5th)
    - 0.00: Dissonant clash or mismatch
    """
    if c1_str == c2_str:
        return 1.0

    if not c1_str or not c2_str:
        return 0.5

    if c1_str == "N" and c2_str == "N":
        return 1.0
    if c1_str == "N" or c2_str == "N":
        return 0.15

    r1, q1, b1 = parse_chord_root_and_quality(c1_str)
    r2, q2, b2 = parse_chord_root_and_quality(c2_str)

    if not r1 or not r2:
        return 0.2

    pc1 = get_pitch_class(r1)
    pc2 = get_pitch_class(r2)

    # Identical root note
    if pc1 == pc2:
        # Simplify quality comparison
        q1_clean = q1.lower().replace("maj", "").replace("min", "m")
        q2_clean = q2.lower().replace("maj", "").replace("min", "m")
        if q1_clean == q2_clean:
            return 1.0
        # Triad vs 7th extension
        if ("7" in q1_clean or "7" in q2_clean) or ("sus" in q1_clean or "sus" in q2_clean):
            return 0.90
        # Major vs minor with same root
        return 0.70

    # Inversion / Bass note agreement (e.g. C/E compared with E or Em)
    if b1 and get_pitch_class(b1) == pc2:
        return 0.80
    if b2 and get_pitch_class(b2) == pc1:
        return 0.80

    # Fifth relationship (e.g. C and G, root distance 7 or 5 semitones)
    interval = abs(pc1 - pc2) % 12
    if interval in [5, 7]:
        return 0.50
    # Relative major/minor (root distance 3 or 9 semitones)
    if interval in [3, 9]:
        return 0.55

    return 0.05


def compute_source_agreement(
    source_chords: Dict[str, List[Dict[str, Any]]],
    duration: float,
    time_step: float = 0.25
) -> Optional[float]:
    """
    Computes cross-source musical agreement across multiple candidate chord sequences.
    
    Parameters
    ----------
    source_chords : Dict[str, List[Dict[str, Any]]]
        Dictionary mapping source names (e.g. 'mix', 'other', 'bass') to chord events.
    duration : float
        Total duration in seconds.
    time_step : float
        Sampling grid interval in seconds.

    Returns
    -------
    Optional[float]
        Mean musical agreement score in [0.0, 1.0], or None if fewer than 2 valid sources exist.
    """
    active_sources = [k for k, v in source_chords.items() if v and len(v) > 0]
    if len(active_sources) < 2 or duration <= 0:
        return None

    times = np.arange(0.0, duration, time_step)
    if len(times) == 0:
        return None

    # Sample chord symbols per source on the uniform time grid
    grid: Dict[str, List[str]] = {src: [] for src in active_sources}

    for src in active_sources:
        events = source_chords[src]
        ev_idx = 0
        n_ev = len(events)
        for t in times:
            while ev_idx < n_ev - 1 and events[ev_idx].get("end", events[ev_idx].get("endTime", 0.0)) <= t:
                ev_idx += 1
            cur = events[ev_idx]
            t0 = cur.get("time", cur.get("startTime", 0.0))
            t1 = cur.get("end", cur.get("endTime", t0 + 0.5))
            if t0 <= t <= t1:
                grid[src].append(cur.get("chord", cur.get("chordName", "N")))
            else:
                grid[src].append("N")

    # Pairwise comparison across sources over all time points
    pairwise_scores = []
    src_list = active_sources
    for i in range(len(src_list)):
        for j in range(i + 1, len(src_list)):
            s1, s2 = src_list[i], src_list[j]
            seq1, seq2 = grid[s1], grid[s2]
            pair_comp = [
                evaluate_chord_compatibility(seq1[k], seq2[k])
                for k in range(len(times))
            ]
            pairwise_scores.append(float(np.mean(pair_comp)))

    if not pairwise_scores:
        return None

    return round(float(np.mean(pairwise_scores)), 3)


def extract_bass_pitch_classes(
    y_bass: np.ndarray,
    sr: int = 22050,
    hop_length: int = 512
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Extracts frame-level dominant pitch classes from a bass audio track
    using low-frequency CQT tuned to fundamental bass registers (E1~41Hz to C4~261Hz).
    """
    if y_bass is None or len(y_bass) < sr * 0.1:
        return np.array([]), np.array([])

    try:
        # 36 bins, 3 octaves starting at C1 (~32.7 Hz)
        cqt_bass = np.abs(librosa.cqt(
            y=y_bass,
            sr=sr,
            hop_length=hop_length,
            fmin=librosa.note_to_hz('C1'),
            n_bins=36,
            bins_per_octave=12
        ))
        
        # Fold octaves into 12 pitch classes
        chroma_bass = np.zeros((12, cqt_bass.shape[1]))
        for oct_idx in range(3):
            chroma_bass += cqt_bass[oct_idx*12:(oct_idx+1)*12, :]

        frame_times = librosa.frames_to_time(np.arange(chroma_bass.shape[1]), sr=sr, hop_length=hop_length)
        dominant_pc = np.argmax(chroma_bass, axis=0)
        return frame_times, dominant_pc
    except Exception:
        return np.array([]), np.array([])


def fuse_bass_evidence(
    chords: List[Dict[str, Any]],
    y_bass: Optional[np.ndarray] = None,
    bass_chords: Optional[List[Dict[str, Any]]] = None,
    sr: int = 22050
) -> List[Dict[str, Any]]:
    """
    Informs chord progressions with bass root and inversion evidence.
    
    Rules:
    1. If bass note matches a triad component other than root (e.g. 3rd or 5th)
       consistently over the chord duration, produces a slash chord (e.g. C/E or G/B).
    2. If bass note matches chord root, reinforces root confidence.
    3. Never fabricates random slash chords without clear harmonic justification.
    """
    if not chords:
        return []

    if y_bass is None and not bass_chords:
        return chords

    frame_times, bass_pcs = (np.array([]), np.array([]))
    if y_bass is not None and len(y_bass) >= sr * 0.2:
        frame_times, bass_pcs = extract_bass_pitch_classes(y_bass, sr=sr)

    fused_chords = []

    for c in chords:
        c_copy = dict(c)
        c_name = c.get("chord", c.get("chordName", "N"))
        t0 = float(c.get("time", c.get("startTime", 0.0)))
        t1 = float(c.get("end", c.get("endTime", t0 + 0.5)))

        if c_name == "N" or "/" in c_name:
            fused_chords.append(c_copy)
            continue

        root, quality, _ = parse_chord_root_and_quality(c_name)
        if not root:
            fused_chords.append(c_copy)
            continue

        root_pc = get_pitch_class(root)
        note_indices = chord_note_indices(c_name)

        # 1. Determine dominant bass pitch class during this chord window
        dominant_bass_pc = None
        if len(frame_times) > 0 and len(bass_pcs) > 0:
            mask = (frame_times >= t0) & (frame_times < t1)
            if np.any(mask):
                window_pcs = bass_pcs[mask]
                counts = np.bincount(window_pcs, minlength=12)
                top_pc = int(np.argmax(counts))
                # Require >= 50% persistence during the chord duration
                if counts[top_pc] / len(window_pcs) >= 0.50:
                    dominant_bass_pc = top_pc

        # Fallback to bass chord sequence if audio CQT is ambiguous
        if dominant_bass_pc is None and bass_chords:
            for bc in bass_chords:
                bt0 = float(bc.get("time", bc.get("startTime", 0.0)))
                bt1 = float(bc.get("end", bc.get("endTime", bt0 + 0.5)))
                if max(t0, bt0) < min(t1, bt1):
                    b_root, _, _ = parse_chord_root_and_quality(bc.get("chord", bc.get("chordName", "N")))
                    if b_root:
                        dominant_bass_pc = get_pitch_class(b_root)
                        break

        # 2. Check if dominant bass note is an inversion of the active chord
        if dominant_bass_pc is not None and dominant_bass_pc in note_indices:
            bass_note_name = NOTE_NAMES[dominant_bass_pc]
            if dominant_bass_pc != root_pc:
                # Bass plays 3rd, 5th, or 7th -> create slash chord (e.g. C/E)
                slash_name = f"{c_name}/{bass_note_name}"
                c_copy["chord"] = slash_name
                c_copy["bass"] = bass_note_name
                c_copy["inversion"] = True
                c_copy["raw_chord"] = slash_name
            else:
                # Bass confirms chord root
                c_copy["bass"] = root
                c_copy["root_reinforced"] = True

        fused_chords.append(c_copy)

    return fused_chords
