"""
backend/theory/transposition.py

Deterministic Musical Key & Progression Transposition Engine for HotChords (Phase 9).
Provides pitch-preserving, diatonic, and chromatic chord/progression transposition
and intelligent beginner key recommendation.

Responsibilities:
1. Pure Deterministic Python (Zero ML, zero external dependencies).
2. Global Semitone Transposition (preserves exact musical intervals across entire progressions).
3. Root & Slash Bass Transposition (accurately transposes both root and inverted bass notes).
4. Raw/Simplified Harmonic Preservation (preserves quality, extensions, and Harte syntax).
5. Beginner Key Recommendation (ranks 12 chromatic keys by playability and black-key reduction).
"""

from typing import List, Dict, Optional, Tuple, Any, Union
import re
from backend.theory.piano_voicing import (
    PITCH_CLASS_MAP,
    NOTE_NAMES_SHARP,
    NOTE_NAMES_FLAT,
    parse_chord_components,
    midi_to_note_name,
)
from backend.theory.simplification import evaluate_beginner_difficulty


def transpose_pitch_class(pc: int, semitones: int) -> int:
    """Transposes a pitch class (0-11) by a semitone offset modulo 12."""
    return (pc + semitones) % 12


def transpose_note_name(note_name: str, semitones: int, prefer_flat: Optional[bool] = None) -> str:
    """
    Transposes a single note name (e.g., 'C' -> 'D', 'F#' -> 'G#') by semitones.
    """
    if not note_name or note_name not in PITCH_CLASS_MAP:
        return note_name

    old_pc = PITCH_CLASS_MAP[note_name]
    new_pc = (old_pc + semitones) % 12

    if prefer_flat is None:
        # Default preference: flats for Eb, Ab, Bb (3, 8, 10); sharp for C#, F# (1, 6)
        prefer_flat = new_pc in (3, 8, 10)

    return NOTE_NAMES_FLAT[new_pc] if prefer_flat else NOTE_NAMES_SHARP[new_pc]


def transpose_chord_symbol(chord_str: str, semitones: int, prefer_flat: Optional[bool] = None) -> str:
    """
    Transposes a single chord symbol (e.g., 'C' -> 'D', 'Am7' -> 'Bm7', 'C/E' -> 'D/F#').
    Supports both Harte notation ('C:maj7' -> 'D:maj7') and standard musician notation.
    """
    if not chord_str or chord_str.strip().upper() in ("N", "NONE", "NO_CHORD", "X", ""):
        return "N"

    clean = chord_str.strip()
    if semitones % 12 == 0:
        return clean

    # Handle Harte syntax ROOT:QUALITY/BASS
    if ":" in clean:
        parts = clean.split(":")
        root = parts[0]
        rest = parts[1]
        
        # Determine accidental orientation from root context
        if prefer_flat is None:
            old_pc = PITCH_CLASS_MAP.get(root, 0)
            new_root_pc = (old_pc + semitones) % 12
            # Sharp keys: E(4), B(11), A(9), D(2), G(7), F#(6), C#(1), G#(8)
            prefer_flat = new_root_pc in (5, 10, 3, 8) and "#" not in root

        transposed_root = transpose_note_name(root, semitones, prefer_flat=prefer_flat)
        if "/" in rest:
            qual, bass = rest.split("/")
            # Bass could be an interval number (e.g. '3') or note name
            if bass in PITCH_CLASS_MAP:
                transposed_bass = transpose_note_name(bass, semitones, prefer_flat=prefer_flat)
                return f"{transposed_root}:{qual}/{transposed_bass}"
            else:
                return f"{transposed_root}:{qual}/{bass}"
        return f"{transposed_root}:{rest}"

    # Handle standard slash chords (e.g., C/E, Dm/F#)
    if "/" in clean:
        main_part, bass_part = clean.split("/", 1)
        root, _, _ = parse_chord_components(main_part)
        if prefer_flat is None and root:
            old_pc = PITCH_CLASS_MAP.get(root, 0)
            new_root_pc = (old_pc + semitones) % 12
            prefer_flat = new_root_pc in (5, 10, 3, 8) and "#" not in root

        transposed_main = transpose_chord_symbol(main_part, semitones, prefer_flat=prefer_flat)
        transposed_bass = transpose_note_name(bass_part, semitones, prefer_flat=prefer_flat)
        return f"{transposed_main}/{transposed_bass}"

    # Handle standard chord (e.g., C#m7, F#sus4, Bb)
    root, quality, bass = parse_chord_components(clean)
    if not root:
        return clean

    transposed_root = transpose_note_name(root, semitones, prefer_flat=prefer_flat)

    # Reconstruct suffix
    if quality in ("maj", ""):
        suffix = ""
    elif quality in ("min", "m"):
        suffix = "m"
    elif quality == "7":
        suffix = "7"
    elif quality == "maj7":
        suffix = "maj7"
    elif quality in ("min7", "m7"):
        suffix = "m7"
    elif quality in ("sus2", "sus4", "dim", "aug", "m7b5", "add9", "9", "maj9", "min9"):
        suffix = quality
    else:
        suffix = quality

    result = f"{transposed_root}{suffix}"
    if bass:
        transposed_bass = transpose_note_name(bass, semitones, prefer_flat=prefer_flat)
        result = f"{result}/{transposed_bass}"

    return result


