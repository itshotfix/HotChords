"""
backend/theory/piano_arrangement.py

Native Piano Arrangement, Hand Separation, Biomechanical Fingering, and Grand Staff
Notation Synthesizer for HotChords.

Responsibilities:
1. Fuses transcribed melody notes, polyphonic accompaniment notes, and recognized
   chord progressions into two distinct, musically balanced piano arrangements:
   - Intermediate Arrangement (`notes`):
       * Right Hand: Lead melody (velocity ~96-108) + harmonic accompaniment fills
         during melodic rests and consonant harmonic dyads/triads.
       * Left Hand: Polyphonic bass lines, arpeggiated chord patterns, and root-fifth
         harmonic anchors (velocity ~58-68).
   - Beginner Arrangement (`beginner_notes`):
       * Right Hand: Clean, single-line playable melody + essential melodic hooks.
       * Left Hand: Beat-aligned harmonic triads or root-fifth shells voiced in C2-C4
         with ergonomic 5-3-1 fingering (velocity ~56).
2. Biomechanical Fingering Solver (`assign_biomechanical_fingering`):
   - Assigns human-playable fingers (1=Thumb, 2=Index, 3=Middle, 4=Ring, 5=Pinky)
     and canonical HotChords pedagogical finger colors (#FF4D4F .. #1677FF).
   - Enforces max hand span (<= 12 semitones) and smooth stepwise finger transitions.
3. Grand Staff Notation Builder (`build_grand_staff_notation`):
   - Produces measure-by-measure Treble (RH) and Bass (LH) staff events from the
     canonical note & chord timeline so the Sheet Music View shares the single
     authoritative timeline.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional, Tuple
import math

from backend.theory.piano_voicing import (
    FINGER_COLORS,
    PITCH_CLASS_MAP,
    CHORD_INTERVALS,
    midi_to_note_name,
    parse_chord_components,
    voice_chord,
)


BLACK_KEY_PCS = {1, 3, 6, 8, 10}


def _find_active_chord(time_sec: float, chords: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Finds the active chord dictionary at `time_sec`."""
    if not chords:
        return None
    for c in chords:
        s = float(c.get("time", c.get("startTime", c.get("start", 0.0))))
        e = float(c.get("end", c.get("endTime", s + 2.0)))
        if s - 0.05 <= time_sec <= e + 0.05:
            return c
    return None


def _chord_pitch_classes(chord_name: str) -> List[int]:
    """Returns pitch classes [0..11] belonging to `chord_name`."""
    root, quality, bass = parse_chord_components(chord_name)
    if not root or root not in PITCH_CLASS_MAP:
        return [0, 4, 7]
    root_pc = PITCH_CLASS_MAP[root]
    intervals = CHORD_INTERVALS.get(quality, [0, 4, 7])
    pcs = [(root_pc + iv) % 12 for iv in intervals]
    if bass and bass in PITCH_CLASS_MAP:
        b_pc = PITCH_CLASS_MAP[bass]
        if b_pc not in pcs:
            pcs.insert(0, b_pc)
    return pcs


def _build_lh_beginner_triad(chord_name: str, prefer_flat: bool = False) -> List[Tuple[int, int]]:
    """
    Builds an ergonomic Left-Hand 3-note triad (or root-fifth-octave shell) in MIDI range 40..59
    with classical 5-3-1 fingering: (midi, finger).
    """
    root, quality, bass = parse_chord_components(chord_name)
    if not root or root not in PITCH_CLASS_MAP:
        return []

    root_pc = PITCH_CLASS_MAP[bass] if (bass and bass in PITCH_CLASS_MAP) else PITCH_CLASS_MAP[root]
    intervals = CHORD_INTERVALS.get(quality, [0, 4, 7])
    third_iv = intervals[1] if len(intervals) > 1 else 4
    fifth_iv = intervals[2] if len(intervals) > 2 else 7

    # Place root between E2 (40) andEb3 (51)
    base_midi = 48 + root_pc
    while base_midi > 52:
        base_midi -= 12
    while base_midi < 40:
        base_midi += 12

    m_root = base_midi
    m_third = base_midi + third_iv
    m_fifth = base_midi + fifth_iv

    return [
        (m_root, 5),   # Pinky on Root
        (m_third, 3),  # Middle on Third
        (m_fifth, 1),  # Thumb on Fifth
    ]


