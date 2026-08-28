/**
 * pianoPlaybackService.js
 * 
 * Core Piano Audio Service for HotChords.
 * Bridges SongTimeline / UI components with Tone.js / Web Audio sample engine.
 * 
 * Architecture:
 * SongTimeline / UI -> PianoPlaybackService -> Tone.Sampler / Web Audio -> Local Audio Samples
 * 
 * Features:
 * - 100% offline sample loading (Yamaha C5 / Salamander Grand Piano, CC-BY 3.0)
 * - Microsecond hardware lookahead scheduling
 * - Simultaneous polyphonic chord playback
 * - Normalized velocity (0.0 to 1.0) and duration control
 * - AudioContext user-gesture resumption & lifecycle management
 * - Clean MIDI / Pitch-Class note conversion utilities
 */

(function(global) {
    'use strict';

    const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
    const NOTE_FLATS = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B'];

    // Full 30-sample multi-sample mapping across the 88-key piano range from official Salamander Grand Piano (CC BY 3.0)
    const DEFAULT_SAMPLE_MAP = {
        'A0': 'A0.mp3',
        'C1': 'C1.mp3', 'D#1': 'Ds1.mp3', 'F#1': 'Fs1.mp3', 'A1': 'A1.mp3',
        'C2': 'C2.mp3', 'D#2': 'Ds2.mp3', 'F#2': 'Fs2.mp3', 'A2': 'A2.mp3',
        'C3': 'C3.mp3', 'D#3': 'Ds3.mp3', 'F#3': 'Fs3.mp3', 'A3': 'A3.mp3',
        'C4': 'C4.mp3', 'D#4': 'Ds4.mp3', 'F#4': 'Fs4.mp3', 'A4': 'A4.mp3',
        'C5': 'C5.mp3', 'D#5': 'Ds5.mp3', 'F#5': 'Fs5.mp3', 'A5': 'A5.mp3',
        'C6': 'C6.mp3', 'D#6': 'Ds6.mp3', 'F#6': 'Fs6.mp3', 'A6': 'A6.mp3',
        'C7': 'C7.mp3', 'D#7': 'Ds7.mp3', 'F#7': 'Fs7.mp3', 'A7': 'A7.mp3',
        'C8': 'C8.mp3'
    };

    const DEFAULT_BASE_URL = '/audio/samples/';


    class PianoPlaybackService {
        constructor() {
            this.state = 'uninitialized'; // 'uninitialized' | 'loading' | 'ready' | 'error'
            this.sustain = false; // Default: OFF
            this.audioCtx = null;
            this.toneSampler = null;
            this.activeNodes = [];
            this.stateListeners = [];
            this.errorListeners = [];
            this.sustainListeners = [];
            this._initPromise = null;
        }

        /**
         * Note Conversion Utilities
         */
        static midiToNoteName(midi) {
            const noteNum = Math.floor(midi);
            const pitch = noteNum % 12;
            const octave = Math.floor(noteNum / 12) - 1;
            return `${NOTE_NAMES[pitch]}${octave}`;
        }

        static noteNameToMidi(name) {
            if (typeof name !== 'string') return 60;
            const match = name.trim().match(/^([A-Ga-g][#b]?)(-?\d+)$/);
            if (!match) return 60;
            const note = match[1].charAt(0).toUpperCase() + match[1].slice(1).toLowerCase();
            const octave = parseInt(match[2], 10);
            let idx = NOTE_NAMES.indexOf(note);
            if (idx === -1) idx = NOTE_FLATS.indexOf(note);
            if (idx === -1) return 60;
            return (octave + 1) * 12 + idx;
        }

        static pitchClassToMidi(pitchClass, octave = 4) {
            return (octave + 1) * 12 + (pitchClass % 12);
        }

        static parseNote(input, defaultOctave = 4) {
            if (typeof input === 'number') {
                // If it's a pitch class 0-11, map to default octave
                if (input >= 0 && input <= 11) {
                    return PianoPlaybackService.pitchClassToMidi(input, defaultOctave);
                }
                return Math.max(21, Math.min(108, input)); // Clamp to 88-key piano MIDI
            }
            if (typeof input === 'string') {
                if (input.match(/\d+$/)) {
                    return PianoPlaybackService.noteNameToMidi(input);
                }
                // Pitch name without octave (e.g. 'C', 'Am' -> 'C4')
                const clean = input.replace('m', '').replace('maj', '').replace('7', '');
                return PianoPlaybackService.noteNameToMidi(`${clean}${defaultOctave}`);
            }
            return 60;
        }

        /**
         * Lifecycle & Initialization
         */
        async initialize(options = {}) {
            if (this.state === 'ready') return true;
            if (this._initPromise) return this._initPromise;

            this._setState('loading');
            const sampleMap = options.sampleMap || DEFAULT_SAMPLE_MAP;
            const baseUrl = options.baseUrl || DEFAULT_BASE_URL;

            this._initPromise = new Promise(async (resolve, reject) => {
                try {
                    // Initialize AudioContext
                    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
                    if (!this.audioCtx && AudioContextClass) {
                        this.audioCtx = new AudioContextClass();
                    }

                    // Check if Tone.js is available in environment
                    if (window.Tone && window.Tone.Sampler) {
                        await this._initToneSampler(sampleMap, baseUrl);
                    } else {
                        // Resilient Native Web Audio Sampler fallback
                        await this._initNativeSampler(sampleMap, baseUrl);
                    }

                    this._setState('ready');
                    resolve(true);
                } catch (err) {
                    console.error('[PianoPlaybackService] Initialization error:', err);
                    this._setState('error', err.message);
                    reject(err);
                } finally {
                    this._initPromise = null;
                }
            });

            return this._initPromise;
        }

        async _initToneSampler(sampleMap, baseUrl) {
            return new Promise((resolve, reject) => {
                try {
                    this.toneSampler = new window.Tone.Sampler({
                        urls: sampleMap,
                        baseUrl: baseUrl,
                        onload: () => resolve(true),
                        onerror: (err) => reject(err)
                    }).toDestination();
                } catch (e) {
                    reject(e);
                }
            });
        }

        async _initNativeSampler(sampleMap, baseUrl) {
            this.nativeBuffers = {};
            const entries = Object.entries(sampleMap);
            const loadPromises = entries.map(async ([noteName, fileName]) => {
                const url = `${baseUrl}${fileName}`;
                try {
                    const resp = await fetch(url);
                    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
                    const arrayBuf = await resp.arrayBuffer();
                    const audioBuf = await this.audioCtx.decodeAudioData(arrayBuf);
                    const midi = PianoPlaybackService.noteNameToMidi(noteName);
                    this.nativeBuffers[midi] = audioBuf;
                } catch (e) {
                    console.warn(`[PianoPlaybackService] Could not preload sample ${url}:`, e);
                }
            });
            await Promise.all(loadPromises);
        }

        async resume() {
            if (window.Tone && window.Tone.context && window.Tone.context.state === 'suspended') {
                await window.Tone.start();
            }
            if (this.audioCtx && this.audioCtx.state === 'suspended') {
                await this.audioCtx.resume();
            }
        }

        /**
         * Core Note & Chord Playback API
         */
        playNote(note, velocity = 0.8, duration = 1.0, time = null) {
            if (this.state !== 'ready') {
                this.initialize().then(() => this.playNote(note, velocity, duration, time)).catch(() => {});
                return;
            }
            this.resume();

            const midi = PianoPlaybackService.parseNote(note);
            const noteName = PianoPlaybackService.midiToNoteName(midi);
            const vel = Math.max(0.01, Math.min(1.0, velocity));
            const baseDur = Math.max(0.05, duration);
            const dur = this.sustain ? Math.max(baseDur * 2.2, baseDur + 2.0) : baseDur;

            if (this.toneSampler && this.toneSampler.loaded) {
                try {
                    if (time !== null && time !== undefined) {
                        this.toneSampler.triggerAttackRelease(noteName, dur, time, vel);
                    } else {
                        this.toneSampler.triggerAttackRelease(noteName, dur, undefined, vel);
                    }
                    return;
                } catch (e) {
                    // Fall through to native playback if Tone trigger fails
                }
            }

            this._playNativeNote(midi, vel, dur, time);
        }

        playChord(notes, velocity = 0.8, duration = 1.0, time = null) {
            if (!notes || !Array.isArray(notes) || notes.length === 0) return;
            if (this.state !== 'ready') {
                this.initialize().then(() => this.playChord(notes, velocity, duration, time)).catch(() => {});
                return;
            }
            this.resume();

            const midiNotes = notes.map(n => PianoPlaybackService.parseNote(n));
            const vel = Math.max(0.01, Math.min(1.0, velocity));
            const baseDur = Math.max(0.05, duration);
            const dur = this.sustain ? Math.max(baseDur * 2.2, baseDur + 2.0) : baseDur;

            if (this.toneSampler && this.toneSampler.loaded) {
                const noteNames = midiNotes.map(m => PianoPlaybackService.midiToNoteName(m));
                try {
                    if (time !== null && time !== undefined) {
                        this.toneSampler.triggerAttackRelease(noteNames, dur, time, vel);
                    } else {
                        this.toneSampler.triggerAttackRelease(noteNames, dur, undefined, vel);
                    }
                    return;
                } catch (e) {
                    // Fallback to native multi-voice
                }
            }

            midiNotes.forEach(m => this._playNativeNote(m, vel, dur, time));
        }

        _playNativeNote(midi, velocity, duration, scheduledTime = null) {
            if (!this.audioCtx) return;
            const startTime = (scheduledTime !== null && scheduledTime !== undefined)
                ? scheduledTime
                : this.audioCtx.currentTime;

            // Find closest available native sample buffer
            const availableMidis = Object.keys(this.nativeBuffers || {}).map(Number);
            if (availableMidis.length === 0) return;

            let closestMidi = availableMidis[0];
            let minDiff = Math.abs(midi - closestMidi);
            for (const m of availableMidis) {
                const diff = Math.abs(midi - m);
                if (diff < minDiff) {
                    minDiff = diff;
                    closestMidi = m;
                }
            }

            const buf = this.nativeBuffers[closestMidi];
            if (!buf) return;

            const semitoneDiff = midi - closestMidi;
            const playbackRate = Math.pow(2, semitoneDiff / 12);

            const src = this.audioCtx.createBufferSource();
            src.buffer = buf;
            src.playbackRate.setValueAtTime(playbackRate, startTime);

            const gain = this.audioCtx.createGain();
            gain.gain.setValueAtTime(velocity * 0.8, startTime);
            gain.gain.exponentialRampToValueAtTime(0.001, startTime + duration);

            src.connect(gain);
            gain.connect(this.audioCtx.destination);

            src.start(startTime);
            src.stop(startTime + duration + 0.05);

            this.activeNodes.push({ src, gain });
        }

        stopAll() {
            // Cancel active Tone.js voices & scheduled events
            if (this.toneSampler) {
                try {
                    this.toneSampler.releaseAll();
                } catch (e) {}
            }
            if (window.Tone && window.Tone.Transport) {
                try {
                    window.Tone.Transport.stop();
                    window.Tone.Transport.cancel(0);
                } catch (e) {}
            }

            // Stop all active native buffer sources
            this.activeNodes.forEach(node => {
                try {
                    node.src.stop();
                    node.src.disconnect();
                    node.gain.disconnect();
                } catch (e) {}
            });
            this.activeNodes = [];
        }

        /**
         * Sustain Control API
         */
        setSustain(enabled) {
            const wasSustain = this.sustain;
            this.sustain = Boolean(enabled);
            if (wasSustain && !this.sustain) {
                // Immediately release currently ringing sustained voices
                this.stopAll();
            }
            this._notifySustainChange();
            return this.sustain;
        }

        getSustain() {
            return this.sustain;
        }

        toggleSustain() {
            return this.setSustain(!this.sustain);
        }

        onSustainChange(cb) {
            if (typeof cb === 'function') this.sustainListeners.push(cb);
        }

        _notifySustainChange() {
            this.sustainListeners.forEach(cb => {
                try { cb(this.sustain); } catch (e) {}
            });
        }

        dispose() {
            this.stopAll();
            if (this.toneSampler) {
                try {
                    this.toneSampler.dispose();
                    this.toneSampler = null;
                } catch (e) {}
            }
            if (this.audioCtx) {
                try {
                    this.audioCtx.close();
                    this.audioCtx = null;
                } catch (e) {}
            }
            this.nativeBuffers = {};
            this._setState('uninitialized');
        }

        getState() {
            return this.state;
        }

        onStateChange(cb) {
            if (typeof cb === 'function') this.stateListeners.push(cb);
        }

        _setState(newState, error = null) {
            this.state = newState;
            this.stateListeners.forEach(cb => {
                try { cb(newState, error); } catch (e) {}
            });
        }
    }

    // Singleton instance
    const serviceInstance = new PianoPlaybackService();
    global.PianoPlaybackService = serviceInstance;
    global.PianoPlaybackServiceClass = PianoPlaybackService;

})(typeof window !== 'undefined' ? window : global);
