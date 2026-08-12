"""
backend/theory/theory.py

Music Theory Engine — pure Python, no ML dependencies.

Responsibilities:
  - Enharmonic normalization (ensures chord names are musician-friendly)
  - Chord note index calculation (pitch classes 0–11 from a chord symbol string)
  - Fingering assignment (which finger plays which note)
  - Chord difficulty rating (easy/medium/hard based on black-key involvement)
  - Roman numeral analysis (I, IV, V, vi etc. relative to detected key)
  - Chord simplification for Beginner Mode
  - Transposition to beginner-friendly keys
"""

import numpy as np

NOTE_NAMES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
NOTE_FLAT  = ['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B']

ENHARMONIC_MAP = {
    'G#': 'Ab', 'G#m': 'Abm', 'G#7': 'Ab7', 'G#maj7': 'Abmaj7', 'G#m7': 'Abm7',
    'D#': 'Eb', 'D#m': 'Ebm', 'D#7': 'Eb7', 'D#maj7': 'Ebmaj7', 'D#m7': 'Ebm7',
    'A#': 'Bb', 'A#m': 'Bbm', 'A#7': 'Bb7', 'A#maj7': 'Bbmaj7', 'A#m7': 'Bbm7',
    'Gb': 'F#', 'Gbm': 'F#m', 'Gb7': 'F#7', 'Gbmaj7': 'F#maj7', 'Gbm7': 'F#m7',
    'Db': 'C#',
}

# Diatonic scale intervals
MAJOR_INTERVALS = [0, 2, 4, 5, 7, 9, 11]
MINOR_INTERVALS = [0, 2, 3, 5, 7, 8, 10]

# List of easy keys for transposing (maximum 1 sharp or flat)
EASY_MAJOR_KEYS = [
    ('C', 0, 0),  # (Name, pitch class, accidentals)
    ('G', 7, 1),
    ('F', 5, 1),
]

EASY_MINOR_KEYS = [
    ('Am', 9, 0),
    ('Em', 4, 1),
    ('Dm', 2, 1),
]

def musician_friendly_name(name):
    """
    Converts sharp-side enharmonics to their flat-side equivalents.

    Convention used by HotChords:
      - Black keys prefer flats: Ab, Eb, Bb (not G#, D#, A#)
        Rationale: flats are standard in jazz lead sheets and classical scores.
      - Exception: F# is kept as F# (more natural in guitar contexts than Gb).
      - Gb is converted to F# for this same reason.
    """
    if name == 'N': return 'N'
    if name.startswith('G#'): return name.replace('G#', 'Ab')
    if name.startswith('Gb'): return name.replace('Gb', 'F#')
    if name.startswith('D#'): return name.replace('D#', 'Eb')
    return ENHARMONIC_MAP.get(name, name)

def chord_note_indices(name):
    if name == 'N': return []
    if name.endswith('maj7'):
        root = name[:-4]; ivs = [0, 4, 7, 11]
    elif name.endswith('m7'):
        root = name[:-2]; ivs = [0, 3, 7, 10]
    elif name.endswith('7') and not name.endswith('maj7'):
        root = name[:-1]; ivs = [0, 4, 7, 10]
    elif name.endswith('m') and len(name) > 1:
        root = name[:-1]; ivs = [0, 3, 7]
    else:
        root = name; ivs = [0, 4, 7]
        
    try: idx = NOTE_NAMES.index(root)
    except:
        try: idx = NOTE_FLAT.index(root)
        except: return []
    return [(idx + i) % 12 for i in ivs]

def get_chord_notes_musician(name):
    idxs = chord_note_indices(name)
    friendly = musician_friendly_name(name)
    use_flats = 'b' in friendly
    return [NOTE_FLAT[i] if use_flats else NOTE_NAMES[i] for i in idxs]

def chord_note_names(name):
    return [NOTE_FLAT[i] for i in chord_note_indices(name)]

def chord_fingers(name):
    """
    Returns a simplified finger-to-pitch-class mapping for basic display.
    Assignment: root=1 (thumb), 3rd=3 (middle), 5th=5 (pinky).
    This is a pedagogical approximation — the full per-octave voicing
    is computed by pianoFingeringEngine.js in the frontend.
    """
    notes = chord_note_indices(name)
    if len(notes) < 3: return {}
    return {notes[0]: 1, notes[1]: 3, notes[2]: 5}

