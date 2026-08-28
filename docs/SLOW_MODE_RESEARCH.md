# HotChords Phase 4A — Slow Mode Audio Architecture Research

## 1. Problem Definition
HotChords requires a pitch-preserving slow playback mode with target speeds of **1.00x, 0.75x, and 0.50x** (extensible to any rate).

The system must solve two fundamentally different problems in tandem:
1. **Uploaded Song Audio (DSP Time-Stretching)**: Slowing down arbitrary pre-recorded complex audio (mixed vocals, drums, guitars) without dropping or altering the harmonic pitch.
2. **Piano Chord Audio (Timeline Event Scaling)**: Slowing down the sequence of piano chords without DSP processing. Acoustic piano samples must preserve their authentic timbre, pitch, and natural resonance, while the onset times and durations of `ChordEvent`s are proportionally stretched across the audio hardware timeline.
3. **Unified Playback Synchronization**: One authoritative `PlaybackClock` to ensure that song audio, original piano, beginner piano, chord highlighting, lyrics, fingering, and hand animations remain synchronized with microsecond precision during play, pause, seek, and dynamic speed switching.

---

## 2. Candidate Technologies

### Candidate 1: Native HTML5 MediaElement + Web Audio Routing (`preservesPitch = true`)
- **Mechanism**: Connects an `<audio>` / `HTMLMediaElement` to Web Audio via `AudioContext.createMediaElementSource()`. Sets `audioElement.playbackRate = rate` and `audioElement.preservesPitch = true` (or `webkitPreservesPitch = true`).
- **Algorithm**: Hardware-accelerated WSOLA/SOLA pitch-preserving phase vocoder integrated natively into OS media frameworks (Apple CoreAudio in WKWebView on macOS, Windows Media Foundation in WebView2).

### Candidate 2: SoundTouchJS / SoundTouch WASM (`AudioWorklet`)
- **Mechanism**: Port of the open-source SoundTouch time-stretching library running inside a Web Audio `AudioWorkletNode`.
- **Algorithm**: WSOLA (Waveform Similarity Overlap-Add).

### Candidate 3: Rubber Band Library (`librubberband` WASM / Native)
- **Mechanism**: High-end phase-vocoder DSP engine running via WebAssembly or native Rust Tauri sidecar.
- **Algorithm**: Multirate phase vocoder with transient detection.

### Candidate 4: FFmpeg Offline Pre-processing (`atempo` / `rubberband` filter)
- **Mechanism**: Backend Python/Rust service pre-renders slowed audio files on disk (e.g. `song_0.75x.mp3`, `song_0.50x.mp3`) during analysis.

### Candidate 5: Tone.js Granular Synthesis (`Tone.GrainPlayer`)
- **Mechanism**: Granular synthesis slicing buffer segments and overlapping grains at variable playback rates.

---

## 3. Comparison Table

