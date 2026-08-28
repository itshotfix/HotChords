# HotChords Lyrics & Transcription Architecture

This document serves as the **official reference architecture** for all lyrics and transcription-related features in HotChords.

---

## 1. Core Architectural Principle

Each domain in the pipeline has a single, strictly bounded responsibility:

| Component | Single Responsibility |
| :--- | :--- |
| **Lyrics** | Owns lyric timing (`startTime`, `endTime`, text, words). |
| **Chords** | Owns chord timing (`startTime`, `endTime`, chord symbol, voicings). |
| **AlignmentEngine** | Owns the relationship and mapping between chords, lyrics, and beat grid. |
| **PlaybackClock** | Owns runtime synchronization and playback time (`PlaybackClock.currentTime`). |

> [!IMPORTANT]
> **Do NOT make one system responsible for all four.**
> Never modify original chord timestamps to fit lyrics.
> Never move lyric timestamps simply because a chord changes.
> `PlaybackClock.currentTime` is the only runtime synchronization source.

---

## 2. Target Architecture Diagram

```
                         UPLOADED SONG
                              │
                            Demucs
                              │
                         VOCAL STEM
                              │
                    ┌─────────┴─────────┐
                    ↓                   ↓
                   VAD                 ASR
                    │                   │
                    │            faster-whisper
                    │                   │
                    │             rough transcript
                    │             + word timestamps
                    │                   │
                    └─────────┬─────────┘
                              ↓
                       WORD ALIGNMENT
                              │
                    precise word timing
                              │
                              ↓
                    TIMESTAMPED LYRICS
                              │
                              │
        ┌─────────────────────┼─────────────────────┐
        ↓                     ↓                     ↓
     Lyrics                Chords                Beat Grid
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              ↓
                     ALIGNMENT ENGINE
                              │
                              ↓
                    CHORD-LYRIC MAP
                              │
                              ↓
                         HotChords UI
                              │
                         PlaybackClock
```

---

## 3. Core Architectural Decisions

1. **Stem Separation**: Use the existing Demucs separation pipeline.
2. **Vocal Isolation**: Prefer the Demucs vocal stem (`vocals.wav`) for transcription.
3. **Initial ASR Engine**: Use `faster-whisper` as the local, offline ASR engine.
4. **Rough vs. Precise**: Treat initial ASR timestamps as **rough** timestamps.
5. **Precision Stage**: Use forced/phoneme alignment as a later precision stage.
6. **Singing Nuances**: Do not assume speech-oriented alignment is perfect for singing.
7. **Timing Signals**: Use vocal activity (VAD) / onset information as a secondary timing signal.
8. **Musical Anchors**: Use chord boundaries as musical anchors, **NOT** as the source of lyric timing.
9. **Soft Constraints**: Use the existing BPM/beat grid information as a **soft** musical constraint.
10. **Chord Invariance**: Never modify original chord timestamps to fit lyrics.
11. **Lyric Invariance**: Never move lyric timestamps simply because a chord changes.
12. **Decoupled Alignment**: Build a dedicated, independent `AlignmentEngine` that derives the relationship.
13. **Dual Timeline Compatibility**: Keep `original_chords` and `beginner_chords` independent. The exact same transcript must work with both.
14. **Single Clock**: Do not create another playback clock. All timestamps use the existing canonical seconds-based timeline (`PlaybackClock.currentTime`).

---

## 4. Efficiency & Caching Requirements

Expensive intermediate analysis results must be cached by song hash:

```
cache/<song_hash>/
    ├── vocals.wav
    ├── chords.json
    ├── transcript.json
    └── aligned_transcript.json
```

### Analysis Invariance
**Do NOT re-run** Demucs, transcription, or alignment when the user only changes:
- Original vs. Beginner mode
- Playback speed / slow mode
- Playback position / seeking

### Parallel Analysis Pipeline
Parallelize independent analysis where practical:

```
Audio
 ├── Chord Analysis
 └── Demucs → Transcription

Then:
 Chord Analysis + Transcript ──► AlignmentEngine ──► Chord-Lyric Map
```

---

## 5. Phased Implementation Roadmap

To maintain system stability and correctness, the lyrics architecture will be rolled out incrementally through distinct phases. **Do not implement future phases prematurely.**

### Phase 1: Foundation (Demucs Vocal Stem → faster-whisper)
- Extract Demucs vocal stem.
- Run offline `faster-whisper` model to produce initial rough transcript with word-level timestamps.
- Cache intermediate audio stems and raw transcripts.

### Phase 2: Precise Word & Phoneme Alignment
- Implement forced/phoneme alignment over the vocal stem.
- Produce precise word-level start and end bounds.

### Phase 3: Multi-Signal Refinement
- Incorporate Vocal Activity Detection (VAD) and onset detection.
- Soft-align with beat grid and chord boundaries.

### Phase 4: Confidence Scoring & Fallbacks
- Word-level confidence evaluation.
- Graceful degradation and fallback heuristics for low-signal or instrumental passages.

### Phase 5: Production UI Integration
- Synchronized lyric teleprompter / karaoke display in HotChords UI.
- Dual-mode (Original / Beginner) chord-over-lyric binding locked to `PlaybackClock`.

---

## 6. Constraints & Non-Negotiables

- **Deterministic Alignment**: Use deterministic temporal and musical alignment algorithms. **Do not use LLMs for chord/lyric matching.**
- **100% Local / Offline**: No cloud APIs, no external network calls, no paid services.
- **Canonical Timeline**: All timestamps throughout the entire system are standard floating-point seconds.
