"""
backend/theory/normalization.py

Chord Normalization and Syntax Translation Layer.
Converts raw model outputs (e.g., Harte notation 'C:maj7', 'A:min7', 'F#:sus4(b7)', 'C:maj/3', 'N')
into standardized HotChords display symbols, pitch class sets, and pedagogical simplified triads.
"""

from typing import NamedTuple, Optional, List, Dict, Any
import re

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
NOTE_FLAT  = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']

PITCH_CLASS_MAP = {
    'C': 0, 'B#': 0,
    'C#': 1, 'Db': 1,
    'D': 2,
    'D#': 3, 'Eb': 3,
    'E': 4, 'Fb': 4,
    'F': 5, 'E#': 5,
    'F#': 6, 'Gb': 6,
    'G': 7,
    'G#': 8, 'Ab': 8,
    'A': 9,
    'A#': 10, 'Bb': 10,
    'B': 11, 'Cb': 11,
}

INTERVAL_SEMITONES = {
    '1': 0, 'b2': 1, '2': 2, 'b3': 3, '3': 4, '4': 5,
    'b5': 6, '5': 7, '#5': 8, 'b6': 8, '6': 9, 'bb7': 9,
    'b7': 10, '7': 11, 'b9': 1, '9': 2, '#9': 3, '11': 5, '#11': 6, '13': 9
}


class ParsedChord(NamedTuple):
    raw_chord: str
    root: Optional[str]
    quality: str
    bass: Optional[str]
    display_symbol: str
    simplified_triad: str
    is_no_chord: bool


def parse_harte_chord(harte_str: str) -> ParsedChord:
    """
    Parses a Harte syntax chord string into a structured ParsedChord.
    
    Examples:
      'C:maj'       -> display: 'C', simplified: 'C'
      'A:min'       -> display: 'Am', simplified: 'Am'
      'G:7'         -> display: 'G7', simplified: 'G'
      'C:maj7'      -> display: 'Cmaj7', simplified: 'C'
      'D:min7'      -> display: 'Dm7', simplified: 'Dm'
      'F#:sus4(b7)' -> display: 'F#7sus4', simplified: 'F#'
      'C:maj/3'     -> display: 'C/E', simplified: 'C'
      'N'           -> display: 'N', simplified: 'N', is_no_chord: True
    """
    if not harte_str or harte_str.strip() in ('N', 'X', 'None', '', 'no_chord'):
        return ParsedChord(
            raw_chord=harte_str or 'N',
            root=None,
            quality='N',
            bass=None,
            display_symbol='N',
            simplified_triad='N',
            is_no_chord=True
        )

    clean_str = harte_str.strip()

    # Match Harte pattern: ROOT:QUALITY/BASS or ROOT:QUALITY or ROOT
    root_match = re.match(r'^([A-G][b#]?)(?::([^/]+))?(?:/(.+))?$', clean_str)
    if not root_match:
        # Fallback: simple symbol like 'Am', 'C7', 'F#m7'
        if clean_str == 'N':
            return ParsedChord('N', None, 'N', None, 'N', 'N', True)
        return _parse_simple_chord_symbol(clean_str)

    root = root_match.group(1)
    quality_raw = root_match.group(2) or 'maj'
    bass_raw = root_match.group(3)

    # Standardize root
    root_pc = PITCH_CLASS_MAP.get(root, 0)
    canonical_root = NOTE_NAMES[root_pc] if '#' in root or root in NOTE_NAMES else NOTE_FLAT[root_pc]

    # Parse Quality
    display_suffix = ''
    triad_suffix = ''

    q = quality_raw.lower()
    if q in ('maj', '', '1', '(1,3,5)'):
        display_suffix = ''
        triad_suffix = ''
    elif q in ('min', 'm', '(1,b3,5)'):
        display_suffix = 'm'
        triad_suffix = 'm'
    elif q in ('7', '(1,3,5,b7)'):
        display_suffix = '7'
        triad_suffix = ''
    elif q in ('maj7', 'maj(7)', '(1,3,5,7)'):
        display_suffix = 'maj7'
        triad_suffix = ''
    elif q in ('min7', 'm7', '(1,b3,5,b7)'):
        display_suffix = 'm7'
        triad_suffix = 'm'
    elif q in ('dim', '(1,b3,b5)'):
        display_suffix = 'dim'
        triad_suffix = 'dim'
    elif q in ('dim7', 'hdim7', 'm7b5', '(1,b3,b5,bb7)', '(1,b3,b5,b7)'):
        display_suffix = 'dim7' if 'dim7' in q else 'm7b5'
        triad_suffix = 'dim'
    elif q in ('aug', '(1,3,#5)'):
        display_suffix = 'aug'
        triad_suffix = 'aug'
    elif q in ('sus4', '(1,4,5)'):
        display_suffix = 'sus4'
        triad_suffix = ''
    elif q in ('sus2', '(1,2,5)'):
        display_suffix = 'sus2'
        triad_suffix = ''
    elif q in ('sus4(b7)', '7sus4'):
        display_suffix = '7sus4'
        triad_suffix = ''
    elif q in ('6', 'maj6', '(1,3,5,6)'):
        display_suffix = '6'
        triad_suffix = ''
    elif q in ('min6', 'm6', '(1,b3,5,6)'):
        display_suffix = 'm6'
        triad_suffix = 'm'
    elif q in ('9', 'maj9'):
        display_suffix = '9' if q == '9' else 'maj9'
        triad_suffix = ''
    elif q in ('min9', 'm9'):
        display_suffix = 'm9'
        triad_suffix = 'm'
    else:
        # Generic extension
        if 'min' in q or 'm' in q:
            display_suffix = 'm'
            triad_suffix = 'm'
        elif 'dim' in q:
            display_suffix = 'dim'
            triad_suffix = 'dim'
        elif 'aug' in q:
            display_suffix = 'aug'
            triad_suffix = 'aug'
        else:
            display_suffix = ''
            triad_suffix = ''

    # Parse Bass Note / Inversion
    bass_note = None
    if bass_raw:
        if bass_raw in PITCH_CLASS_MAP:
            bass_note = bass_raw
        elif bass_raw in INTERVAL_SEMITONES:
            semitones = INTERVAL_SEMITONES[bass_raw]
            bass_pc = (root_pc + semitones) % 12
            bass_note = NOTE_FLAT[bass_pc] if 'b' in root else NOTE_NAMES[bass_pc]

    # Build display and simplified symbols
    base_display = f"{canonical_root}{display_suffix}"
    if bass_note and bass_note != canonical_root:
        display_symbol = f"{base_display}/{bass_note}"
    else:
        display_symbol = base_display

    simplified_triad = f"{canonical_root}{triad_suffix}"

    return ParsedChord(
        raw_chord=clean_str,
        root=canonical_root,
        quality=quality_raw,
        bass=bass_note,
        display_symbol=display_symbol,
        simplified_triad=simplified_triad,
        is_no_chord=False
    )