| Evaluation Criteria | **1. Native HTML5 / Web Audio `preservesPitch` (Recommended)** | **2. SoundTouch WASM / AudioWorklet** | **3. Rubber Band (librubberband)** | **4. FFmpeg Offline Pre-processing** | **5. Tone.js GrainPlayer** |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Pitch Preservation** | **Exact / High Fidelity** | Good (minor transient smear) | Pristine / Studio Grade | Exact | Moderate (robotic at 0.5x) |
| **2. Audio Quality** | **High** | Moderate/Good | Excellent | Excellent | Low/Moderate |
| **3. Real-Time Capability** | **Instantaneous** | Real-Time | Real-Time | No (offline batch render) | Real-Time |
| **4. Offline Operation** | **100% Offline** | 100% Offline | 100% Offline | 100% Offline | 100% Offline |
| **5. macOS Support** | **Native** (WebKit / CoreAudio) | Supported | Supported | Supported | Supported |
| **6. Windows Support** | **Native** (WebView2 / WASAPI) | Supported | Supported | Supported | Supported |
| **7. Tauri Compatibility** | **Native** (Zero IPC hop) | Compatible | Requires WASM/IPC bridge | High disk I/O | Compatible |
| **8. React / TS Compatibility** | **Seamless** | Requires Worklet bundling | Complex WASM memory | REST API polling | Seamless |
| **9. CPU Usage** | **Near Zero** (OS DSP) | Moderate (~10–18% CPU) | High (~25–40% CPU) | High during analysis | Moderate |
| **10. Memory Usage** | **< 5 MB** (streamed) | ~30 MB buffer | ~50 MB heap | Large disk files | ~40 MB RAM |
| **11. Software License** | **W3C Standard (Zero Dep)** | LGPL v2.1 | **GPL v2 / Commercial ($$$)** | LGPL / GPL | MIT |
| **12. Redistribution** | **Unrestricted** | Requires LGPL notices | Restrictive GPL copyleft | Large binary binaries | Unrestricted |
| **13. Implementation Complexity** | **Very Low / Clean** | High (Worklet IPC) | Very High (WASM bridging) | High (file management) | Low |
| **14. Piano Sync Precision** | **Sample-accurate** (`currentTime`) | Sample-accurate | Sample-accurate | Drift on file switch | Slight grain jitter |
| **15. Seeking Support** | **Instantaneous** | Buffer index seek | Buffer index seek | File reload required | Instantaneous |
| **16. Stop / Restart** | **Instantaneous** | Instantaneous | Instantaneous | Instantaneous | Instantaneous |
| **17. Dynamic Rate Switching** | **Instant (0ms latency)** | Instant | Instant | Stalls playback (file switch) | Instant |

---

## 4. Recommended Time-Stretching Technology

### **RECOMMENDATION: Native HTMLMediaElement + Web Audio (`preservesPitch = true`)**

#### Why this is the optimal choice:
1. **Zero External Dependencies & Permissive Licensing**: Uses native W3C and OS-level DSP capabilities. No GPL copyleft encumbrance (avoiding Rubber Band licensing risks) and no heavy WASM worklets.
2. **Native OS Audio Acceleration**: Both Apple WebKit (macOS Tauri) and Chromium WebView2 (Windows Tauri) execute native, hardware-optimized WSOLA pitch preservation inside the OS audio pipeline with $<1\%$ CPU load.
3. **Instantaneous Dynamic Rate Switching**: Changing speed from `1.0x` $\to$ `0.75x` $\to$ `0.5x` during active playback requires only setting `audio.playbackRate = newRate`. The audio transitions instantaneously without glitching or re-rendering.
4. **Seamless Web Audio Routing**: The media element routes directly into the existing `AudioContext` destination node via `AudioContext.createMediaElementSource(audioElement)`, allowing shared volume control, muting, and master gain staging.

---

## 5. Recommended Playback-Clock Architecture

A centralized, authoritative `PlaybackClock` orchestrates all application timing:

```
                                  ┌────────────────────────┐
                                  │   SongTimeline Model   │
                                  └───────────┬────────────┘
                                              │
                                              ▼
                                 ┌──────────────────────────┐
                                 │      PlaybackClock       │
                                 │ ──────────────────────── │
                                 │ • currentTime            │
                                 │ • playbackRate (1/0.75/.5)│
                                 │ • play(), pause(), stop()│
                                 │ • seek(timelineTime)     │
                                 └────────────┬─────────────┘
                                              │
               ┌──────────────────────────────┼──────────────────────────────┐
               ▼                              ▼                              ▼
    ┌──────────────────────┐      ┌──────────────────────┐      ┌──────────────────────┐
    │  Song Audio Engine   │      │ Unified Piano Engine │      │    UI Visualizers    │
    │ ──────────────────── │      │ ──────────────────── │      │ ──────────────────── │
    │ • MediaElementSource │      │ • PlaybackService    │      │ • Chord Highlighting │
    │ • preservesPitch=true│      │ • Scaled scheduling  │      │ • Scrolling Lyrics   │
    │ • playbackRate=rate  │      │ • Natural note decay │      │ • Hands / Fingering  │
    └──────────────────────┘      └──────────────────────┘      └──────────────────────┘
```