def _build_lh_intermediate_pattern(
    chord_name: str,
    start_time: float,
    end_time: float,
    tempo: float = 120.0,
) -> List[Dict[str, Any]]:
    """
    Generates an expressive Left-Hand arpeggio / root-fifth-octave accompaniment pattern
    when raw bass/accompaniment stems are sparse over a chord span.
    """
    root, quality, bass = parse_chord_components(chord_name)
    if not root or root not in PITCH_CLASS_MAP:
        return []

    dur = end_time - start_time
    if dur < 0.15:
        return []

    root_pc = PITCH_CLASS_MAP[bass] if (bass and bass in PITCH_CLASS_MAP) else PITCH_CLASS_MAP[root]
    intervals = CHORD_INTERVALS.get(quality, [0, 4, 7])
    third_iv = intervals[1] if len(intervals) > 1 else 4
    fifth_iv = intervals[2] if len(intervals) > 2 else 7

    # Place bass root in C2 (36) .. B2 (47)
    r_midi = 36 + root_pc
    if r_midi < 36:
        r_midi += 12
    fifth_midi = r_midi + fifth_iv
    oct_midi = r_midi + 12
    tenth_midi = oct_midi + third_iv

    beat_sec = 60.0 / max(40.0, min(220.0, float(tempo or 120.0)))
    step = beat_sec / 2.0  # 8th-note arpeggio pulse

    pattern_pitches = [
        (r_midi, 5, 64),
        (fifth_midi, 2, 58),
        (oct_midi, 1, 60),
        (tenth_midi if tenth_midi <= 58 else fifth_midi, 1 if tenth_midi <= 58 else 2, 56),
    ]

    generated: List[Dict[str, Any]] = []
    t = start_time
    idx = 0
    while t + 0.08 < end_time:
        n_end = min(end_time, t + max(0.18, step * 0.92))
        p_midi, p_finger, p_vel = pattern_pitches[idx % len(pattern_pitches)]
        generated.append({
            "midi": int(p_midi),
            "note": midi_to_note_name(int(p_midi)),
            "start": round(t, 4),
            "end": round(n_end, 4),
            "velocity": int(p_vel),
            "hand": "left",
            "source": "chord",
            "finger": int(p_finger),
            "chord": chord_name,
        })
        t += step
        idx += 1

    return generated


