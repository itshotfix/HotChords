"""
backend/analysis/pipeline.py

Main audio analysis pipeline for HotChords.

Processing stages (in order):
  1. Optional stem separation via Demucs (removes vocals, isolates instruments)
  2. Audio loading at 22kHz mono (sufficient resolution for chroma features)
  3. HPSS — strips percussive transients so drums don't corrupt chord detection
  4. Chroma CQT — extracts 12-note pitch class energy at 36 bins/octave
  5. Beat tracking — quantizes chord observations to musical beat boundaries
  6. Template matching — cosine similarity against 61 overtone-aware chord templates
  7. Viterbi HMM — smooths noisy per-beat detections using music-theoretic transitions
  8. Theory enrichment — enharmonics, Roman numerals, beginner chart generation
"""

import os
import gc
import tempfile
import numpy as np
import librosa
import torch
from backend.theory.theory import (
    NOTE_NAMES, NOTE_FLAT, musician_friendly_name,
    chord_note_indices, get_chord_notes_musician, chord_fingers,
    chord_difficulty, chord_roman, _scale_notes, get_pitch_class,
    simplify_progression
)

STEMS_DIR = os.path.join(tempfile.gettempdir(), 'hotchords_stems')
if not os.path.exists(STEMS_DIR):
    os.makedirs(STEMS_DIR)

# ══════════════════════════════════════════════════════════════
#  OVERTONE-AWARE TEMPLATES
# ══════════════════════════════════════════════════════════════
def _build_overtone_templates():
    """
    Builds chroma templates for 61 chord types incorporating overtone leaking
    (harmonics) to model physical instruments more accurately.

    Why overtones matter:
    Real instruments produce energy not just at the fundamental pitch but at
    integer multiples (harmonics). A piano C4 will also excite G4 (3rd harmonic),
    E5 (5th harmonic), and C5 (2nd harmonic). If we use flat binary templates
    (1 where the note is, 0 elsewhere), the detector treats this natural overtone
    energy as a false positive for other chords. Modeling it explicitly removes
    that ambiguity.
    """
    T = {}
    chord_types = {
        '': [0, 4, 7],          # Major
        'm': [0, 3, 7],         # Minor
        '7': [0, 4, 7, 10],     # Dominant 7th
        'm7': [0, 3, 7, 10],    # Minor 7th
        'maj7': [0, 4, 7, 11]   # Major 7th
    }
    
    for i, r in enumerate(NOTE_NAMES):
        for suffix, notes in chord_types.items():
            v = np.zeros(12)
            for note in notes:
                pitch = (i + note) % 12
                # Fundamental: full weight
                v[pitch] += 1.0
                # Perfect 5th (3rd harmonic) — very prominent in most instruments
                v[(pitch + 7) % 12] += 0.35
                # Major 3rd (5th harmonic) — present but weaker
                v[(pitch + 4) % 12] += 0.15
                # Octave (2nd harmonic) — always present, moderate strength
                v[(pitch + 12) % 12] += 0.20
            T[r + suffix] = v / np.linalg.norm(v)
            
    T['N'] = np.ones(12) / np.sqrt(12)
    return T

TEMPLATES   = _build_overtone_templates()
CHORD_NAMES = list(TEMPLATES.keys())
CHORD_MAT   = np.array([TEMPLATES[c] for c in CHORD_NAMES]).T  # (12, 61)

# ══════════════════════════════════════════════════════════════
#  KEY, SCALE & TIME SIGNATURES
# ══════════════════════════════════════════════════════════════
KS_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KS_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

def detect_key_scale(chroma_mean):
    best_r, best_key, best_scale = -2.0, 'C', 'Major'
    for i in range(12):
        r = np.corrcoef(chroma_mean, np.roll(KS_MAJOR, i))[0, 1]
        if r > best_r:
            best_r, best_key, best_scale = r, NOTE_FLAT[i], 'Major'
        r = np.corrcoef(chroma_mean, np.roll(KS_MINOR, i))[0, 1]
        if r > best_r:
            best_r, best_key, best_scale = r, NOTE_FLAT[i], 'Minor'
    return best_key, best_scale

def detect_time_sig(y, sr, tempo):
    try:
        hop = 512
        onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
        ac = librosa.autocorrelate(onset_env, max_size=int(sr * 4 / hop))
        bp = int(round(60.0 / float(tempo) * sr / hop))
        if bp < 1: return '4/4'
        s4 = ac[bp * 4] if bp * 4 < len(ac) else 0
        s3 = ac[bp * 3] if bp * 3 < len(ac) else 0
        return '3/4' if s3 > s4 * 1.1 else '4/4'
    except:
        return '4/4'

