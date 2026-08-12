import numpy as np
from .constants import NOTE_NAMES, NOTE_FLAT, KS_MAJOR, KS_MINOR

def _scale_notes(root_idx, is_minor):
    ivs = [0,2,3,5,7,8,10] if is_minor else [0,2,4,5,7,9,11]
    return [(root_idx + i) % 12 for i in ivs]

def chord_roman(chord_name, key, scale):
    MAJOR_SCALE = [0,2,4,5,7,9,11]
    MINOR_SCALE = [0,2,3,5,7,8,10]
    ROMAN = ['I','II','III','IV','V','VI','VII']
    ROMAN_LOWER = ['i','ii','iii','iv','v','vi','vii']
    try:
        root = chord_name.replace('maj7','').replace('m7','').replace('7','').rstrip('m')
        is_min = 'm' in chord_name and not chord_name.endswith('maj7')
        ki = NOTE_FLAT.index(key) if key in NOTE_FLAT else NOTE_NAMES.index(key)
        ci = NOTE_FLAT.index(root) if root in NOTE_FLAT else NOTE_NAMES.index(root)
        sc = MINOR_SCALE if scale == 'Minor' else MAJOR_SCALE
        interval = (ci - ki) % 12
        if interval in sc:
            deg = sc.index(interval)
            return ROMAN_LOWER[deg] if is_min else ROMAN[deg]
    except: pass
    return ''

def detect_key_scale(chroma_mean):
    best_r, best_key, best_scale = -2, 'C', 'Major'
    for i in range(12):
        r = np.corrcoef(chroma_mean, np.roll(KS_MAJOR,i))[0,1]
        if r > best_r: best_r, best_key, best_scale = r, NOTE_FLAT[i], 'Major'
        r = np.corrcoef(chroma_mean, np.roll(KS_MINOR,i))[0,1]
        if r > best_r: best_r, best_key, best_scale = r, NOTE_FLAT[i], 'Minor'
    return best_key, best_scale

def detect_time_sig(y, sr, tempo):
    try:
        import librosa
        hop = 512
        onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
        ac = librosa.autocorrelate(onset_env, max_size=int(sr*4/hop))
        bp = int(round(60.0/float(tempo)*sr/hop))
        if bp < 1: return '4/4'
        s4 = ac[bp*4] if bp*4 < len(ac) else 0
        s3 = ac[bp*3] if bp*3 < len(ac) else 0
        return '3/4' if s3 > s4*1.1 else '4/4'
    except: return '4/4'