def assign_biomechanical_fingering(
    notes: List[Dict[str, Any]],
    hand: str = "right",
) -> List[Dict[str, Any]]:
    """
    Assigns ergonomic piano fingerings (1=Thumb .. 5=Pinky) and HotChords pedagogical
    finger colors to a sequence of notes for a single hand ('left' or 'right').

    Handles both simultaneous chord clusters and sequential melodic lines:
    - Chord clusters (notes starting within 35ms): sorted by pitch and mapped to
      anatomical finger ordering (RH: low->high = 1..5; LH: low->high = 5..1).
    - Sequential notes: dynamic transition rules avoiding repeated fingers on different
      pitches and minimizing awkward thumb-on-black-key placements.
    """
    if not notes:
        return []

    # Sort by onset time then MIDI pitch
    sorted_notes = [dict(n) for n in sorted(notes, key=lambda x: (float(x["start"]), int(x["midi"])))]

    # Group into simultaneous onset clusters (within 35ms)
    clusters: List[List[Dict[str, Any]]] = []
    for n in sorted_notes:
        if not clusters or abs(float(n["start"]) - float(clusters[-1][0]["start"])) > 0.035:
            clusters.append([n])
        else:
            clusters[-1].append(n)

    # First assign polyphonic clusters deterministically, keeping track of fixed anchors
    fixed_finger: List[Optional[int]] = [None] * len(clusters)
    anchor_midi: List[int] = [0] * len(clusters)

    for idx_c, cluster in enumerate(clusters):
        cluster.sort(key=lambda x: int(x["midi"]))
        k = len(cluster)

        if k > 1:
            # Polyphonic / dyad / triad cluster in one hand
            span = int(cluster[-1]["midi"]) - int(cluster[0]["midi"])
            if hand == "right":
                if k == 2:
                    f_map = [1, 3] if span <= 4 else ([1, 4] if span <= 6 else [1, 5])
                elif k == 3:
                    f_map = [1, 3, 5] if span <= 9 else [1, 2, 5]
                elif k == 4:
                    f_map = [1, 2, 3, 5]
                else:
                    f_map = [1, 2, 3, 4, 5][:k]
            else:
                # Left hand: lowest note gets Pinky (5), highest gets Thumb (1)
                if k == 2:
                    f_map = [5, 2] if span <= 4 else ([5, 1])
                elif k == 3:
                    f_map = [5, 3, 1]
                elif k == 4:
                    f_map = [5, 3, 2, 1]
                else:
                    f_map = [5, 4, 3, 2, 1][:k]

            for idx, note in enumerate(cluster):
                assigned = note.get("finger")
                if assigned not in (1, 2, 3, 4, 5):
                    assigned = f_map[min(idx, len(f_map) - 1)]
                note["finger"] = int(assigned)
                note["color"] = FINGER_COLORS.get(int(assigned), "#FF4D4F")

            anchor = cluster[-1] if hand == "right" else cluster[0]
            anchor_midi[idx_c] = int(anchor["midi"])
            fixed_finger[idx_c] = int(anchor["finger"])
        else:
            note = cluster[0]
            anchor_midi[idx_c] = int(note["midi"])
            existing = note.get("finger")
            if existing in (1, 2, 3, 4, 5):
                fixed_finger[idx_c] = int(existing)

    # Viterbi DP over fingers 1..5 for optimal biomechanical single-note transitions
    n_cl = len(clusters)
    if n_cl > 0:
        INF = 1e9
        dp = [[INF] * 6 for _ in range(n_cl)]
        back = [[0] * 6 for _ in range(n_cl)]

        def _emit_cost(midi_val: int, finger: int) -> float:
            cost = 0.0
            is_black = (midi_val % 12) in BLACK_KEY_PCS
            if is_black:
                if finger == 1:
                    cost += 3.0
                elif finger == 5:
                    cost += 1.5
            if finger in (1, 5):
                cost += 0.2
            return cost

        def _trans_cost(pm: int, pf: int, cm: int, cf: int) -> float:
            diff = cm - pm
            if diff == 0:
                return 0.0 if cf == pf else 1.2
            # Right hand: ascending pitch -> ascending finger; Left hand: ascending pitch -> descending finger
            signed_f_diff = (cf - pf) if hand == "right" else (pf - cf)
            if (diff > 0 and signed_f_diff > 0) or (diff < 0 and signed_f_diff < 0):
                ideal_span = abs(cf - pf) * 2.0
                stretch = abs(abs(diff) - ideal_span)
                penalty = 0.35 * stretch
                if abs(diff) > 11:
                    penalty += 3.0
                return penalty
            if signed_f_diff == 0:
                return 2.2 + 0.35 * abs(diff)
            # Crossing over/under
            if cf == 1 or pf == 1:
                cross_cost = 1.3 + 0.3 * abs(diff)
                if cf == 1 and (cm % 12) in BLACK_KEY_PCS:
                    cross_cost += 2.5
                return cross_cost
            return 6.0 + 0.5 * abs(diff)

        # Initialize cluster 0
        m0 = anchor_midi[0]
        f0_fixed = fixed_finger[0]
        cands0 = [f0_fixed] if f0_fixed is not None else [1, 2, 3, 4, 5]
        for f in cands0:
            init_bias = 0.0
            if f0_fixed is None:
                if hand == "right":
                    init_bias = 0.0 if f in (2, 3) else 0.4
                else:
                    init_bias = 0.0 if f in (3, 5) else 0.4
            dp[0][f] = _emit_cost(m0, f) + init_bias

        # Forward pass
        for i in range(1, n_cl):
            mi = anchor_midi[i]
            mp = anchor_midi[i - 1]
            fi_fixed = fixed_finger[i]
            cands = [fi_fixed] if fi_fixed is not None else [1, 2, 3, 4, 5]
            for cf in cands:
                em = _emit_cost(mi, cf)
                best_val = INF
                best_pf = 3
                for pf in (1, 2, 3, 4, 5):
                    if dp[i - 1][pf] >= INF * 0.5:
                        continue
                    val = dp[i - 1][pf] + _trans_cost(mp, pf, mi, cf) + em
                    if val < best_val:
                        best_val = val
                        best_pf = pf
                dp[i][cf] = best_val
                back[i][cf] = best_pf

        # Backtrack
        best_last_f = min((1, 2, 3, 4, 5), key=lambda f: dp[n_cl - 1][f])
        chosen = [0] * n_cl
        chosen[n_cl - 1] = best_last_f
        for i in range(n_cl - 1, 0, -1):
            chosen[i - 1] = back[i][chosen[i]]

        for i, cluster in enumerate(clusters):
            if len(cluster) == 1:
                finger = int(max(1, min(5, chosen[i])))
                cluster[0]["finger"] = finger
                cluster[0]["color"] = FINGER_COLORS.get(finger, "#FF4D4F")

    # Flatten back into chronological order
    result = [n for cl in clusters for n in cl]
    result.sort(key=lambda x: (float(x["start"]), int(x["midi"])))
    return result