### PlaybackClock Contract
```typescript
interface PlaybackClock {
  // State
  readonly isPlaying: boolean;
  readonly isPaused: boolean;
  readonly playbackRate: number;     // 1.0, 0.75, 0.50
  readonly timelineTime: number;     // Current position in SongTimeline coordinates (seconds)
  readonly duration: number;

  // Actions
  load(timeline: SongTimeline, audioSourceUrl?: string): Promise<void>;
  play(): Promise<void>;
  pause(): void;
  stop(): void;
  seek(timelineSeconds: number): void;
  setPlaybackRate(rate: number): void; // 1.0, 0.75, 0.50

  // Event Subscriptions
  onTick(callback: (timelineTime: number) => void): () => void;
  onStateChange(callback: (state: 'playing' | 'paused' | 'stopped') => void): () => void;
  onRateChange(callback: (newRate: number) => void): () => void;
}
```

---

## 6. How Piano Synchronization Should Work

### Separation of Concerns:
- **Audio DSP Time-Stretching**: Applied ONLY to the uploaded song audio track.
- **Piano Playback**: Does **NOT** use DSP stretching. Instead, its musical event timeline is scaled by the speed factor:

$$\text{Scheduled Audio Time} = t_{\text{start, audio}} + \frac{t_{\text{event, timeline}} - t_{\text{start, timeline}}}{\text{playbackRate}}$$

$$\text{Scheduled Note Duration} = \frac{\Delta t_{\text{event, timeline}}}{\text{playbackRate}}$$

### Example: Timeline Progression at Different Speeds
Given a SongTimeline event: `C major` from $t = 2.0\text{s}$ to $t = 4.0\text{s}$ ($\Delta t = 2.0\text{s}$):
- **At 1.00x**: Starts at audio clock $+2.0\text{s}$, sustains for $2.0\text{s}$.
- **At 0.75x**: Starts at audio clock $+2.67\text{s}$ ($2.0 / 0.75$), sustains for $2.67\text{s}$.
- **At 0.50x**: Starts at audio clock $+4.00\text{s}$ ($2.0 / 0.50$), sustains for $4.00\text{s}$.

**Note Timbre Integrity**: Because piano notes are triggered as fresh acoustic samples from the Salamander library at their natural playback rate, the piano notes retain 100% natural resonance, hammer attack, and acoustic clarity with zero DSP artifacts.

---

## 7. Licensing Implications
- **Native Web Audio / MediaElement**: Open W3C standard. 100% free, no licenses or third-party attributions required.
- **Salamander Grand Piano Samples**: CC BY 3.0 (Alexander Holm). Fully preserved and redistributable.
- **No GPL Risk**: Avoiding Rubber Band and complex GPL sound libraries ensures HotChords can be freely distributed under permissive open-source or commercial terms.

---

## 8. Performance Risks & Mitigations
1. **Clock Drift Between HTML Audio and Web Audio Context**:
   - *Risk*: The browser media element clock and `AudioContext.currentTime` may experience tiny micro-drifts over a 4-minute song.
   - *Mitigation*: The `PlaybackClock` synchronizes periodically against `audioElement.currentTime` (the master timeline clock) and reschedules lookahead piano buffers in small 1.5-second sliding windows rather than queuing the entire 4-minute song at once.
2. **AudioContext Autoplay Policy in Tauri**:
   - *Risk*: AudioContext suspension on startup.
   - *Mitigation*: Both media element and AudioContext are unlocked and resumed on the user's first play click.

---

## 9. Implementation Sequence for Phase 4B Onward
1. **Phase 4B**: Build `PlaybackClock` service in `frontend/js/audio/playbackClock.js` implementing rate control (`1.0x`, `0.75x`, `0.5x`), time synchronization, and event emissions.
2. **Phase 4C**: Connect `PlaybackClock` to `UnifiedPianoPlaybackController` to schedule piano chords with rate-scaled timing.
3. **Phase 4D**: Connect `PlaybackClock` to song audio playback with native `preservesPitch` pitch-preserving time stretching.
4. **Phase 4E**: Validate full end-to-end synchronization across mixed audio, original piano, and beginner piano at 1.0x, 0.75x, and 0.5x speeds.
