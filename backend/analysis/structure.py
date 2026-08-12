"""
backend/analysis/structure.py

Song structure detection using a chroma novelty curve.

Approach: compute the frame-by-frame rate of change in chroma features.
Peaks in this novelty signal indicate musical boundaries (verse → chorus etc.).

This O(n) approach replaced an earlier O(n²) recurrence matrix
(librosa.segment.recurrence_matrix) that caused the server to hang on
long songs. The novelty curve is faster and sufficient for section labeling.
"""
import numpy as np
import librosa

def detect_structure(chroma, sr, hop, duration):
    """
    Detect musical section boundaries and label them.

    Algorithm:
      1. Compute sum of absolute chroma differences across all 12 pitch classes
         per frame — this is the 'novelty' signal (high = musical change).
      2. Smooth the novelty curve over an 8-second window to ignore micro-changes.
      3. Find local maxima (peaks) in the smoothed novelty curve.
      4. Select the top N peaks as section boundaries (N scales with song length).
      5. Label sections by position: Intro, Verse, Pre-Chorus, Chorus, Bridge, Outro.

    Labels are position-based heuristics, not machine-learned classifications.
    They're approximate but useful for navigating the song in the Practice panel.
    """
    try:
        from scipy.signal import argrelmax
        # Novelty = sum of chroma change per frame across all 12 pitch classes
        diff = np.sum(np.abs(np.diff(chroma, axis=1)), axis=0)
        # Smooth over ~8s to capture section-level changes, not beat-level
        win = max(1, int(sr*8/hop))
        novelty = np.convolve(diff, np.ones(win)/win, mode='same')
        # Scale number of sections with song duration (longer songs have more sections)
        n_sec = max(3, min(8, int(duration//25)))
        peaks = argrelmax(novelty, order=max(1, int(sr*5/hop)))[0]
        top = sorted(sorted(peaks, key=lambda p:-novelty[p])[:n_sec-1]) if len(peaks) >= n_sec-1 else list(peaks)
        bt = librosa.frames_to_time(np.array(top), sr=sr, hop_length=hop).tolist() if len(top) else []
        bounds = [0.0] + bt + [duration]
        n = len(bounds)-1
        labels = []
        for i in range(n):
            pos = i/max(n-1,1)
            if i==0: labels.append('Intro')
            elif i==n-1: labels.append('Outro')
            elif pos<0.30: labels.append('Verse')
            elif pos<0.50: labels.append('Pre-Chorus')
            elif pos<0.70: labels.append('Chorus')
            else: labels.append('Bridge')
        return [{'label':labels[i],'start':round(bounds[i],3),'end':round(bounds[i+1],3)} for i in range(n)]
    except:
        # Fall back to 4 equal sections if scipy or any step fails
        seg = duration/4
        return [
            {'label':'Intro', 'start':0, 'end':round(seg,3)},
            {'label':'Verse', 'start':round(seg,3), 'end':round(seg*2,3)},
            {'label':'Chorus', 'start':round(seg*2,3),'end':round(seg*3,3)},
            {'label':'Outro', 'start':round(seg*3,3),'end':round(duration,3)},
        ]
