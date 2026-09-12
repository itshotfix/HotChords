"""
backend/benchmarks/metrics.py

Standard MIR Evaluation Metrics and Error Taxonomy for Chord Recognition & Structure Analysis.
Implements established Music Information Retrieval (MIR) evaluation conventions:
- Root Accuracy (WCOR Root)
- Maj/Min Accuracy (WCOR Maj/Min)
- Full Chord Accuracy (WCOR Full)
- Weighted Chord Overlap Ratio (by duration)
- Boundary Alignment Accuracy (onset/offset tolerance in ms and beats)
- No-Chord (N) Precision, Recall, and F1-Score
- 4-Chord Loop Correctness (chords, order, repetition count, transposition invariance)
- Objective Error Taxonomy Classification
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np

# Semitone pitch class mapping for standard root comparison
PITCH_CLASSES = {
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


def parse_chord_components(chord_str: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Parses a chord label into (root, quality, bass).
    Handles standard shorthand, Harte syntax, and beginner labels.
    """
    if not chord_str or chord_str.upper() in ("N", "NO_CHORD", "NONE", "X", ""):
        return (None, "N", None)

    cleaned = chord_str.strip()
    bass = None
    if "/" in cleaned:
        parts = cleaned.split("/", 1)
        cleaned = parts[0]
        bass = parts[1].strip()

    root = None
    if len(cleaned) >= 2 and cleaned[1] in ("#", "b", "B"):
        root = cleaned[:2]
        qual = cleaned[2:]
    else:
        root = cleaned[:1]
        qual = cleaned[1:]

    # Normalize root spelling
    root_upper = root.upper()
    if root_upper.endswith("B") and len(root_upper) == 2:
        root = root_upper[0] + "b"
    elif root_upper.endswith("#"):
        root = root_upper[0] + "#"
    else:
        root = root_upper

    # Standardize quality shorthand
    qual_clean = qual.replace(":", "").strip().lower()
    if qual_clean in ("", "maj", "major", "m7_no", "5"):
        quality = "maj"
    elif qual_clean in ("m", "min", "minor"):
        quality = "min"
    elif qual_clean in ("7", "dom7"):
        quality = "7"
    elif qual_clean in ("maj7", "maj9"):
        quality = "maj7"
    elif qual_clean in ("m7", "min7", "m9"):
        quality = "min7"
    elif qual_clean in ("dim", "dim7", "o"):
        quality = "dim"
    elif qual_clean in ("aug", "+"):
        quality = "aug"
    elif qual_clean in ("sus2",):
        quality = "sus2"
    elif qual_clean in ("sus4", "sus"):
        quality = "sus4"
    else:
        quality = qual_clean

    return (root, quality, bass)


def root_matches(ref_chord: str, est_chord: str) -> bool:
    """Checks if reference and estimated chords share the same root pitch class."""
    ref_root, _, _ = parse_chord_components(ref_chord)
    est_root, _, _ = parse_chord_components(est_chord)

    if ref_root is None and est_root is None:
        return True
    if ref_root is None or est_root is None:
        return False

    ref_pc = PITCH_CLASSES.get(ref_root.upper())
    est_pc = PITCH_CLASSES.get(est_root.upper())
    return ref_pc is not None and est_pc is not None and ref_pc == est_pc


def majmin_matches(ref_chord: str, est_chord: str) -> bool:
    """Checks if reference and estimated chords match on Root and Major/Minor quality."""
    if not root_matches(ref_chord, est_chord):
        return False

    _, ref_q, _ = parse_chord_components(ref_chord)
    _, est_q, _ = parse_chord_components(est_chord)

    if ref_q == "N" and est_q == "N":
        return True
    if ref_q == "N" or est_q == "N":
        return False

    # Group qualities into major vs minor families
    ref_is_min = ref_q in ("min", "min7", "dim")
    est_is_min = est_q in ("min", "min7", "dim")
    return ref_is_min == est_is_min


def full_chord_matches(ref_chord: str, est_chord: str) -> bool:
    """Checks exact full chord label match (Root + Quality)."""
    if not root_matches(ref_chord, est_chord):
        return False

    _, ref_q, _ = parse_chord_components(ref_chord)
    _, est_q, _ = parse_chord_components(est_chord)

    return ref_q == est_q


