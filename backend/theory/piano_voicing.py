"""
backend/theory/piano_voicing.py

Production Piano Voicing and Voice-Leading Engine for HotChords (Phase 8).
Generates deterministic, ergonomically optimized left- and right-hand piano voicings,
MIDI mappings, finger assignments, and difficulty metrics from chord progressions.

Key Responsibilities:
1. Pure Music Theory / Voicing Generation (Zero ML, zero UI dependencies).
2. Voice-Leading Cost Minimization (smooth movements, common tones, compact register).
3. Range Constraints (prevents low muddy rumble below C2 and shrill highs above G5).
4. Dual-Hand Ergonomics (LH bass anchor, RH harmonic triad / inversion).
5. Cyclic 4-Chord Loop Optimization (seamless loop transition from chord 4 -> chord 1).
"""

from typing import List, Dict, Optional, Tuple, Any, Union
from pydantic import BaseModel
import re

# Standard finger colors matching HotChords UI
FINGER_COLORS = {
    1: "#FF4D4F",  # Thumb (Red)
    2: "#FAAD14",  # Index (Orange/Yellow)
    3: "#52C41A",  # Middle (Green)
    4: "#13C2C2",  # Ring (Cyan)
    5: "#1677FF",  # Pinky (Blue)
}

NOTE_NAMES_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
NOTE_NAMES_FLAT  = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]

PITCH_CLASS_MAP = {
    "C": 0, "B#": 0,
    "C#": 1, "Db": 1,
    "D": 2,
    "D#": 3, "Eb": 3,
    "E": 4, "Fb": 4,
    "F": 5, "E#": 5,
    "F#": 6, "Gb": 6,
    "G": 7,
    "G#": 8, "Ab": 8,
    "A": 9,
    "A#": 10, "Bb": 10,
    "B": 11, "Cb": 11,
}

# Standard intervals for chord qualities (relative to root in semitones)
CHORD_INTERVALS: Dict[str, List[int]] = {
    "maj": [0, 4, 7],
    "min": [0, 3, 7],
    "7": [0, 4, 7, 10],
    "dom7": [0, 4, 7, 10],
    "maj7": [0, 4, 7, 11],
    "min7": [0, 3, 7, 10],
    "m7": [0, 3, 7, 10],
    "sus2": [0, 2, 7],
    "sus4": [0, 5, 7],
    "dim": [0, 3, 6],
    "dim7": [0, 3, 6, 9],
    "m7b5": [0, 3, 6, 10],
    "aug": [0, 4, 8],
    "5": [0, 7],
    "add9": [0, 4, 7, 14],
    "9": [0, 4, 7, 10, 14],
    "maj9": [0, 4, 7, 11, 14],
    "min9": [0, 3, 7, 10, 14],
    "m9": [0, 3, 7, 10, 14],
}

# Register bounds (MIDI numbers)
LH_MIN_MIDI = 36  # C2
LH_MAX_MIDI = 55  # G3
RH_MIN_MIDI = 55  # G3
RH_MAX_MIDI = 79  # G5
RH_TARGET_CENTER = 64  # E4 / Middle register anchor