# ══════════════════════════════════════════════════════════════
#  HMM VITERBI DECODER
# ══════════════════════════════════════════════════════════════
def build_transition_matrix(key, scale):
    """
    Builds a music-theoretically informed transition probability matrix
    favoring self-transitions, diatonic transitions, and root movements
    of fourths and fifths.
    """
    N = len(CHORD_NAMES)
    A = np.zeros((N, N))
    
    # Identify diatonic chords for transition bias
    diatonic_chords = []
    if key != 'N':
        try:
            key_root = NOTE_NAMES.index(key) if key in NOTE_NAMES else NOTE_FLAT.index(key)
            is_minor = (scale == 'Minor')
            intervals = [0, 2, 3, 5, 7, 8, 10] if is_minor else [0, 2, 4, 5, 7, 9, 11]
            suffixes = ['m', 'dim', '', 'm', 'm', '', ''] if is_minor else ['', 'm', 'm', '', '', 'm', 'dim']
            
            for deg, interval in enumerate(intervals):
                root_note = NOTE_NAMES[(key_root + interval) % 12]
                suffix = suffixes[deg]
                diatonic_chords.append(musician_friendly_name(root_note + suffix))
        except:
            pass

    for i in range(N):
        c_from = CHORD_NAMES[i]
        # 72% chance to stay on the same chord (forces temporal stability)
        A[i, i] = 0.72
        
        remaining_weight = 0.28
        weights = np.zeros(N)
        
        for j in range(N):
            if i == j: continue
            c_to = CHORD_NAMES[j]
            weight = 1.0
            
            # Diatonic transition bonus
            if c_to in diatonic_chords:
                weight *= 3.5
                
            # Root motion bonus (fourths/fifths)
            r_from = get_pitch_class(c_from)
            r_to = get_pitch_class(c_to)
            if r_from is not None and r_to is not None:
                interval = (r_to - r_from) % 12
                if interval in [5, 7]: # Perfect 4th (5) or Perfect 5th (7)
                    weight *= 2.0
                    
            if c_from == 'N' or c_to == 'N':
                weight *= 1.5
                
            weights[j] = weight
            
        sum_w = np.sum(weights)
        if sum_w > 0:
            weights = (weights / sum_w) * remaining_weight
            for j in range(N):
                if i != j:
                    A[i, j] = weights[j]
        else:
            # Fallback uniform distribution
            for j in range(N):
                if i != j:
                    A[i, j] = remaining_weight / (N - 1)
                    
    return A

def viterbi_decode(similarity_matrix, transition_matrix):
    """
    Decodes the most likely chord sequence using the Viterbi algorithm in log space
    to avoid numerical underflow.
    """
    T, N = similarity_matrix.shape
    
    # Prevent log(0)
    log_A = np.log(transition_matrix + 1e-100)
    
    # Scale similarities to represent log emission likelihoods
    # Bounded cosine similarity is typically in [0, 1]
    log_emissions = similarity_matrix * 9.0
    
    viterbi_log = np.zeros((T, N))
    backpointer = np.zeros((T, N), dtype=int)
    
    # Initialization (uniform start prior)
    viterbi_log[0] = np.log(1.0 / N) + log_emissions[0]
    
    # Recursion
    for t in range(1, T):
        for n in range(N):
            # Find log( P(state_s at t-1) * P(transition s -> n) )
            temp = viterbi_log[t-1] + log_A[:, n]
            best_s = np.argmax(temp)
            viterbi_log[t, n] = temp[best_s] + log_emissions[t, n]
            backpointer[t, n] = best_s
            
    # Termination
    best_last = np.argmax(viterbi_log[-1])
    
    # Backtrack
    path = [best_last]
    for t in range(T - 1, 0, -1):
        best_last = backpointer[t, path[-1]]
        path.append(best_last)
        
    path.reverse()
    return path