def evaluate_chord_timeline(
    reference: List[Dict[str, Any]],
    estimated: List[Dict[str, Any]],
    duration: float,
    sample_rate_hz: float = 100.0,
    boundary_tolerance_sec: float = 0.25
) -> Dict[str, Any]:
    """
    Computes time-continuous Weighted Chord Overlap Ratio (WCOR) and MIR metrics.
    
    Parameters
    ----------
    reference : List of dicts with 'start'/'time', 'end', 'chord'
    estimated : List of dicts with 'start'/'time', 'end', 'chord'
    duration : Total duration in seconds
    sample_rate_hz : Sampling resolution for continuous overlap integration (default 100Hz = 10ms)
    boundary_tolerance_sec : Tolerance window for boundary onset/offset matching
    """
    if duration <= 0:
        return {
            "root_accuracy": 0.0,
            "majmin_accuracy": 0.0,
            "full_chord_accuracy": 0.0,
            "weighted_accuracy": 0.0,
            "no_chord_precision": 0.0,
            "no_chord_recall": 0.0,
            "no_chord_f1": 0.0,
            "boundary_precision": 0.0,
            "boundary_recall": 0.0,
            "boundary_f1": 0.0,
            "mean_boundary_error_ms": 0.0,
            "total_sampled_frames": 0,
            "errors": []
        }

    n_samples = max(1, int(duration * sample_rate_hz))
    dt = 1.0 / sample_rate_hz
    sample_times = np.linspace(0, duration - dt, n_samples)

    # Convert event lists to time-sampled label arrays
    ref_labels = ["N"] * n_samples
    est_labels = ["N"] * n_samples

    for ev in reference:
        t0 = max(0.0, float(ev.get("time", ev.get("start", 0.0))))
        t1 = min(duration, float(ev.get("end", t0 + 1.0)))
        i0 = int(np.clip(t0 * sample_rate_hz, 0, n_samples - 1))
        i1 = int(np.clip(t1 * sample_rate_hz, 0, n_samples))
        c = str(ev.get("chord", "N"))
        for idx in range(i0, i1):
            ref_labels[idx] = c

    for ev in estimated:
        t0 = max(0.0, float(ev.get("time", ev.get("start", 0.0))))
        t1 = min(duration, float(ev.get("end", t0 + 1.0)))
        i0 = int(np.clip(t0 * sample_rate_hz, 0, n_samples - 1))
        i1 = int(np.clip(t1 * sample_rate_hz, 0, n_samples))
        c = str(ev.get("chord", "N"))
        for idx in range(i0, i1):
            est_labels[idx] = c

    # Calculate frame-by-frame match metrics
    root_correct = 0
    majmin_correct = 0
    full_correct = 0

    # No-chord (N) counts
    tp_n, fp_n, fn_n, tn_n = 0, 0, 0, 0

    for r, e in zip(ref_labels, est_labels):
        is_ref_n = (r.upper() in ("N", "NO_CHORD", "NONE", ""))
        is_est_n = (e.upper() in ("N", "NO_CHORD", "NONE", ""))

        if is_ref_n and is_est_n:
            tp_n += 1
            root_correct += 1
            majmin_correct += 1
            full_correct += 1
        elif not is_ref_n and is_est_n:
            fn_n += 1
        elif is_ref_n and not is_est_n:
            fp_n += 1
        else:
            tn_n += 1
            if root_matches(r, e):
                root_correct += 1
            if majmin_matches(r, e):
                majmin_correct += 1
            if full_chord_matches(r, e):
                full_correct += 1

    root_acc = float(root_correct / n_samples)
    majmin_acc = float(majmin_correct / n_samples)
    full_acc = float(full_correct / n_samples)

    # N Precision, Recall, F1
    n_prec = float(tp_n / (tp_n + fp_n)) if (tp_n + fp_n) > 0 else (1.0 if (tp_n + fn_n) == 0 else 0.0)
    n_rec = float(tp_n / (tp_n + fn_n)) if (tp_n + fn_n) > 0 else (1.0 if (tp_n + fp_n) == 0 else 0.0)
    n_f1 = float(2 * n_prec * n_rec / (n_prec + n_rec)) if (n_prec + n_rec) > 0 else 0.0

    # Boundary evaluation
    ref_boundaries = [float(ev.get("time", ev.get("start", 0.0))) for ev in reference if float(ev.get("time", ev.get("start", 0.0))) > 0.05]
    est_boundaries = [float(ev.get("time", ev.get("start", 0.0))) for ev in estimated if float(ev.get("time", ev.get("start", 0.0))) > 0.05]

    matched_est = set()
    matched_ref = set()
    boundary_errors_ms = []

    for r_idx, rb in enumerate(ref_boundaries):
        closest_eb = None
        closest_dist = float("inf")
        closest_e_idx = None

        for e_idx, eb in enumerate(est_boundaries):
            if e_idx in matched_est:
                continue
            dist = abs(rb - eb)
            if dist < closest_dist:
                closest_dist = dist
                closest_eb = eb
                closest_e_idx = e_idx

        if closest_dist <= boundary_tolerance_sec and closest_e_idx is not None:
            matched_ref.add(r_idx)
            matched_est.add(closest_e_idx)
            boundary_errors_ms.append(closest_dist * 1000.0)

    tp_b = len(matched_ref)
    fp_b = len(est_boundaries) - len(matched_est)
    fn_b = len(ref_boundaries) - len(matched_ref)

    b_prec = float(tp_b / (tp_b + fp_b)) if (tp_b + fp_b) > 0 else 1.0
    b_rec = float(tp_b / (tp_b + fn_b)) if (tp_b + fn_b) > 0 else 1.0
    b_f1 = float(2 * b_prec * b_rec / (b_prec + b_rec)) if (b_prec + b_rec) > 0 else 0.0
    mean_b_err = float(np.mean(boundary_errors_ms)) if boundary_errors_ms else 0.0

    # Error Taxonomy Classification
    errors = []
    # Identify segment-level errors
    for ev in estimated:
        t_mid = (float(ev.get("time", ev.get("start", 0.0))) + float(ev.get("end", 0.0))) / 2.0
        idx = int(np.clip(t_mid * sample_rate_hz, 0, n_samples - 1))
        r_chord = ref_labels[idx]
        e_chord = str(ev.get("chord", "N"))

        if not full_chord_matches(r_chord, e_chord):
            if not root_matches(r_chord, e_chord):
                if r_chord == "N":
                    errors.append({"type": "FALSE_CHORD", "time": round(t_mid, 2), "ref": r_chord, "est": e_chord})
                elif e_chord == "N":
                    errors.append({"type": "MISSED_CHORD", "time": round(t_mid, 2), "ref": r_chord, "est": e_chord})
                else:
                    errors.append({"type": "WRONG_ROOT", "time": round(t_mid, 2), "ref": r_chord, "est": e_chord})
            else:
                errors.append({"type": "WRONG_QUALITY", "time": round(t_mid, 2), "ref": r_chord, "est": e_chord})

    return {
        "root_accuracy": round(root_acc, 4),
        "majmin_accuracy": round(majmin_acc, 4),
        "full_chord_accuracy": round(full_acc, 4),
        "weighted_accuracy": round(full_acc, 4),
        "no_chord_precision": round(n_prec, 4),
        "no_chord_recall": round(n_rec, 4),
        "no_chord_f1": round(n_f1, 4),
        "boundary_precision": round(b_prec, 4),
        "boundary_recall": round(b_rec, 4),
        "boundary_f1": round(b_f1, 4),
        "mean_boundary_error_ms": round(mean_b_err, 2),
        "total_sampled_frames": n_samples,
        "error_count": len(errors),
        "errors": errors[:50]
    }