def _extract_monophonic_instrumental_hooks(
    rh_fills: List[Dict[str, Any]],
    rh_melody: List[Dict[str, Any]],
    min_midi: int = 44,
    max_midi: int = 84,
    vocal_guard_sec: float = 0.08,
    min_hook_dur: float = 0.12,
) -> List[Dict[str, Any]]:
    """
    Extract a clean monophonic top-line instrumental melody from accompaniment fills
    during vocal rests for Beginner Right Hand playability.
    """
    if not rh_fills:
        return []

    def _hook_salience(n: Dict[str, Any]) -> float:
        m = int(n["midi"])
        dur = max(0.05, float(n["end"]) - float(n["start"]))
        conf = float(n.get("confidence", 0.7))
        # Lead piano/flute/vocal register C4..A5 (60..81) preferred over extreme >84 overtones
        if 60 <= m <= 81:
            reg_w = 1.18
        elif 55 <= m < 60 or 81 < m <= 84:
            reg_w = 0.92
        else:
            reg_w = 0.78
        return conf * min(2.4, 0.65 + dur) * reg_w

    # Group fills into simultaneous onset clusters (60 ms window) and pick highest musical salience
    sorted_fills = sorted(rh_fills, key=lambda n: (float(n["start"]), -_hook_salience(n)))
    clusters: List[List[Dict[str, Any]]] = []
    for n in sorted_fills:
        midi_val = int(n["midi"])
        if midi_val < min_midi or midi_val > max_midi:
            continue
        if not clusters or abs(float(n["start"]) - float(clusters[-1][0]["start"])) > 0.060:
            clusters.append([n])
        else:
            clusters[-1].append(n)

    top_candidates: List[Dict[str, Any]] = []
    for cl in clusters:
        best = max(cl, key=_hook_salience)
        s = float(best["start"])
        e = float(best["end"])
        if e - s < min_hook_dur:
            continue
        # Skip if overlapping an active vocal melody note (with guard margin)
        overlaps_vocal = any(
            not (e <= float(m["start"]) - vocal_guard_sec or s >= float(m["end"]) + vocal_guard_sec)
            for m in rh_melody
        )
        if overlaps_vocal:
            continue
        top_candidates.append({
            "midi": int(best["midi"]),
            "note": best.get("note") or midi_to_note_name(int(best["midi"])),
            "start": round(s, 4),
            "end": round(e, 4),
            "velocity": int(max(58, min(80, best.get("velocity", 68)))),
            "confidence": float(best.get("confidence", 0.72)),
            "hand": "right",
            "source": "instrumental",
            "_salience": _hook_salience(best),
        })

    # Enforce monophonic non-overlapping output without letting brief blips truncate strong sustained leads
    mono: List[Dict[str, Any]] = []
    for cand in top_candidates:
        if mono and cand["start"] < mono[-1]["end"]:
            prev = mono[-1]
            prev_dur = prev["end"] - prev["start"]
            cand_dur = cand["end"] - cand["start"]
            if (
                prev_dur >= 0.60
                and cand_dur < 0.45
                and float(cand.get("confidence", 0.7)) < 0.68
                and cand["_salience"] < prev["_salience"] * 0.85
            ):
                continue
            if cand["start"] - prev["start"] >= min_hook_dur:
                prev["end"] = round(cand["start"], 4)
            else:
                if cand["_salience"] > prev["_salience"]:
                    mono.pop()
                else:
                    continue
        mono.append(cand)

    out: List[Dict[str, Any]] = []
    for n in mono:
        if (n["end"] - n["start"]) >= min_hook_dur:
            clean = dict(n)
            clean.pop("_salience", None)
            out.append(clean)
    return out