def chord_difficulty(name):
    """
    Rates a chord as 'easy', 'medium', or 'hard' for beginner guidance.

    Heuristic:
      - Black keys (C#/Db, D#/Eb, F#/Gb, G#/Ab, A#/Bb) are harder to play
        because they require thumb-under or position shifts.
      - Minor chords are slightly harder than major due to the minor 3rd span.
      - Combining both = 'hard' (e.g. Abm, Ebm).
    """
    if name == 'N': return 'easy'
    root = name.replace('maj7','').replace('m7','').replace('7','').rstrip('m')
    black = {1, 3, 6, 8, 10}  # MIDI pitch class indices of black keys
    try: idx = NOTE_NAMES.index(root)
    except: return 'medium'
    is_min = 'm' in name and not name.endswith('maj7')
    if idx in black and is_min: return 'hard'
    if idx in black: return 'medium'
    if is_min: return 'medium'
    return 'easy'

def _scale_notes(root_idx, is_minor):
    ivs = MINOR_INTERVALS if is_minor else MAJOR_INTERVALS
    return [(root_idx + i) % 12 for i in ivs]

def chord_roman(chord_name, key, scale):
    ROMAN       = ['I','II','III','IV','V','VI','VII']
    ROMAN_LOWER = ['i','ii','iii','iv','v','vi','vii']
    try:
        root = chord_name.replace('maj7','').replace('m7','').replace('7','').rstrip('m')
        is_min = 'm' in chord_name and not chord_name.endswith('maj7')
        ki = NOTE_FLAT.index(key) if key in NOTE_FLAT else NOTE_NAMES.index(key)
        ci = NOTE_FLAT.index(root) if root in NOTE_FLAT else NOTE_NAMES.index(root)
        sc = MINOR_INTERVALS if scale == 'Minor' else MAJOR_INTERVALS
        interval = (ci - ki) % 12
        if interval in sc:
            deg = sc.index(interval)
            return ROMAN_LOWER[deg] if is_min else ROMAN[deg]
    except: pass
    return ''

# Basic collapse rules mapping extended chords to major/minor triads
SIMPLIFY = {}
for _n in NOTE_NAMES:
    for _e in ['maj7','maj9','6','add9','sus2','sus4','2','5','maj']:
        SIMPLIFY[f"{_n}{_e}"] = _n
    for _e in ['7','9','11','13']:
        SIMPLIFY[f"{_n}{_e}"] = _n
    for _e in ['m7','m9','m11','m6','madd9']:
        SIMPLIFY[f"{_n}{_e}"] = _n+'m'
    for _e in ['dim','dim7','°','m7b5']:
        SIMPLIFY[f"{_n}{_e}"] = _n+'m'
    for _e in ['aug','+']:
        SIMPLIFY[f"{_n}{_e}"] = _n

for _n in NOTE_FLAT:
    for _e in ['maj7','maj9','6','add9','sus2','sus4','2','5','maj']:
        SIMPLIFY[f"{_n}{_e}"] = _n
    for _e in ['7','9','11','13']:
        SIMPLIFY[f"{_n}{_e}"] = _n
    for _e in ['m7','m9','m11','m6','madd9']:
        SIMPLIFY[f"{_n}{_e}"] = _n+'m'
    for _e in ['dim','dim7','°','m7b5']:
        SIMPLIFY[f"{_n}{_e}"] = _n+'m'
    for _e in ['aug','+']:
        SIMPLIFY[f"{_n}{_e}"] = _n

def simplify_chord(c):
    return SIMPLIFY.get(c, c)

def get_pitch_class(note_name):
    if not note_name or note_name == 'N': return None
    # Extract root note (first 2 chars if second is accidental, else first 1 char)
    if len(note_name) > 1 and note_name[1] in ['#', 'b']:
        root = note_name[:2]
    else:
        root = note_name[:1]
        
    if root in NOTE_NAMES:
        return NOTE_NAMES.index(root)
    if root in NOTE_FLAT:
        return NOTE_FLAT.index(root)
    return None

def transpose_chord(chord_name, semitones):
    if chord_name == 'N': return 'N'
    # Find root note and suffix
    if len(chord_name) > 1 and (chord_name[1] == '#' or chord_name[1] == 'b'):
        root = chord_name[:2]
        suffix = chord_name[2:]
    else:
        root = chord_name[:1]
        suffix = chord_name[1:]
        
    try:
        p = NOTE_FLAT.index(root)
        use_flats = True
    except ValueError:
        try:
            p = NOTE_NAMES.index(root)
            use_flats = False
        except ValueError:
            return chord_name
            
    new_p = (p + semitones) % 12
    new_root = NOTE_FLAT[new_p] if use_flats else NOTE_NAMES[new_p]
    return musician_friendly_name(new_root + suffix)