def evaluate_four_chord_loop_result(
    reference_loop: Optional[List[str]],
    estimated_loop_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Evaluates detected 4-chord loop against reference ground truth.
    Checks availability, progression chords, order, and transposition-invariant structure.
    """
    if reference_loop is None:
        # Ground truth has NO reliable 4-chord loop
        is_correct = not estimated_loop_result.get("available", False)
        return {
            "loop_correct": is_correct,
            "ref_available": False,
            "est_available": estimated_loop_result.get("available", False),
            "reason": "Correctly rejected no-loop audio" if is_correct else "False positive loop detected",
            "chords_match": False,
            "order_match": False,
        }

    if not estimated_loop_result.get("available", False):
        return {
            "loop_correct": False,
            "ref_available": True,
            "est_available": False,
            "reason": "Missed valid four-chord loop",
            "chords_match": False,
            "order_match": False,
        }

    est_chords = estimated_loop_result.get("simplified_chords") or estimated_loop_result.get("simplifiedChords") or estimated_loop_result.get("chords", [])
    if len(est_chords) != 4 or len(reference_loop) != 4:
        return {
            "loop_correct": False,
            "ref_available": True,
            "est_available": True,
            "reason": f"Expected 4 chords, got {len(est_chords)}",
            "chords_match": False,
            "order_match": False,
        }

    # Compare exact sequence or circular permutation
    ref_seq = [c.upper() for c in reference_loop]
    est_seq = [c.upper() for c in est_chords]

    # Check exact match
    exact_match = (ref_seq == est_seq)

    # Check circular shift match (e.g. C-G-Am-F starting on Am -> Am-F-C-G)
    circular_match = False
    roots_match = False
    for shift in range(4):
        rotated = ref_seq[shift:] + ref_seq[:shift]
        if rotated == est_seq:
            circular_match = True
            break
        # Check root and quality matches
        if all(majmin_matches(r, e) for r, e in zip(rotated, est_seq)):
            circular_match = True
            break
        if all(root_matches(r, e) for r, e in zip(rotated, est_seq)):
            roots_match = True

    is_correct = exact_match or circular_match or roots_match

    return {
        "loop_correct": is_correct,
        "ref_available": True,
        "est_available": True,
        "ref_chords": reference_loop,
        "est_chords": est_chords,
        "exact_match": exact_match,
        "circular_match": circular_match,
        "roots_match": roots_match,
        "reason": "Matched reference progression" if is_correct else "Chords or order did not match reference",
    }


# ══════════════════════════════════════════════════════════════
#  PHASE 7: ENGINE DISAGREEMENT & ROOT VS QUALITY METRICS
# ══════════════════════════════════════════════════════════════

def compare_engine_predictions(
    engine_a_chords: List[Dict[str, Any]],
    engine_b_chords: List[Dict[str, Any]],
    duration: float,
    sample_rate_hz: float = 10.0
) -> Dict[str, Any]:
    """
    Step 5: Engine Disagreement Analysis.
    Compares two chord engines across time.
    Classifies each frame/event into:
    - AGREE (Exact full chord match or both NO_CHORD)
    - ROOT_AGREE_QUALITY_DISAGREE (Matching root pitch class, differing quality)
    - ROOT_DISAGREE (Both have chords, but different root pitch classes)
    - NO_CHORD_DISAGREEMENT (One engine predicts a chord, the other predicts NO_CHORD / silence)
    """
    if duration <= 0:
        return {
            "total_frames": 0,
            "agreement_rate": 1.0,
            "root_agreement_rate": 1.0,
            "category_percentages": {
                "AGREE": 100.0,
                "ROOT_AGREE_QUALITY_DISAGREE": 0.0,
                "ROOT_DISAGREE": 0.0,
                "NO_CHORD_DISAGREEMENT": 0.0
            },
            "disagreement_events": []
        }

    n_samples = max(1, int(duration * sample_rate_hz))
    labels_a = ["N"] * n_samples
    labels_b = ["N"] * n_samples

    for ev in engine_a_chords:
        t0 = max(0.0, float(ev.get("time", ev.get("start", 0.0))))
        t1 = min(duration, float(ev.get("end", t0 + 1.0)))
        i0 = int(np.clip(t0 * sample_rate_hz, 0, n_samples - 1))
        i1 = int(np.clip(t1 * sample_rate_hz, 0, n_samples))
        c = str(ev.get("chord", "N"))
        for idx in range(i0, i1):
            labels_a[idx] = c

    for ev in engine_b_chords:
        t0 = max(0.0, float(ev.get("time", ev.get("start", 0.0))))
        t1 = min(duration, float(ev.get("end", t0 + 1.0)))
        i0 = int(np.clip(t0 * sample_rate_hz, 0, n_samples - 1))
        i1 = int(np.clip(t1 * sample_rate_hz, 0, n_samples))
        c = str(ev.get("chord", "N"))
        for idx in range(i0, i1):
            labels_b[idx] = c

    counts = {
        "AGREE": 0,
        "ROOT_AGREE_QUALITY_DISAGREE": 0,
        "ROOT_DISAGREE": 0,
        "NO_CHORD_DISAGREEMENT": 0
    }

    disagreements = []
    last_cat = None

    for i, (ca, cb) in enumerate(zip(labels_a, labels_b)):
        t_curr = i / sample_rate_hz
        is_a_n = (ca.upper() in ("N", "NO_CHORD", "NONE", ""))
        is_b_n = (cb.upper() in ("N", "NO_CHORD", "NONE", ""))

        if is_a_n and is_b_n:
            cat = "AGREE"
        elif is_a_n != is_b_n:
            cat = "NO_CHORD_DISAGREEMENT"
        elif full_chord_matches(ca, cb):
            cat = "AGREE"
        elif root_matches(ca, cb):
            cat = "ROOT_AGREE_QUALITY_DISAGREE"
        else:
            cat = "ROOT_DISAGREE"

        counts[cat] += 1

        if cat != "AGREE":
            if cat != last_cat:
                if len(disagreements) < 50:
                    disagreements.append({
                        "category": cat,
                        "time": round(t_curr, 2),
                        "engine_a": ca,
                        "engine_b": cb
                    })
        last_cat = cat

    tot = float(n_samples)
    pcts = {k: round((v / tot) * 100.0, 2) for k, v in counts.items()}
    agr_rate = round(float((counts["AGREE"]) / tot), 4)
    root_agr_rate = round(float((counts["AGREE"] + counts["ROOT_AGREE_QUALITY_DISAGREE"]) / tot), 4)

    return {
        "total_frames": n_samples,
        "agreement_rate": agr_rate,
        "root_agreement_rate": root_agr_rate,
        "category_percentages": pcts,
        "category_counts": counts,
        "disagreement_events": disagreements
    }


def classify_real_song_error(
    ref_chord: str,
    est_chord: str,
    ref_bass: Optional[str] = None,
    est_bass: Optional[str] = None
) -> str:
    """
    Step 6 & 16: Classifies errors according to strict Phase 7 MIR Error Taxonomy:
    - WRONG_ROOT: Fundamental recognition error (different pitch class)
    - CORRECT_ROOT_WRONG_QUALITY: Root correct, quality differing (e.g. Am7 vs A)
    - WRONG_BASS: Root correct, but inversion/slash bass misidentified (e.g. C/E vs C/G)
    - MISSED_CHORD: Reference has chord, estimate has 'N'
    - FALSE_CHORD: Reference has 'N', estimate has chord
    """
    is_ref_n = (ref_chord.upper() in ("N", "NO_CHORD", "NONE", ""))
    is_est_n = (est_chord.upper() in ("N", "NO_CHORD", "NONE", ""))

    if is_ref_n and is_est_n:
        return "NO_ERROR"
    if is_ref_n and not is_est_n:
        return "FALSE_CHORD"
    if not is_ref_n and is_est_n:
        return "MISSED_CHORD"

    if not root_matches(ref_chord, est_chord):
        return "WRONG_ROOT"

    # Root matches; check quality
    if not majmin_matches(ref_chord, est_chord):
        return "WRONG_QUALITY"

    # Check bass note if available
    if ref_bass and est_bass and ref_bass.upper() != est_bass.upper():
        return "WRONG_BASS"

    if not full_chord_matches(ref_chord, est_chord):
        return "CORRECT_ROOT_WRONG_QUALITY"

    return "NO_ERROR"

