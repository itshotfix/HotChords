import numpy as np
from .constants import NOTE_NAMES, NOTE_FLAT

def _build_templates():
    T = {}
    for i, r in enumerate(NOTE_NAMES):
        # Major triad
        v = np.zeros(12); v[i]=1; v[(i+4)%12]=1; v[(i+7)%12]=1
        T[r] = v / np.linalg.norm(v)
        # Minor triad
        v = np.zeros(12); v[i]=1; v[(i+3)%12]=1; v[(i+7)%12]=1
        T[r+'m'] = v / np.linalg.norm(v)
        # Dominant 7th
        v = np.zeros(12); v[i]=1; v[(i+4)%12]=1; v[(i+7)%12]=1; v[(i+10)%12]=1
        T[r+'7'] = v / np.linalg.norm(v)
        # Minor 7th
        v = np.zeros(12); v[i]=1; v[(i+3)%12]=1; v[(i+7)%12]=1; v[(i+10)%12]=1
        T[r+'m7'] = v / np.linalg.norm(v)
        # Major 7th
        v = np.zeros(12); v[i]=1; v[(i+4)%12]=1; v[(i+7)%12]=1; v[(i+11)%12]=1
        T[r+'maj7'] = v / np.linalg.norm(v)
    T['N'] = np.ones(12)/np.sqrt(12)
    return T

TEMPLATES = _build_templates()
CHORD_NAMES = list(TEMPLATES.keys())
CHORD_MAT = np.array([TEMPLATES[c] for c in CHORD_NAMES]).T

def chord_note_indices(name):
    if name == 'N': return []
    if name.endswith('maj7'):
        root = name[:-4]; ivs = [0,4,7,11]
    elif name.endswith('m7'):
        root = name[:-2]; ivs = [0,3,7,10]
    elif name.endswith('7') and not name.endswith('maj7'):
        root = name[:-1]; ivs = [0,4,7,10]
    elif name.endswith('m') and len(name) > 1:
        root = name[:-1]; ivs = [0,3,7]
    else:
        root = name; ivs = [0,4,7]
    try: idx = NOTE_NAMES.index(root)
    except:
        try: idx = NOTE_FLAT.index(root)
        except: return []
    return [(idx+i)%12 for i in ivs]

def chord_note_names(name):
    return [NOTE_FLAT[i] for i in chord_note_indices(name)]

def chord_difficulty(name):
    if name == 'N': return 'easy'
    root = name.replace('maj7','').replace('m7','').replace('7','').rstrip('m')
    black = {1,3,6,8,10}
    try: idx = NOTE_NAMES.index(root)
    except: return 'medium'
    is_min = 'm' in name and not name.endswith('maj7')
    if idx in black and is_min: return 'hard'
    if idx in black: return 'medium'
    if is_min: return 'medium'
    return 'easy'

SIMPLIFY = {}
for _n in NOTE_NAMES:
    for _e in ['maj7','maj9','6','add9','sus2','sus4','2','5','maj']:
        SIMPLIFY[f"{_n}{_e}"] = _n
    for _e in ['7','9','11','13']:
        SIMPLIFY[f"{_n}{_e}"] = _n
    for _e in ['m7','m9','m11','m6','madd9']:
        SIMPLIFY[f"{_n}{_e}"] = _n+'m'
    for _e in ['dim','dim7','°']:
        SIMPLIFY[f"{_n}{_e}"] = _n+'m'
    for _e in ['aug','+']:
        SIMPLIFY[f"{_n}{_e}"] = _n

def simplify_chord(c): return SIMPLIFY.get(c, c)