def transpose_progression(
    chords: List[Union[str, Dict[str, Any]]],
    semitones: int,
    prefer_flat: Optional[bool] = None
) -> List[Any]:
    """
    Transposes an entire chord progression consistently with a single global semitone offset.
    Preserves timing and dictionary structure when dictionaries are provided.
    """
    if semitones % 12 == 0:
        return chords

    transposed = []
    for item in chords:
        if isinstance(item, str):
            transposed.append(transpose_chord_symbol(item, semitones, prefer_flat=prefer_flat))
        elif isinstance(item, dict):
            c_copy = dict(item)
            c_name = c_copy.get("chord") or c_copy.get("chord_name") or c_copy.get("chordName")
            if c_name:
                trans_chord = transpose_chord_symbol(c_name, semitones, prefer_flat=prefer_flat)
                if "chord" in c_copy:
                    c_copy["chord"] = trans_chord
                if "chord_name" in c_copy:
                    c_copy["chord_name"] = trans_chord
                if "chordName" in c_copy:
                    c_copy["chordName"] = trans_chord
            raw_c = c_copy.get("raw_chord") or c_copy.get("rawChord")
            if raw_c:
                trans_raw = transpose_chord_symbol(raw_c, semitones, prefer_flat=prefer_flat)
                if "raw_chord" in c_copy:
                    c_copy["raw_chord"] = trans_raw
                if "rawChord" in c_copy:
                    c_copy["rawChord"] = trans_raw
            transposed.append(c_copy)
        else:
            transposed.append(item)

    return transposed


def transpose_key_name(key_name: str, semitones: int) -> str:
    """Transposes a musical key name (e.g., 'E Major' -> 'C Major', 'C# Minor' -> 'A Minor')."""
    if not key_name or key_name == "N":
        return key_name

    parts = key_name.strip().split()
    root = parts[0]
    scale = parts[1] if len(parts) > 1 else ""

    trans_root = transpose_note_name(root, semitones)
    return f"{trans_root} {scale}".strip() if scale else trans_root


def evaluate_key_transpositions(
    chords: List[str],
    current_key: Optional[str] = None,
    current_scale: str = "Major"
) -> Dict[str, Any]:
    """
    Step 11: Beginner Key Recommendation Algorithm.
    Evaluates all 12 chromatic transpositions of the input chord list.
    Calculates difficulty, black-key usage, and white-key anchors to find the optimal beginner key.
    """
    if not chords:
        return {
            "currentKey": current_key or "C",
            "recommendedKey": current_key or "C",
            "recommendedOffset": 0,
            "transpositionOptions": [],
        }

    # Filter out NO_CHORD ('N') for difficulty evaluation
    valid_chords = [c for c in chords if c and c.upper() not in ("N", "NONE", "NO_CHORD", "")]
    if not valid_chords:
        return {
            "currentKey": current_key or "C",
            "recommendedKey": current_key or "C",
            "recommendedOffset": 0,
            "transpositionOptions": [],
        }

    options = []
    
    for offset in range(-6, 6):
        # Calculate transposed chords
        trans_chords = [transpose_chord_symbol(c, offset) for c in valid_chords]
        unique_trans = list(set(trans_chords))

        # Evaluate difficulty for each chord in transposed key
        diff_scores = []
        easy_count = 0
        mod_count = 0
        diff_count = 0

        for c in trans_chords:
            diff = evaluate_beginner_difficulty(c)
            if diff == "EASY":
                diff_scores.append(0.15)
                easy_count += 1
            elif diff == "MODERATE":
                diff_scores.append(0.40)
                mod_count += 1
            else:
                diff_scores.append(0.75)
                diff_count += 1

        avg_diff = float(sum(diff_scores) / len(diff_scores))
        max_diff = float(max(diff_scores)) if diff_scores else 0.0

        # Transposed key label
        trans_key = transpose_key_name(current_key or "C", offset) if current_key else f"Offset {offset}"

        # Natural white key anchor bonus
        white_key_anchors = sum(1 for c in unique_trans if c in ("C", "G", "F", "Am", "Em", "Dm"))
        anchor_ratio = white_key_anchors / max(1, len(unique_trans))

        # Offset penalty (prefer smaller transpose distances if difficulty is equal)
        offset_penalty = abs(offset) * 0.01

        # Composite Beginner Suitability Score (Lower is better)
        suitability_score = 0.50 * avg_diff + 0.30 * (1.0 - anchor_ratio) + 0.20 * (max_diff / 0.75) + offset_penalty

        options.append({
            "offset": offset,
            "key": trans_key,
            "averageDifficulty": round(avg_diff, 3),
            "maxDifficulty": round(max_diff, 3),
            "easyChordRatio": round(easy_count / len(trans_chords), 3),
            "uniqueChords": unique_trans,
            "suitabilityScore": round(float(suitability_score), 4),
            "isOriginal": (offset == 0),
        })

    # Sort options by suitability score (lowest difficulty score first)
    options.sort(key=lambda x: x["suitabilityScore"])

    best_option = options[0]

    return {
        "currentKey": current_key or "C",
        "recommendedKey": best_option["key"],
        "recommendedOffset": best_option["offset"],
        "recommendedScore": best_option["suitabilityScore"],
        "options": options[:6],  # Top 6 easiest keys
    }
