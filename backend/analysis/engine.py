import os, librosa, numpy as np
from ..theory.constants import NOTE_FLAT
from ..theory.chords import CHORD_MAT, CHORD_NAMES, chord_note_indices, chord_note_names, chord_fingers, chord_difficulty, simplify_chord
from ..theory.analysis_helpers import detect_key_scale, detect_time_sig, _scale_notes, chord_roman
from ..analysis.structure import detect_structure
from ..analysis.source_separation import separate_stems
from ..utils.progress import upd

def analyze(filepath):
    upd('Loading audio file...', 5)
    # Step 1: Source Separation (Placeholder integrated)
    inst_path, voc_path = separate_stems(filepath, upd_callback=upd)
    
    upd('Preparing song analysis...', 28)
    y, sr = librosa.load(inst_path, sr=22050, mono=True)
    duration = librosa.get_duration(y=y, sr=sr)

    y_harm = librosa.effects.harmonic(y, margin=4)

    upd('Finding musical notes...', 45)
    hop = 512
    chroma = librosa.feature.chroma_cqt(y=y_harm, sr=sr, hop_length=hop, bins_per_octave=36)
    win = max(1, int(0.4*sr/hop))
    chroma_s = np.apply_along_axis(lambda x: np.convolve(x, np.ones(win)/win, 'same'), 1, chroma)

    upd('Calculating tempo...', 55)
    tempo_arr, beat_frames = librosa.beat.beat_track(y=y, sr=sr, hop_length=hop)
    tempo = float(tempo_arr[0]) if hasattr(tempo_arr, '__len__') else float(tempo_arr)
    frame_times = librosa.frames_to_time(np.arange(chroma.shape[1]), sr=sr, hop_length=hop)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop)

    upd('Detecting song key...', 60)
    key, scale = detect_key_scale(chroma.mean(axis=1))
    time_sig = detect_time_sig(y, sr, tempo)
    root_idx = NOTE_FLAT.index(key) if key in NOTE_FLAT else 0
    is_minor = scale == 'Minor'
    scale_note_idxs = _scale_notes(root_idx, is_minor)

    upd('Detecting chords...', 70)
    chroma_norm = chroma_s / (np.linalg.norm(chroma_s, axis=0, keepdims=True)+1e-8)
    similarity = CHORD_MAT.T @ chroma_norm
    boundaries = np.concatenate([[0], beat_times, [duration]])
    chords = []
    for i in range(len(boundaries)-1):
        t0, t1 = boundaries[i], boundaries[i+1]
        mask = (frame_times>=t0)&(frame_times<t1)
        if not np.any(mask): continue
        seg = similarity[:,mask].mean(axis=1)
        idx = int(np.argmax(seg))
        conf = float(np.clip(seg[idx],0,1))
        chords.append({
            'time': round(float(t0), 3),
            'end': round(float(t1), 3),
            'chord': CHORD_NAMES[idx],
            'confidence': round(conf, 3)
        })

    upd('Building results...', 85)
    sections = detect_structure(chroma_s, sr, hop, duration)

    freq = {}
    for c in chords:
        freq[c['chord']] = freq.get(c['chord'], 0) + c['confidence']
    unique_chords = [c for c in sorted(freq, key=lambda k: -freq[k]) if c != 'N']

    simp_map = {}
    for c in unique_chords:
        simp_map[c] = simplify_chord(c)

    all_chords = list(set(unique_chords + list(simp_map.values())))
    chord_data = {}
    for c in all_chords:
        if c == 'N': continue
        idxs = chord_note_indices(c)
        chord_data[c] = {
            'notes': idxs,
            'note_names': chord_note_names(c),
            'fingers': chord_fingers(c),
            'difficulty': chord_difficulty(c),
        }

    roman_numerals = {c: chord_roman(c, key, scale) for c in all_chords if c != 'N'}

    upd('Preparing piano view...', 95)
    upd('Done!', 100)

    return {
        'file': os.path.basename(filepath),
        'duration': round(duration, 2),
        'key': key,
        'scale': scale,
        'key_full': f'{key} {scale}',
        'tempo': round(tempo, 1),
        'time_sig': time_sig,
        'scale_notes': scale_note_idxs,
        'chords': chords,
        'unique_chords': unique_chords,
        'simplified_map': simp_map,
        'chord_data': chord_data,
        'roman_numerals': roman_numerals,
        'sections': sections
    }
