# Audio Analysis Pipeline

HotChords uses a multi-stage Digital Signal Processing (DSP) and Machine Learning pipeline to turn raw audio into a beat-synced chord progression.

The entire pipeline runs locally in Python, primarily leveraging `librosa` and `numpy`.

## Pipeline Stages

### 1. Source Separation (Optional)
If installed, HotChords uses **Demucs** (`htdemucs` model) to split the audio into 4 stems: Vocals, Drums, Bass, and Other. 
We combine Bass + Other into a single "Instrumental" stem. This removes vocals (which confuse chord detectors with pitch glides) and isolates the harmonic content.

### 2. Audio Loading
Audio is loaded downsampled to **22050 Hz mono**. 
Since the highest note on a standard piano (C8) is ~4186 Hz, a 22kHz sample rate (Nyquist limit ~11kHz) provides more than enough resolution while cutting memory usage in half compared to 44.1kHz.

### 3. Harmonic-Percussive Source Separation (HPSS)
We run `librosa.effects.harmonic()` with a strict `margin=4`.
This median-filtering technique separates sustained tonal sounds (chords) from transient percussive sounds (drum hits). Filtering out the percussion is critical because broadband drum transients corrupt chroma features.

### 4. Chroma Constant-Q Transform (CQT)
We extract pitch-class energy using a Constant-Q Transform.
Unlike STFT, CQT has logarithmically spaced frequency bins, giving equal resolution across all octaves. We use **36 bins per octave** (3x oversampling of the standard 12 notes) to improve pitch accuracy. The resulting chroma features are smoothed over a ~0.4s window to suppress note-onset artifacts.

### 5. Beat Tracking & Quantization
Instead of classifying every 23ms frame independently (which leads to erratic, noisy chord changes), we run `librosa.beat.beat_track` to find musical beat boundaries. 
Chroma features are averaged across each beat segment. This aligns chord detections to the underlying musical grid.

### 6. Overtone-Aware Template Matching
We compute the Cosine Similarity between the normalized beat chroma and 61 predefined chord templates.
Crucially, our templates model real instrument physics: they don't just contain 1s at the chord notes. They also include:
- The Fundamental (1.0)
- The Perfect 5th / 3rd Harmonic (0.35)
- The Major 3rd / 5th Harmonic (0.15)
- The Octave / 2nd Harmonic (0.20)

Modeling overtones prevents the detector from mistaking natural harmonics for false chord tones.

### 7. Viterbi HMM Decoding
The raw template similarities act as emission probabilities for a Hidden Markov Model (HMM). We decode the optimal sequence using the Viterbi algorithm.
Our transition matrix encodes music theory:
- **72% self-transition probability:** Chords tend to last for a few beats.
- **Diatonic Bias:** Chords that fit the detected global key are weighted 3.5x higher.
- **Root Motion Bias:** Transitions moving by a Perfect 4th or 5th (e.g., G -> C) are weighted 2.0x higher, reflecting standard Western harmony.

This ensures the final output isn't just locally optimal, but makes logical musical sense across the entire song.