def simplify_progression(chords, key, scale):
    """
    Creates a simplified beginner-friendly version of the chord timeline.
    1. Simplifies chord types to basic major/minor triads (and handles diminished substitutions).
    2. Merges short, passing chords (duration < 1.5s) to slow down the pace.
    3. Calculates if transposition to an easy key (C Maj / A Min etc.) is recommended.
    """
    if not chords:
        return [], key, scale, 0
        
    is_minor = (scale == 'Minor')
    key_root = get_pitch_class(key)
    
    # 1. First Pass: Simplify individual chords and do diatonic mapping
    simplified_raw = []
    for c in chords:
        chord_name = c['chord']
        if chord_name == 'N':
            simplified_name = 'N'
        else:
            # Triad collapse
            simplified_name = simplify_chord(chord_name)
            
            # Diminished chord replacement
            if 'dim' in chord_name or '°' in chord_name or 'm7b5' in chord_name:
                c_root = get_pitch_class(chord_name)
                if c_root is not None and key_root is not None:
                    # Relate to key
                    rel_p = (c_root - key_root) % 12
                    if is_minor:
                        # In minor key, ii° (e.g. Bdim in Am) -> iv (Dm)
                        if rel_p == 2:
                            simplified_name = musician_friendly_name(NOTE_NAMES[(key_root + 5) % 12] + 'm')
                        else:
                            simplified_name = musician_friendly_name(NOTE_NAMES[c_root] + 'm')
                    else:
                        # In major key, vii° (e.g. Bdim in C) -> V (G)
                        if rel_p == 11:
                            simplified_name = musician_friendly_name(NOTE_NAMES[(key_root + 7) % 12])
                        else:
                            simplified_name = musician_friendly_name(NOTE_NAMES[c_root] + 'm')
                            
        simplified_raw.append({
            'time': c['time'],
            'end': c['end'],
            'chord': simplified_name,
            'confidence': c['confidence']
        })
        
    # 2. Second Pass: Merge consecutive identical chords
    merged = []
    for c in simplified_raw:
        if not merged:
            merged.append(c.copy())
        else:
            last = merged[-1]
            if last['chord'] == c['chord']:
                last['end'] = c['end']
                last['confidence'] = max(last['confidence'], c['confidence'])
            else:
                merged.append(c.copy())
                
    # 3. Third Pass: Eliminate short chords (duration < 1.5s) to reduce pacing pressure
    min_dur = 1.5
    smoothed = []
    i = 0
    while i < len(merged):
        c = merged[i]
        dur = c['end'] - c['time']
        
        if dur < min_dur:
            if not smoothed:
                if i + 1 < len(merged):
                    merged[i+1]['time'] = c['time']
                else:
                    smoothed.append(c)
            elif i + 1 == len(merged):
                smoothed[-1]['end'] = c['end']
            else:
                prev_c = smoothed[-1]
                next_c = merged[i+1]
                
                if prev_c['chord'] == 'N' and next_c['chord'] != 'N':
                    next_c['time'] = c['time']
                elif next_c['chord'] == 'N' and prev_c['chord'] != 'N':
                    prev_c['end'] = c['end']
                elif prev_c['confidence'] >= next_c['confidence']:
                    prev_c['end'] = c['end']
                else:
                    next_c['time'] = c['time']
        else:
            smoothed.append(c)
        i += 1

    final_chords = []
    for c in smoothed:
        if not final_chords:
            final_chords.append(c)
        else:
            last = final_chords[-1]
            if last['chord'] == c['chord']:
                last['end'] = c['end']
            else:
                final_chords.append(c)
                
    # 4. Transposition analysis
    transpose_offset = 0
    easy_key_name = key
    easy_scale = scale
    
    if key_root is not None:
        targets = EASY_MINOR_KEYS if is_minor else EASY_MAJOR_KEYS
        current_in_easy = False
        
        for name, pc, acc in targets:
            clean_key_name = key.replace('m', '')
            clean_target_name = name.replace('m', '')
            if get_pitch_class(clean_key_name) == pc:
                current_in_easy = True
                break
                
        if not current_in_easy:
            best_dist = 99
            best_target_name = None
            
            for name, pc, acc in targets:
                dist = (pc - key_root) % 12
                if dist > 5:
                    dist -= 12
                if abs(dist) < abs(best_dist):
                    best_dist = dist
                    best_target_name = name
                    
            if best_target_name:
                transpose_offset = best_dist
                easy_key_name = best_target_name
                
    # Generate transposed beginner chords if offset != 0
    beginner_chords = []
    for c in final_chords:
        new_c = c.copy()
        if transpose_offset != 0:
            new_c['chord'] = transpose_chord(c['chord'], transpose_offset)
        beginner_chords.append(new_c)
        
    return beginner_chords, easy_key_name, transpose_offset
