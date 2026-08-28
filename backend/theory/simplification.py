"""
backend/theory/simplification.py

Dedicated, deterministic Beginner Chord Simplification Engine for HotChords.
Transforms complex detected chord progressions into beginner-playable piano progressions
while preserving the song's harmonic identity, tempo, and key.

Pipeline Stages:
1. Normalization: Canonical enharmonics and symbol cleanup.
2. Harmonic Reduction: Eliminates unneeded extensions (maj7, m7, 9, 11, 13) and
   resolves diminished/altered harmonies diatonically.
3. Difficulty Evaluation: Categorizes chords as EASY, MODERATE, or DIFFICULT.
4. Progression-Level Smoothing: Merges consecutive identical chords and absorbs
   short passing chords using a beat/tempo-aware threshold.
5. Timeline Generation: Produces new beginner ChordEvents without mutating original chords.
"""

from typing import List, Dict, Optional, Union, Any, Tuple
from backend.theory.constants import NOTE_NAMES, NOTE_FLAT
from backend.theory.theory import (
    musician_friendly_name,
    chord_note_indices,
    get_chord_notes_musician,
    chord_difficulty,
    chord_fingers,
    chord_roman,
    get_pitch_class
)
from backend.models.timeline import ChordEvent, SongTimeline


# Stage 2: Comprehensive, deterministic harmonic reduction table
REDUCTION_TABLE: Dict[str, str] = {}

# Build reduction map for all roots
for _root in NOTE_NAMES + NOTE_FLAT:
    # Major triad reductions
    for _sfx in ['maj7', 'maj9', 'maj11', 'maj13', 'maj', '6', 'add9', '9', '11', '13', '7', 'dom7', '5', '2']:
        REDUCTION_TABLE[f"{_root}{_sfx}"] = _root
    # Minor triad reductions
    for _sfx in ['m7', 'm9', 'm11', 'm13', 'm6', 'madd9', 'min7', 'min9', 'min']:
        REDUCTION_TABLE[f"{_root}{_sfx}"] = f"{_root}m"
    # Suspended preservation
    for _sfx in ['sus2', 'sus4', 'sus']:
        REDUCTION_TABLE[f"{_root}{_sfx}"] = f"{_root}{_sfx}"
    # Diminished / Augmented base fallbacks
    for _sfx in ['dim', 'dim7', '°', 'm7b5', 'ø']:
        REDUCTION_TABLE[f"{_root}{_sfx}"] = f"{_root}dim"
    for _sfx in ['aug', '+', '+5']:
        REDUCTION_TABLE[f"{_root}{_sfx}"] = _root


# Stage 3: Categorized sets for beginner difficulty
EASY_CHORDS = {'C', 'G', 'F', 'Am', 'Em', 'Dm'}
BLACK_KEY_PITCHES = {1, 3, 6, 8, 10}


def evaluate_beginner_difficulty(chord_name: str) -> str:
    """
    Evaluates chord difficulty for beginner piano players:
    - EASY: Natural white-key triads (C, G, F, Am, Em, Dm)
    - MODERATE: Black-key involved triads and simple 7ths (D, A, E, Bm, Bb, Eb, etc.)
    - DIFFICULT: Diminished, augmented, or multi-black key minor chords (Abm, Ebm, Bdim)
    """
    if not chord_name or chord_name == 'N':
        return 'EASY'
    
    clean = musician_friendly_name(chord_name)
    if 'dim' in clean or '°' in clean or 'aug' in clean or '+' in clean or 'm7b5' in clean:
        return 'DIFFICULT'
    
    if clean in EASY_CHORDS:
        return 'EASY'
    
    # Check black keys involvement
    notes = chord_note_indices(clean)
    black_count = sum(1 for n in notes if n in BLACK_KEY_PITCHES)
    is_minor = 'm' in clean and not clean.endswith('maj7')
    
    if black_count >= 2 and is_minor:
        return 'DIFFICULT'
    elif black_count >= 1 or '7' in clean or is_minor:
        return 'MODERATE'
    
    return 'EASY'