def generate_piano_arrangements(
    chords: List[Dict[str, Any]],
    beginner_chords: Optional[List[Dict[str, Any]]] = None,
    melody_notes: Optional[List[Dict[str, Any]]] = None,
    accompaniment_notes: Optional[List[Dict[str, Any]]] = None,
    tempo: float = 120.0,
    time_sig: str = "4/4",
    key: str = "C",
    scale: str = "Major",
    duration: float = 0.0,
) -> Dict[str, Any]:
    """
    Synthesizes complete Intermediate (`notes`) and Beginner (`beginner_notes`)
    piano arrangements + Grand Staff notation data from transcribed audio and chords.
    """
    melody_list = list(melody_notes or [])
    accomp_list = list(accompaniment_notes or [])
    orig_chords = list(chords or [])
    beg_chords = list(beginner_chords if beginner_chords is not None else orig_chords)

    # 1. Prepare Right-Hand Melody Line (transposed into comfortable RH range C4..C6 if needed)
    rh_melody: List[Dict[str, Any]] = []
    for m in melody_list:
        midi = int(m["midi"])
        while midi < 60:
            midi += 12
        while midi > 88:
            midi -= 12
        act_c = _find_active_chord(float(m["start"]), orig_chords)
        rh_melody.append({
            "midi": midi,
            "note": midi_to_note_name(midi),
            "start": round(float(m["start"]), 4),
            "end": round(float(m["end"]), 4),
            "velocity": int(m.get("velocity", 100)),
            "hand": "right",
            "source": "melody",
            "confidence": float(m.get("confidence", 0.9)),
            "chord": act_c.get("chord") if act_c else None,
        })

    # 2. Partition Accompaniment Notes into LH (< 60) and RH (>= 60), avoiding collisions with RH melody
    lh_accomp: List[Dict[str, Any]] = []
    rh_fills: List[Dict[str, Any]] = []

    for a in accomp_list:
        midi = int(a["midi"])
        s = float(a["start"])
        e = float(a["end"])
        act_c = _find_active_chord(s, orig_chords)
        c_name = act_c.get("chord") if act_c else None

        if midi < 60:
            # Clamp bass into clear piano register E1 (28) .. B3 (59)
            while midi < 28:
                midi += 12
            lh_accomp.append({
                "midi": midi,
                "note": midi_to_note_name(midi),
                "start": round(s, 4),
                "end": round(e, 4),
                "velocity": int(min(66, max(36, a.get("velocity", 62)))),
                "hand": "left",
                "source": "accompaniment",
                "confidence": float(a.get("confidence", 0.8)),
                "chord": c_name,
            })
        else:
            # Check if RH melody is active at this timestamp
            melody_collision = False
            for m in rh_melody:
                if not (e <= m["start"] + 0.02 or s >= m["end"] - 0.02):
                    # Simultaneous with melody: only keep if it forms a clean harmonic 3rd/6th below melody
                    interval = m["midi"] - midi
                    if interval not in (3, 4, 8, 9):
                        melody_collision = True
                        break
            if not melody_collision:
                rh_fills.append({
                    "midi": midi,
                    "note": midi_to_note_name(midi),
                    "start": round(s, 4),
                    "end": round(e, 4),
                    "velocity": int(min(68, a.get("velocity", 62))),
                    "hand": "right",
                    "source": "accompaniment",
                    "confidence": float(a.get("confidence", 0.8)),
                    "chord": c_name,
                })

    # 3. Ensure every chord segment in Intermediate and Beginner has rich musical content
    inter_lh: List[Dict[str, Any]] = list(lh_accomp)
    inter_rh: List[Dict[str, Any]] = list(rh_melody) + list(rh_fills)

    for c in orig_chords:
        c_name = c.get("chord", "N")
        if not c_name or c_name == "N":
            continue
        c_start = float(c.get("time", c.get("startTime", 0.0)))
        c_end = float(c.get("end", c.get("endTime", c_start + 2.0)))
        if c_end <= c_start + 0.05:
            continue

        # Check if LH already has notes in this chord window
        has_lh = any(not (n["end"] <= c_start + 0.05 or n["start"] >= c_end - 0.05) for n in inter_lh)
        if not has_lh:
            inter_lh.extend(_build_lh_intermediate_pattern(c_name, c_start, c_end, tempo=tempo))

        # Check if RH has any notes in this chord window; if completely empty, voice RH chord triad/arpeggio
        has_rh = any(not (n["end"] <= c_start + 0.05 or n["start"] >= c_end - 0.05) for n in inter_rh)
        if not has_rh:
            v = c.get("voicing") or voice_chord(c_name, beginner_mode=False)
            rh_v = v.get("rightHand", []) if isinstance(v, dict) else []
            for vn in rh_v:
                v_midi = int(vn.get("midi", 60))
                inter_rh.append({
                    "midi": v_midi,
                    "note": midi_to_note_name(v_midi),
                    "start": round(c_start, 4),
                    "end": round(c_end, 4),
                    "velocity": 72,
                    "hand": "right",
                    "source": "chord",
                    "finger": int(vn.get("finger", 1)),
                    "chord": c_name,
                })

    # 4. Build Beginner Arrangement:
    #    - Left Hand: Clean 5-3-1 block triads from `beg_chords`
    #    - Right Hand: Lead vocal melody (`rh_melody`) + monophonic instrumental hooks during
    #      vocal rests + essential RH chord tones only where no melody or hook exists
    beg_lh: List[Dict[str, Any]] = []
    beg_rh: List[Dict[str, Any]] = list(rh_melody)

    # Extract monophonic top-line instrumental hooks from rh_fills during vocal rests
    inst_hooks = _extract_monophonic_instrumental_hooks(
        rh_fills,
        rh_melody,
        min_midi=44,
        max_midi=84,
    )
    beg_rh.extend(inst_hooks)

    beats_per_bar = 3 if str(time_sig).startswith("3/") else 4
    bar_sec = beats_per_bar * (60.0 / max(40.0, min(220.0, float(tempo or 120.0))))

    for c in beg_chords:
        c_name = c.get("chord", "N")
        if not c_name or c_name == "N":
            continue
        c_start = float(c.get("time", c.get("startTime", 0.0)))
        c_end = float(c.get("end", c.get("endTime", c_start + 2.0)))
        if c_end <= c_start + 0.05:
            continue

        triad = _build_lh_beginner_triad(c_name)
        # Re-articulate Beginner LH block triads at bar boundaries for held multi-bar chords
        span_t = c_start
        bar_idx = 0
        while span_t + 0.15 < c_end:
            seg_end = min(c_end, span_t + bar_sec)
            if (c_end - seg_end) < 0.35:
                seg_end = c_end
            triad_vel = 56 if bar_idx == 0 else 52
            for t_midi, t_finger in triad:
                beg_lh.append({
                    "midi": int(t_midi),
                    "note": midi_to_note_name(int(t_midi)),
                    "start": round(span_t, 4),
                    "end": round(seg_end, 4),
                    "velocity": triad_vel,
                    "hand": "left",
                    "source": "chord",
                    "finger": int(t_finger),
                    "chord": c_name,
                })
            span_t = seg_end
            bar_idx += 1

        # If RH has no melody or instrumental hook during this beginner chord, add a clean RH tone
        has_beg_rh = any(not (n["end"] <= c_start + 0.05 or n["start"] >= c_end - 0.05) for n in beg_rh)
        if not has_beg_rh:
            v = c.get("voicing") or voice_chord(c_name, beginner_mode=True)
            rh_v = v.get("rightHand", []) if isinstance(v, dict) else []
            for vn in rh_v:
                v_midi = int(vn.get("midi", 64))
                beg_rh.append({
                    "midi": v_midi,
                    "note": midi_to_note_name(v_midi),
                    "start": round(c_start, 4),
                    "end": round(c_end, 4),
                    "velocity": 68,
                    "hand": "right",
                    "source": "accompaniment",
                    "finger": int(vn.get("finger", 1)),
                    "chord": c_name,
                })

    # 5. Run Biomechanical Fingering Solver on all 4 hand streams
    inter_lh_fingered = assign_biomechanical_fingering(inter_lh, hand="left")
    inter_rh_fingered = assign_biomechanical_fingering(inter_rh, hand="right")
    beg_lh_fingered = assign_biomechanical_fingering(beg_lh, hand="left")
    beg_rh_fingered = assign_biomechanical_fingering(beg_rh, hand="right")

    intermediate_notes = sorted(
        inter_lh_fingered + inter_rh_fingered,
        key=lambda x: (float(x["start"]), 0 if x["hand"] == "left" else 1, int(x["midi"])),
    )
    beginner_notes = sorted(
        beg_lh_fingered + beg_rh_fingered,
        key=lambda x: (float(x["start"]), 0 if x["hand"] == "left" else 1, int(x["midi"])),
    )

    # 6. Build Grand Staff Notation Measures from the canonical timeline
    notation = build_grand_staff_notation(
        intermediate_notes=intermediate_notes,
        beginner_notes=beginner_notes,
        chords=orig_chords,
        tempo=tempo,
        time_sig=time_sig,
        key=key,
        scale=scale,
        duration=duration,
    )

    return {
        "notes": intermediate_notes,
        "beginner_notes": beginner_notes,
        "notation": notation,
    }