# ══════════════════════════════════════════════════════════════
#  PIPELINE ENTRY POINT
# ══════════════════════════════════════════════════════════════
def run_pipeline(filepath, upd_callback=None):
    def update(msg, pct):
        if upd_callback:
            upd_callback(msg, pct)
        else:
            print(f'  [{pct:3d}%] {msg}')

    update('Loading song...', 5)
    
    # Optional stem separation via torch/demucs with GPU auto-detection
    try:
        from demucs import pretrained
        from demucs.apply import apply_model
        from demucs.audio import save_audio
        
        update('Preparing analysis...', 10)
        
        # Determine best available hardware accelerator
        device = 'cpu'
        if torch.cuda.is_available():
            device = 'cuda'
        elif torch.backends.mps.is_available():
            device = 'mps'
            
        print(f"  [Info] Running Demucs separation on target device: {device}")
        
        model = pretrained.get_model('htdemucs')
        model.to(device)
        
        wav, sr = librosa.load(filepath, sr=model.samplerate, mono=False)
        # Ensure 2D tensor shape (channels, samples)
        if wav.ndim == 1:
            wav = np.stack([wav, wav])
        wav_torch = torch.tensor(wav, device=device).unsqueeze(0)
        
        update('Separating vocals and instruments...', 20)
        with torch.no_grad():
            sources = apply_model(model, wav_torch, device=device)[0]
            
        sources = sources.cpu()
        # Instrumental stem = drums (0) + bass (1) + other (2)
        instrumental_audio = sources[0] + sources[1] + sources[2]
        
        base_name = os.path.basename(filepath).split('.')[0]
        inst_path = os.path.join(STEMS_DIR, f"{base_name}_inst.wav")
        save_audio(instrumental_audio, inst_path, samplerate=model.samplerate)
        
        analysis_path = inst_path
        # Clean up torch resources
        del sources, wav_torch
        if device != 'cpu':
            torch.cuda.empty_cache() if device == 'cuda' else gc.collect()
    except Exception as e:
        print(f"  [Info] AI Separation skipped or failed: {e}")
        analysis_path = filepath

    update('Preparing analysis...', 28)
    # 22kHz is sufficient for chroma (highest piano note C7 ≈ 2093Hz, well below Nyquist)
    # and cuts memory roughly in half versus 44.1kHz.
    y, sr = librosa.load(analysis_path, sr=22050, mono=True)
    duration = librosa.get_duration(y=y, sr=sr)

    # HPSS: separate harmonic (sustained, tonal) from percussive (transient) components.
    # margin=4 uses a stricter filter — we want clean chord tones even at the cost of
    # some attack transients, because drum hits severely distort chroma features.
    y_harm = librosa.effects.harmonic(y, margin=4)

    update('Finding musical notes...', 45)
    hop = 512  # ~23ms per frame at 22kHz — fine enough for beat-level analysis
    # CQT chroma is preferred over STFT chroma because its log-spaced frequency bins
    # give equal resolution per octave. 36 bins/octave = 3× oversampling of the standard
    # 12-bin layout, giving better pitch accuracy for borderline notes.
    chroma = librosa.feature.chroma_cqt(y=y_harm, sr=sr, hop_length=hop, bins_per_octave=36)
    # Smooth chroma over ~0.4s window to suppress note-onset transient artifacts.
    # Without this, brief passing notes and attack energy create spurious detections.
    win = max(1, int(0.4 * sr / hop))
    chroma_s = np.apply_along_axis(lambda x: np.convolve(x, np.ones(win) / win, 'same'), 1, chroma)

    update('Calculating tempo...', 55)
    tempo_arr, beat_frames = librosa.beat.beat_track(y=y, sr=sr, hop_length=hop)
    tempo = float(tempo_arr[0]) if hasattr(tempo_arr, '__len__') else float(tempo_arr)
    frame_times = librosa.frames_to_time(np.arange(chroma.shape[1]), sr=sr, hop_length=hop)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop)

    update('Finding song key...', 60)
    key, scale = detect_key_scale(chroma.mean(axis=1))
    time_sig = detect_time_sig(y, sr, tempo)
    root_idx = NOTE_FLAT.index(key) if key in NOTE_FLAT else 0
    is_minor = scale == 'Minor'
    scale_note_idxs = _scale_notes(root_idx, is_minor)

    update('Detecting chords...', 75)
    # Clamp the L2 norm to avoid division-by-zero in silent sections
    norms = np.linalg.norm(chroma_s, axis=0, keepdims=True)
    norms = np.maximum(norms, 1e-6)
    chroma_norm = chroma_s / norms
    chroma_norm = np.nan_to_num(chroma_norm, nan=0.0, posinf=0.0, neginf=0.0)
    
    # Cosine similarity: dot product of L2-normalized chroma against L2-normalized templates.
    # Result shape: (61 chords, N frames). Higher value = better match.
    similarity = CHORD_MAT.T @ chroma_norm
    # Beat boundaries define the chord segments. Using beats instead of raw frames
    # aligns chord detections with the musical grid and dramatically reduces noise.
    boundaries = np.concatenate([[0], beat_times, [duration]])
    
    T_segments = len(boundaries) - 1
    beat_similarities = np.zeros((T_segments, len(CHORD_NAMES)))
    
    for i in range(T_segments):
        t0, t1 = boundaries[i], boundaries[i+1]
        mask = (frame_times >= t0) & (frame_times < t1)
        if np.any(mask):
            # Average the per-frame similarities within each beat segment.
            # Mean is robust — a single noisy frame won't dominate the beat decision.
            beat_similarities[i] = similarity[:, mask].mean(axis=1)
        else:
            # Silent or very short segment — assign to 'N' (no chord)
            beat_similarities[i] = np.zeros(len(CHORD_NAMES))
            beat_similarities[i][-1] = 1.0  # Index of 'N' in CHORD_NAMES
            
    # Viterbi HMM: find the globally optimal chord sequence.
    # The transition matrix encodes music theory knowledge (diatonic preference,
    # 4th/5th root motion bias, temporal stability) so the decoder doesn't just
    # pick the locally best chord at each beat — it picks the best whole-song sequence.
    update('Applying HMM smoothing...', 82)
    transition_matrix = build_transition_matrix(key, scale)
    viterbi_path = viterbi_decode(beat_similarities, transition_matrix)
    
    chords = []
    for i in range(T_segments):
        t0, t1 = boundaries[i], boundaries[i+1]
        idx = viterbi_path[i]
        raw_name = CHORD_NAMES[idx]
        friendly = musician_friendly_name(raw_name)
        conf = float(np.clip(beat_similarities[i, idx], 0, 1))
        
        chords.append({
            'time': round(float(t0), 3),
            'end': round(float(t1), 3),
            'chord': friendly,
            'raw_chord': raw_name,
            'confidence': round(conf, 3)
        })

    update('Preparing piano view...', 88)
    # Calculate unique chords for chord dictionary details
    freq = {}
    for c in chords:
        freq[c['chord']] = freq.get(c['chord'], 0.0) + c['confidence']
    unique_chords = [c for c in sorted(freq, key=lambda k: -freq[k]) if c != 'N']

    chord_data = {}
    for c in set(unique_chords):
        if c == 'N': continue
        chord_data[c] = {
            'notes': chord_note_indices(c),
            'note_names': get_chord_notes_musician(c),
            'fingers': chord_fingers(c),
            'difficulty': chord_difficulty(c),
        }

    roman_numerals = {c: chord_roman(c, key, scale) for c in unique_chords}
    friendly_key = musician_friendly_name(key)

    # ══════════════════════════════════════════════════════════════
    #  GENERATE BEGINNER CHART
    # ══════════════════════════════════════════════════════════════
    update('Generating beginner chart...', 92)
    beginner_chords, easy_key, transpose_offset = simplify_progression(chords, friendly_key, scale)
    
    # Calculate unique chords for the beginner progression
    b_freq = {}
    for c in beginner_chords:
        b_freq[c['chord']] = b_freq.get(c['chord'], 0.0) + c['confidence']
    unique_beginner_chords = [c for c in sorted(b_freq, key=lambda k: -b_freq[k]) if c != 'N']
    
    for c in set(unique_beginner_chords):
        if c == 'N' or c in chord_data: continue
        chord_data[c] = {
            'notes': chord_note_indices(c),
            'note_names': get_chord_notes_musician(c),
            'fingers': chord_fingers(c),
            'difficulty': chord_difficulty(c),
        }
        
    for c in unique_beginner_chords:
        if c not in roman_numerals:
            roman_numerals[c] = chord_roman(c, easy_key, scale)

    update('Done!', 100)
    
    return {
        'ready': True,
        'duration': round(duration, 2),
        'key': friendly_key,
        'scale': scale,
        'key_full': f'{friendly_key} {scale}',
        'tempo': round(tempo, 1),
        'time_sig': time_sig,
        'scale_notes': scale_note_idxs,
        'chords': chords,
        'unique_chords': unique_chords,
        'chord_data': chord_data,
        'roman_numerals': roman_numerals,
        # Beginner chart output
        'beginner_chords': beginner_chords,
        'unique_beginner_chords': unique_beginner_chords,
        'easy_key': easy_key,
        'easy_key_full': f'{easy_key} {scale}',
        'transpose_offset': int(transpose_offset)
    }