def reduce_chord_harmony(chord_name: str, key: Optional[str] = None, scale: Optional[str] = None) -> str:
    """
    STAGE 1 & 2: Normalizes and harmonically reduces a single chord symbol.
    - Strips non-essential extensions (Cmaj7 -> C, Am7 -> Am, G7 -> G).
    - Resolves diminished chords to their diatonic function relative to key/scale when available.
    - Deterministic fallback for unknown inputs.
    """
    if not chord_name or chord_name == 'N':
        return 'N'
    
    name = musician_friendly_name(chord_name.strip())
    
    # 1. Lookup in deterministic reduction table
    reduced = REDUCTION_TABLE.get(name)
    
    if not reduced:
        # Fallback parser for arbitrary chord naming strings
        root_pc = get_pitch_class(name)
        if root_pc is not None:
            root_str = NOTE_FLAT[root_pc] if 'b' in name else NOTE_NAMES[root_pc]
            if 'm' in name and not name.startswith(('maj', 'Maj')) and 'dim' not in name:
                reduced = f"{root_str}m"
            elif 'sus2' in name:
                reduced = f"{root_str}sus2"
            elif 'sus4' in name or 'sus' in name:
                reduced = f"{root_str}sus4"
            else:
                reduced = root_str
        else:
            return 'N'

    # 2. Diatonic substitution for diminished harmonies if key is known
    if 'dim' in reduced:
        c_root = get_pitch_class(reduced)
        key_root = get_pitch_class(key) if key else None
        if c_root is not None and key_root is not None:
            is_minor = (scale == 'Minor') if scale else False
            rel_interval = (c_root - key_root) % 12
            if is_minor:
                # In minor key, ii° (e.g. Bdim in Am) -> iv (Dm)
                if rel_interval == 2:
                    return musician_friendly_name(f"{NOTE_NAMES[(key_root + 5) % 12]}m")
                return musician_friendly_name(f"{NOTE_NAMES[c_root]}m")
            else:
                # In major key, vii° (e.g. Bdim in C) -> V (G)
                if rel_interval == 11:
                    return musician_friendly_name(f"{NOTE_NAMES[(key_root + 7) % 12]}")
                return musician_friendly_name(f"{NOTE_NAMES[c_root]}m")
        else:
            # Safe generic fallback without key context: map diminished to root minor
            c_root = get_pitch_class(reduced)
            return musician_friendly_name(f"{NOTE_NAMES[c_root]}m") if c_root is not None else 'N'

    return musician_friendly_name(reduced)