def _parse_simple_chord_symbol(symbol: str) -> ParsedChord:
    """Parses standard symbols like 'C', 'Am', 'G7', 'Cmaj7', 'F#m7'."""
    m = re.match(r'^([A-G][b#]?)(.*)$', symbol)
    if not m:
        return ParsedChord(symbol, None, 'N', None, 'N', 'N', True)

    root = m.group(1)
    suffix = m.group(2) or ''
    root_pc = PITCH_CLASS_MAP.get(root, 0)
    canonical_root = NOTE_NAMES[root_pc] if '#' in root or root in NOTE_NAMES else NOTE_FLAT[root_pc]

    triad_suffix = 'm' if suffix.startswith('m') and not suffix.startswith('maj') else ''
    if 'dim' in suffix:
        triad_suffix = 'dim'
    elif 'aug' in suffix:
        triad_suffix = 'aug'

    return ParsedChord(
        raw_chord=symbol,
        root=canonical_root,
        quality=suffix or 'maj',
        bass=None,
        display_symbol=f"{canonical_root}{suffix}",
        simplified_triad=f"{canonical_root}{triad_suffix}",
        is_no_chord=False
    )


def normalize_chord_sequence(raw_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalizes a sequence of chord events from a recognition engine into
    standardized HotChords chord dictionaries.
    """
    normalized = []
    for ev in raw_events:
        t0 = float(ev.get('start_time', ev.get('startTime', ev.get('start', ev.get('time', 0.0)))))
        t1 = float(ev.get('end_time', ev.get('endTime', ev.get('end', t0 + 0.5))))
        raw_label = str(ev.get('chord', ev.get('chordName', ev.get('label', 'N'))))
        conf = float(ev.get('confidence', 1.0)) if ev.get('confidence') is not None else 1.0

        parsed = parse_harte_chord(raw_label)
        normalized.append({
            'time': round(t0, 3),
            'end': round(t1, 3),
            'chord': parsed.display_symbol,
            'raw_chord': raw_label,
            'root': parsed.root,
            'quality': parsed.quality,
            'bass': parsed.bass,
            'simplified': parsed.simplified_triad,
            'confidence': round(conf, 3),
            'is_no_chord': parsed.is_no_chord
        })
    return normalized