def midi_to_note_name(midi: int, prefer_flat: bool = False) -> str:
    """Converts a MIDI note number (0-127) to a standard scientific pitch string (e.g. 60 -> 'C4')."""
    octave = (midi // 12) - 1
    pc = midi % 12
    name = NOTE_NAMES_FLAT[pc] if prefer_flat else NOTE_NAMES_SHARP[pc]
    return f"{name}{octave}"


def parse_chord_components(chord_str: str) -> Tuple[Optional[str], str, Optional[str]]:
    """
    Parses any chord string into (root, quality, bass_note).
    Examples:
      'C' -> ('C', 'maj', None)
      'Am' -> ('A', 'min', None)
      'C#m7' -> ('C#', 'min7', None)
      'D/F#' -> ('D', 'maj', 'F#')
      'C:maj7' -> ('C', 'maj7', None)
      'D:min9/F#' -> ('D', 'min9', 'F#')
      'N' -> (None, 'N', None)
    """
    if not chord_str or chord_str.strip().upper() in ("N", "NONE", "NO_CHORD", "X", ""):
        return None, "N", None

    clean = chord_str.strip()
    
    # Check for Harte syntax like ROOT:QUALITY/BASS
    harte_match = re.match(r"^([A-G][b#]?)(?::([^/]+))?(?:/(.+))?$", clean)
    if harte_match and ":" in clean:
        root = harte_match.group(1)
        raw_qual = harte_match.group(2) or "maj"
        bass = harte_match.group(3)
        qual = raw_qual.lower()
        if qual in ("maj", "", "1", "(1,3,5)"):
            quality = "maj"
        elif qual in ("min", "m", "(1,b3,5)"):
            quality = "min"
        elif qual in ("7", "dom7"):
            quality = "7"
        elif qual in ("maj7",):
            quality = "maj7"
        elif qual in ("min7", "m7"):
            quality = "min7"
        elif qual in ("sus2",):
            quality = "sus2"
        elif qual in ("sus4", "sus"):
            quality = "sus4"
        elif qual in ("dim", "dim7", "°"):
            quality = "dim"
        elif qual in ("aug", "+"):
            quality = "aug"
        else:
            quality = qual
        return root, quality, bass

    # Handle standard slash chord format (e.g., C/E, Dm7/G)
    slash_parts = clean.split("/")
    main_chord = slash_parts[0].strip()
    bass_note = slash_parts[1].strip() if len(slash_parts) > 1 else None

    # Parse main chord
    m = re.match(r"^([A-Ga-g][#b]?)(.*)$", main_chord)
    if not m:
        return None, "N", None

    root = m.group(1).upper()
    if len(m.group(1)) > 1 and m.group(1)[1] == "b":
        root = root[0] + "b"
    elif len(m.group(1)) > 1 and m.group(1)[1] == "#":
        root = root[0] + "#"

    suffix = m.group(2).strip()

    if suffix in ("", "M", "maj", "Maj"):
        quality = "maj"
    elif suffix in ("m", "min", "Min", "-"):
        quality = "min"
    elif suffix in ("7", "dom7"):
        quality = "7"
    elif suffix in ("maj7", "Maj7", "M7", "Δ"):
        quality = "maj7"
    elif suffix in ("m7", "min7", "Min7", "-7"):
        quality = "min7"
    elif suffix in ("sus2", "2"):
        quality = "sus2"
    elif suffix in ("sus4", "sus", "4"):
        quality = "sus4"
    elif suffix in ("dim", "dim7", "°", "o"):
        quality = "dim"
    elif suffix in ("m7b5", "ø"):
        quality = "m7b5"
    elif suffix in ("aug", "+", "+5"):
        quality = "aug"
    elif suffix in ("add9",):
        quality = "add9"
    elif suffix in ("9",):
        quality = "9"
    elif suffix in ("maj9", "Maj9"):
        quality = "maj9"
    elif suffix in ("m9", "min9"):
        quality = "min9"
    else:
        quality = suffix.lower() if suffix else "maj"

    return root, quality, bass_note


def generate_candidate_rh_voicings(
    root: str,
    quality: str,
    beginner_mode: bool = True
) -> List[List[int]]:
    """
    Generates all musical candidate Right Hand voicings (inversions and octave positions)
    within the target piano register (MIDI 55 - 79).
    """
    if root not in PITCH_CLASS_MAP:
        return []

    root_pc = PITCH_CLASS_MAP[root]
    
    # In beginner mode, reduce extended 9ths/11ths to core triads or 7ths
    if beginner_mode:
        if quality in ("maj9", "add9"):
            effective_quality = "maj"
        elif quality in ("min9", "m9"):
            effective_quality = "min"
        elif quality in ("9",):
            effective_quality = "7"
        elif quality in ("m7b5",):
            effective_quality = "dim"
        else:
            effective_quality = quality
    else:
        effective_quality = quality

    intervals = CHORD_INTERVALS.get(effective_quality, [0, 4, 7])
    # In beginner mode, use triads for standard maj7/min7 if requested, but preserve 3 essential notes
    if beginner_mode and effective_quality in ("maj7", "min7", "7"):
        # Beginner 7th can use full 4 notes or 3 notes
        intervals = CHORD_INTERVALS.get(effective_quality, [0, 4, 7])

    pitch_classes = [(root_pc + interval) % 12 for interval in intervals]
    
    # Unique pitch classes in ascending order from root
    candidates = []
    
    # Generate root position, 1st inversion, 2nd inversion, 3rd inversion
    n_notes = len(pitch_classes)
    for inv in range(n_notes):
        # Rotate pitch classes for inversion
        inv_pcs = pitch_classes[inv:] + pitch_classes[:inv]
        
        # Test octave placements (Octave 3, 4, 5 -> base 48, 60, 72)
        for base_oct in (48, 60, 72):
            notes = []
            curr_midi = base_oct + inv_pcs[0]
            notes.append(curr_midi)
            
            for pc in inv_pcs[1:]:
                # Move upward
                diff = (pc - (curr_midi % 12)) % 12
                if diff == 0:
                    diff = 12
                curr_midi = curr_midi + diff
                notes.append(curr_midi)
                
            # Validate within RH bounds
            if all(RH_MIN_MIDI <= n <= RH_MAX_MIDI for n in notes):
                span = max(notes) - min(notes)
                if span <= 14:  # Ergonomic hand span (<= octave + 2 semitones)
                    candidates.append(notes)

    # Deduplicate candidate note sets
    unique_candidates = []
    seen = set()
    for c in candidates:
        tup = tuple(c)
        if tup not in seen:
            seen.add(tup)
            unique_candidates.append(c)

    return unique_candidates


def score_voice_leading(
    prev_notes: Optional[List[int]],
    cand_notes: List[int]
) -> float:
    """
    Step 8: Voice-Leading Cost Function.
    Calculates cost of moving from prev_notes to cand_notes:
    - Minimizes total voice displacement sum(|c_i - p_i|)
    - Rewards common tone retention
    - Penalizes wide hand spans
    - Encourages centering near middle register (MIDI 64)
    """
    if not cand_notes:
        return 999.0

    span = max(cand_notes) - min(cand_notes)
    span_penalty = max(0, span - 12) * 1.5
    
    center = sum(cand_notes) / len(cand_notes)
    center_penalty = abs(center - RH_TARGET_CENTER) * 0.25

    if not prev_notes:
        # Initial chord: prioritize root position / middle register
        return span_penalty + center_penalty

    # Calculate movement distance
    # Common tones bonus
    common_tones = len(set(prev_notes) & set(cand_notes))
    common_bonus = common_tones * 3.0

    # Total movement cost: pair closest notes
    movement_cost = 0.0
    for cn in cand_notes:
        closest = min(abs(cn - pn) for pn in prev_notes)
        movement_cost += closest

    total_cost = movement_cost + span_penalty + center_penalty - common_bonus
    return float(total_cost)


def assign_rh_fingering(notes: List[int], is_root_position: bool = False) -> List[int]:
    """
    Assigns standard ergonomic Right Hand fingers (1=Thumb, 2=Index, 3=Middle, 4=Ring, 5=Pinky).
    """
    count = len(notes)
    if count == 1:
        return [1]
    elif count == 2:
        return [1, 5]
    elif count == 3:
        span = max(notes) - min(notes)
        # Standard triad fingering: [1, 3, 5] for root or wide, [1, 2, 5] for 1st inversion
        if is_root_position or span <= 7:
            return [1, 3, 5]
        else:
            return [1, 2, 5]
    elif count == 4:
        return [1, 2, 3, 5]
    else:
        return [1, 2, 3, 4, 5][:count]


def generate_lh_voicing(root: str, bass_note: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Step 9: Left Hand Voicing.
    Plays the root or bass note in Octave 2/3 (MIDI 36-55).
    """
    eff_note = bass_note if bass_note and bass_note in PITCH_CLASS_MAP else root
    if eff_note not in PITCH_CLASS_MAP:
        return []

    pc = PITCH_CLASS_MAP[eff_note]
    prefer_flat = "b" in eff_note
    
    # Choose optimal bass octave (target MIDI 36 - 47)
    midi_note = 36 + pc
    if midi_note < LH_MIN_MIDI:
        midi_note += 12
    elif midi_note > LH_MAX_MIDI:
        midi_note -= 12

    name = midi_to_note_name(midi_note, prefer_flat=prefer_flat)
    
    return [
        {
            "midi": midi_note,
            "note": name,
            "finger": 5,  # Pinky on bass anchor
            "color": FINGER_COLORS[5],
        }
    ]


def calculate_chord_difficulty_score(
    chord_name: str,
    rh_notes: List[int],
    prev_rh_notes: Optional[List[int]] = None
) -> float:
    """
    Step 10: Calculates internal beginner difficulty score [0.0, 1.0].
    Considers:
    - Black key count in right hand
    - Chord quality complexity
    - Hand span
    - Distance jump from previous chord
    """
    if not chord_name or chord_name == "N" or not rh_notes:
        return 0.0

    # 1. Black key count
    black_keys = sum(1 for n in rh_notes if (n % 12) in (1, 3, 6, 8, 10))
    black_key_ratio = black_keys / len(rh_notes)

    # 2. Quality complexity
    root, quality, bass = parse_chord_components(chord_name)
    quality_weight = 0.1
    if quality in ("min", "m"):
        quality_weight = 0.2
    elif quality in ("7", "dom7", "sus2", "sus4"):
        quality_weight = 0.4
    elif quality in ("maj7", "min7"):
        quality_weight = 0.5
    elif quality in ("dim", "aug", "m7b5"):
        quality_weight = 0.8

    # 3. Span
    span = max(rh_notes) - min(rh_notes)
    span_factor = min(1.0, max(0.0, (span - 7) / 7.0))

    # 4. Jump from previous
    jump_factor = 0.0
    if prev_rh_notes:
        dist = abs((sum(rh_notes)/len(rh_notes)) - (sum(prev_rh_notes)/len(prev_rh_notes)))
        jump_factor = min(1.0, dist / 12.0)

    # Composite difficulty [0.0, 1.0]
    difficulty = 0.35 * black_key_ratio + 0.30 * quality_weight + 0.20 * span_factor + 0.15 * jump_factor
    return round(float(difficulty), 3)


def voice_chord(
    chord_name: str,
    prev_rh_notes: Optional[List[int]] = None,
    beginner_mode: bool = True
) -> Dict[str, Any]:
    """
    Voices a single chord with optimal voice leading from prev_rh_notes.
    Returns:
      {
        'leftHand': [...],
        'rightHand': [...],
        'midiNotes': [...],
        'difficultyScore': float
      }
    """
    root, quality, bass = parse_chord_components(chord_name)
    if not root or quality == "N":
        return {
            "leftHand": [],
            "rightHand": [],
            "midiNotes": [],
            "difficultyScore": 0.0,
        }

    # Generate LH
    lh_voicing = generate_lh_voicing(root=root, bass_note=bass)

    # Generate RH Candidates
    candidates = generate_candidate_rh_voicings(root=root, quality=quality, beginner_mode=beginner_mode)
    
    if not candidates:
        # Fallback to simple root triad
        root_pc = PITCH_CLASS_MAP.get(root, 0)
        c_notes = [60 + root_pc, 64 + root_pc, 67 + root_pc]
        candidates = [c_notes]

    # Select best candidate via voice-leading cost
    best_candidate = min(candidates, key=lambda c: score_voice_leading(prev_rh_notes, c))
    
    # Assign RH fingering
    root_pc = PITCH_CLASS_MAP.get(root, 0)
    is_root_pos = (best_candidate[0] % 12 == root_pc)
    fingers = assign_rh_fingering(best_candidate, is_root_position=is_root_pos)
    prefer_flat = "b" in root or (bass and "b" in bass)

    rh_voicing = []
    for note_midi, finger in zip(best_candidate, fingers):
        rh_voicing.append({
            "midi": note_midi,
            "note": midi_to_note_name(note_midi, prefer_flat=prefer_flat),
            "finger": finger,
            "color": FINGER_COLORS.get(finger, "#5856D6"),
        })

    all_midi = [n["midi"] for n in lh_voicing] + [n["midi"] for n in rh_voicing]
    diff_score = calculate_chord_difficulty_score(chord_name, best_candidate, prev_rh_notes)

    return {
        "leftHand": lh_voicing,
        "rightHand": rh_voicing,
        "midiNotes": sorted(list(set(all_midi))),
        "difficultyScore": diff_score,
    }


def voice_chord_progression(
    chords: List[Union[str, Dict[str, Any]]],
    beginner_mode: bool = True
) -> List[Dict[str, Any]]:
    """
    Voices a sequential chord progression, chaining voice-leading smoothly from chord to chord.
    """
    voicings = []
    prev_rh = None

    for item in chords:
        c_name = item.get("chord") or item.get("chord_name") if isinstance(item, dict) else str(item)
        v = voice_chord(chord_name=c_name, prev_rh_notes=prev_rh, beginner_mode=beginner_mode)
        voicings.append(v)
        if v["rightHand"]:
            prev_rh = [n["midi"] for n in v["rightHand"]]

    return voicings


def voice_four_chord_loop(loop_chords: List[str]) -> List[Dict[str, Any]]:
    """
    Step 11: Four-Chord Loop + Voicing Integration.
    Voices a 4-chord loop cyclically such that chord 4 leads smoothly back into chord 1.
    """
    if not loop_chords or len(loop_chords) != 4:
        return voice_chord_progression(loop_chords)

    # Initial pass
    v1 = voice_chord_progression(loop_chords, beginner_mode=True)
    if not v1 or not v1[-1]["rightHand"]:
        return v1

    # Check loop wrap cost (chord 4 -> chord 1)
    rh_4 = [n["midi"] for n in v1[-1]["rightHand"]]
    rh_1 = [n["midi"] for n in v1[0]["rightHand"]]
    
    # Re-voice chord 1 considering chord 4 for cyclic continuity
    v_first_adjusted = voice_chord(loop_chords[0], prev_rh_notes=rh_4, beginner_mode=True)
    
    # Re-run forward progression from adjusted chord 1
    adjusted_voicings = []
    curr_rh = None
    for i, chord_name in enumerate(loop_chords):
        if i == 0:
            v = v_first_adjusted
        else:
            v = voice_chord(chord_name, prev_rh_notes=curr_rh, beginner_mode=True)
        adjusted_voicings.append(v)
        if v["rightHand"]:
            curr_rh = [n["midi"] for n in v["rightHand"]]

    return adjusted_voicings


def evaluate_loop_beginner_playability(chords: List[str]) -> float:
    """
    Step 10 & 11: Evaluates beginner playability for a 4-chord progression:
    - distinct chord count (penalizes awkward clusters, rewards 3-4 distinct chords)
    - chord complexity (EASY = 1.0, MODERATE = 0.7, DIFFICULT = 0.3)
    - presence of white-key anchors (C, G, F, Am, Em, Dm)
    """
    if not chords or len(chords) != 4:
        return 0.0

    from backend.theory.simplification import evaluate_beginner_difficulty

    scores = []
    for c in chords:
        diff = evaluate_beginner_difficulty(c)
        if diff == "EASY":
            scores.append(1.0)
        elif diff == "MODERATE":
            scores.append(0.7)
        else:
            scores.append(0.3)

    avg_simplicity = float(sum(scores) / len(scores))
    unique_count = len(set(chords))
    variety_score = 1.0 if unique_count in (3, 4) else (0.85 if unique_count == 2 else 0.4)

    playability = 0.70 * avg_simplicity + 0.30 * variety_score
    return round(float(playability), 3)