def simplify_progression(
    chords: List[Union[ChordEvent, Dict[str, Any]]],
    tempo: Optional[float] = None,
    key: Optional[str] = None,
    scale: Optional[str] = None,
    min_duration_seconds: Optional[float] = None,
    beat_threshold: float = 2.0
) -> List[ChordEvent]:
    """
    STAGE 4: Progression-level simplification engine.
    - Evaluates surrounding chord context.
    - Merges consecutive identical chords.
    - Eliminates short passing chords based on tempo/BPM-aware threshold.
    - Generates new beginner ChordEvents without mutating input events.
    """
    if not chords:
        return []

    # Calculate tempo/beat-aware minimum passing duration
    # Default: 2 beats at the song tempo (e.g., 1.0s at 120 BPM), clamped between 0.8s and 2.0s
    if min_duration_seconds is not None:
        min_dur = max(0.5, float(min_duration_seconds))
    elif tempo and tempo > 0:
        beat_seconds = 60.0 / float(tempo)
        min_dur = max(0.8, min(2.0, beat_seconds * beat_threshold))
    else:
        min_dur = 1.0

    # Pass 1: Harmonically reduce each chord
    reduced_events: List[Dict[str, Any]] = []
    for c in chords:
        if isinstance(c, ChordEvent):
            start = float(c.start_time)
            end = float(c.end_time)
            c_name = c.chord_name
            conf = c.confidence
            raw = c.raw_chord
        else:
            start = float(c.get('time', c.get('startTime', c.get('start', 0.0))))
            end = float(c.get('end', c.get('endTime', 0.0)))
            c_name = c.get('chord', c.get('chordName', 'N'))
            conf = c.get('confidence', 1.0)
            raw = c.get('raw_chord', c.get('rawChord'))

        simplified_name = reduce_chord_harmony(c_name, key=key, scale=scale)
        reduced_events.append({
            'start': start,
            'end': end,
            'chord': simplified_name,
            'raw_chord': raw,
            'confidence': conf
        })

    # Pass 2: Merge adjacent identical chords
    merged: List[Dict[str, Any]] = []
    for c in reduced_events:
        if not merged:
            merged.append(c.copy())
        else:
            last = merged[-1]
            if last['chord'] == c['chord']:
                last['end'] = c['end']
                if last['confidence'] is not None and c['confidence'] is not None:
                    last['confidence'] = max(last['confidence'], c['confidence'])
            else:
                merged.append(c.copy())

    # Pass 3: Absorb short passing chords (< min_dur)
    smoothed: List[Dict[str, Any]] = []
    i = 0
    while i < len(merged):
        c = merged[i]
        dur = c['end'] - c['start']

        if dur < min_dur and len(merged) > 1:
            if not smoothed:
                # Initial short chord -> absorb into next if available
                if i + 1 < len(merged):
                    merged[i + 1]['start'] = c['start']
                else:
                    smoothed.append(c.copy())
            elif i + 1 == len(merged):
                # Final short chord -> absorb into previous
                smoothed[-1]['end'] = c['end']
            else:
                # Middle short chord -> decide whether to merge with previous or next
                prev_c = smoothed[-1]
                next_c = merged[i + 1]
                
                prev_conf = prev_c['confidence'] if prev_c['confidence'] is not None else 1.0
                next_conf = next_c['confidence'] if next_c['confidence'] is not None else 1.0

                if prev_c['chord'] == 'N' and next_c['chord'] != 'N':
                    next_c['start'] = c['start']
                elif next_c['chord'] == 'N' and prev_c['chord'] != 'N':
                    prev_c['end'] = c['end']
                elif prev_conf >= next_conf:
                    prev_c['end'] = c['end']
                else:
                    next_c['start'] = c['start']
        else:
            smoothed.append(c.copy())
        i += 1

    # Pass 4: Final merge of any consecutive chords merged during pass 3
    final_merged: List[Dict[str, Any]] = []
    for c in smoothed:
        if not final_merged:
            final_merged.append(c.copy())
        else:
            last = final_merged[-1]
            if last['chord'] == c['chord']:
                last['end'] = c['end']
                if last['confidence'] is not None and c['confidence'] is not None:
                    last['confidence'] = max(last['confidence'], c['confidence'])
            else:
                final_merged.append(c.copy())

    # STAGE 5: Timeline generation (create new ChordEvents)
    beginner_events: List[ChordEvent] = []
    for item in final_merged:
        c_name = item['chord']
        notes = chord_note_indices(c_name) if c_name != 'N' else []
        note_names = get_chord_notes_musician(c_name) if c_name != 'N' else []
        fingering = chord_fingers(c_name) if c_name != 'N' else {}
        difficulty = evaluate_beginner_difficulty(c_name)
        roman = chord_roman(c_name, key, scale) if (key and scale and c_name != 'N') else None

        event = ChordEvent(
            startTime=round(item['start'], 3),
            endTime=round(item['end'], 3),
            chordName=c_name,
            rawChord=item.get('raw_chord'),
            notes=notes if notes else None,
            noteNames=note_names if note_names else None,
            fingering=fingering if fingering else None,
            difficulty=difficulty,
            romanNumeral=roman,
            confidence=round(item['confidence'], 3) if item['confidence'] is not None else None
        )
        beginner_events.append(event)

    return beginner_events


def simplify_timeline(timeline: SongTimeline, min_duration_seconds: Optional[float] = None) -> SongTimeline:
    """
    Transforms SongTimeline.original_chords -> Beginner Simplification Engine -> SongTimeline.beginner_chords.
    Never modifies SongTimeline.original_chords.
    """
    if not timeline or not timeline.original_chords:
        timeline.beginner_chords = []
        return timeline

    tempo = timeline.metadata.tempo if timeline.metadata else None
    key = timeline.metadata.key if timeline.metadata else None
    scale = timeline.metadata.scale if timeline.metadata else None

    # Generate beginner timeline events
    beginner_chords = simplify_progression(
        chords=timeline.original_chords,
        tempo=tempo,
        key=key,
        scale=scale,
        min_duration_seconds=min_duration_seconds
    )

    # Compute unique beginner chords
    b_freq: Dict[str, float] = {}
    for c in beginner_chords:
        conf = c.confidence if c.confidence is not None else 1.0
        b_freq[c.chord_name] = b_freq.get(c.chord_name, 0.0) + conf
    unique_beg = [c for c in sorted(b_freq, key=lambda k: -b_freq[k]) if c != 'N']

    # Update beginner properties on timeline without touching original_chords
    timeline.beginner_chords = beginner_chords
    timeline.unique_beginner_chords = unique_beg
    if timeline.metadata:
        # Keep in original key (no auto-transposition in Phase 2B)
        timeline.metadata.easy_key = timeline.metadata.key
        timeline.metadata.easy_key_full = timeline.metadata.key_full
        timeline.metadata.transpose_offset = 0

    return timeline