def build_grand_staff_notation(
    intermediate_notes: List[Dict[str, Any]],
    beginner_notes: List[Dict[str, Any]],
    chords: List[Dict[str, Any]],
    tempo: float = 120.0,
    time_sig: str = "4/4",
    key: str = "C",
    scale: str = "Major",
    duration: float = 0.0,
) -> Dict[str, Any]:
    """
    Constructs structured Grand Staff (Treble + Bass) measure data from the canonical
    note and chord timelines so the Sheet Music View renders in lockstep with audio.
    """
    beats_per_bar = 3 if str(time_sig).startswith("3") else 4
    beat_dur = 60.0 / max(40.0, min(220.0, float(tempo or 120.0)))
    measure_dur = beat_dur * beats_per_bar

    max_end = float(duration or 0.0)
    if intermediate_notes:
        max_end = max(max_end, max(float(n["end"]) for n in intermediate_notes))
    if chords:
        max_end = max(max_end, max(float(c.get("end", c.get("endTime", 0.0))) for c in chords))

    total_measures = max(1, int(math.ceil(max_end / measure_dur))) if max_end > 0 else 1

    measures: List[Dict[str, Any]] = []
    for m_idx in range(total_measures):
        m_start = round(m_idx * measure_dur, 4)
        m_end = round((m_idx + 1) * measure_dur, 4)

        # Find active chords in this measure
        m_chords = [
            {
                "chord": c.get("chord", c.get("chordName", "N")),
                "start": round(float(c.get("time", c.get("startTime", m_start))), 4),
                "end": round(float(c.get("end", c.get("endTime", m_end))), 4),
            }
            for c in chords
            if not (
                float(c.get("end", c.get("endTime", 0.0))) <= m_start + 0.02
                or float(c.get("time", c.get("startTime", 0.0))) >= m_end - 0.02
            )
            and c.get("chord", c.get("chordName", "N")) != "N"
        ]

        treble_notes = [
            n for n in intermediate_notes
            if n.get("hand") == "right" and (m_start - 0.02 <= float(n["start"]) < m_end - 0.02)
        ]
        bass_notes = [
            n for n in intermediate_notes
            if n.get("hand") == "left" and (m_start - 0.02 <= float(n["start"]) < m_end - 0.02)
        ]

        beg_treble_notes = [
            n for n in beginner_notes
            if n.get("hand") == "right" and (m_start - 0.02 <= float(n["start"]) < m_end - 0.02)
        ]
        beg_bass_notes = [
            n for n in beginner_notes
            if n.get("hand") == "left" and (m_start - 0.02 <= float(n["start"]) < m_end - 0.02)
        ]

        measures.append({
            "index": m_idx + 1,
            "startTime": m_start,
            "endTime": m_end,
            "chords": m_chords,
            "trebleNotes": treble_notes,
            "bassNotes": bass_notes,
            "beginnerTrebleNotes": beg_treble_notes,
            "beginnerBassNotes": beg_bass_notes,
        })

    return {
        "clef": "grand",
        "key_signature": f"{key} {scale}".strip(),
        "time_signature": time_sig,
        "tempo": round(float(tempo or 120.0), 1),
        "measure_duration": round(measure_dur, 4),
        "measures": measures,
    }
