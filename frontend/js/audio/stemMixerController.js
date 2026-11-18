/**
 * stemMixerController.js
 *
 * HotChords Unified MIX Engine — Sample-Accurate Web Audio Synchronisation
 * for Piano Arrangement, Original Song, Vocals, and Backing Track.
 *
 * Architecture:
 * - PlaybackClock remains the sole authoritative timeline time authority.
 * - Uses a shared Web Audio AudioContext (reusing PianoPlaybackService.audioCtx
 *   when available) with one GainNode + AudioBufferSourceNode per audio channel
 *   ('original', 'vocals', 'instrumental', 'bass', 'drums') scheduled from a
 *   common AudioContext.currentTime reference.
 * - Handles differing sample rates (via decodeAudioData) and differing buffer
 *   durations safely, with automatic AbortController + source node cleanup.
 * - Falls back gracefully to SongAudioController / HTMLAudioElement if Web Audio
 *   decoding is unavailable or fails.
 */

(function(global) {
    'use strict';

    const DEFAULT_CHANNELS = ['piano', 'original', 'vocals', 'instrumental', 'bass', 'drums'];
    const AUDIO_BUFFER_CHANNELS = ['original', 'vocals', 'instrumental', 'bass', 'drums'];

    class StemMixerController {
        constructor(options = {}) {
            this.clock = options.clock || global.PlaybackClock || null;
            this.adapter = options.adapter || global.StudioTimelineAdapter || null;
            this.pianoService = options.pianoService || global.PianoPlaybackService || null;
            this._createAudioContext = options.audioContextFactory || (() => {
                const Ctx = global.AudioContext || global.webkitAudioContext;
                return Ctx ? new Ctx() : null;
            });

            this.pitchShift = 0;
            this.pitchPreservingEnabled = false;
            this._soundTouchReady = false;
            this._soundTouchNodes = {};
            this.channels = {};
            this.audioCtx = null;
            this.gainNodes = {};
            this.audioBuffers = {};
            this.activeSources = {};
            this.channelLoadErrors = {};
            this.stemAudios = {}; // HTMLAudioElement fallback only when Web Audio buffer unavailable

            this._triggeredNoteIds = new Set();
            this._lastClockTime = 0;
            this._lastRate = 1.0;
            this._isPlayingBuffers = false;
            this._lastSyncAnchor = null;
            this._loadGeneration = 0;
            this._abortControllers = [];
            this._clockUnsub = null;
            this.listeners = new Set();

            this._initDefaultChannels();
            if (this.clock) {
                this.bindClock(this.clock);
            }
        }

        _initDefaultChannels() {
            DEFAULT_CHANNELS.forEach(ch => {
                this.channels[ch] = {
                    name: ch,
                    volume: ch === 'piano' ? 0.90 : (ch === 'vocals' || ch === 'instrumental' ? 0.85 : 0.0),
                    muted: ch !== 'piano',
                    solo: false,
                    available: ch === 'piano' || ch === 'original',
                    loading: false,
                    decoded: false
                };
            });
        }

        _ensureAudioContext() {
            if (this.audioCtx) return this.audioCtx;
            if (this.pianoService && this.pianoService.audioCtx) {
                this.audioCtx = this.pianoService.audioCtx;
            } else {
                this.audioCtx = this._createAudioContext();
            }
            if (this.audioCtx) {
                AUDIO_BUFFER_CHANNELS.forEach(ch => this._ensureGainNode(ch));
            }
            return this.audioCtx;
        }

        _ensureGainNode(channelName) {
            if (!this.audioCtx || typeof this.audioCtx.createGain !== 'function') return null;
            if (!this.gainNodes[channelName]) {
                const g = this.audioCtx.createGain();
                g.gain.value = this._targetGainFor(channelName);
                if (typeof g.connect === 'function' && this.audioCtx.destination) {
                    g.connect(this.audioCtx.destination);
                }
                this.gainNodes[channelName] = g;
            }
            return this.gainNodes[channelName];
        }

        _targetGainFor(channelName) {
            return this._isChannelAudible(channelName) ? this.channels[channelName].volume : 0;
        }

        _applyGain(channelName) {
            const g = this.gainNodes[channelName];
            const target = this._targetGainFor(channelName);
            if (g && g.gain) {
                const now = this.audioCtx ? this.audioCtx.currentTime : 0;
                if (typeof g.gain.setTargetAtTime === 'function') {
                    g.gain.setTargetAtTime(target, now, 0.015);
                } else {
                    g.gain.value = target;
                }
            }
            if (this.stemAudios[channelName]) {
                const audible = this._isChannelAudible(channelName);
                this.stemAudios[channelName].volume = target;
                this.stemAudios[channelName].muted = !audible;
            }
        }

        _cancelPendingLoads() {
            this._abortControllers.forEach(ac => {
                try { ac.abort(); } catch (e) {}
            });
            this._abortControllers = [];
        }

        _stopAllBufferSources() {
            Object.entries(this.activeSources).forEach(([ch, src]) => {
                if (!src) return;
                try { src.stop(0); } catch (e) {}
                try { src.disconnect(); } catch (e) {}
                delete this.activeSources[ch];
            });
            Object.entries(this._soundTouchNodes || {}).forEach(([ch, node]) => {
                if (!node) return;
                try { node.disconnect(); } catch (e) {}
                delete this._soundTouchNodes[ch];
            });
            this._isPlayingBuffers = false;
        }

        /**
         * Loads stems & optional original audio source into shared Web Audio buffers.
         * @param {Object} stemsMap - e.g. { original, vocals, instrumental, bass, drums }
         */
        loadStems(stemsMap = {}) {
            this._loadGeneration += 1;
            const gen = this._loadGeneration;

            this._cancelPendingLoads();
            this._stopAllBufferSources();

            Object.values(this.stemAudios).forEach(a => {
                try { a.pause(); a.src = ''; } catch (e) {}
            });
            this.stemAudios = {};
            this.audioBuffers = {};
            this.channelLoadErrors = {};

            AUDIO_BUFFER_CHANNELS.forEach(ch => {
                this.channels[ch].decoded = false;
                this.channels[ch].loading = false;
                if (ch !== 'original') {
                    this.channels[ch].available = false;
                }
            });

            const entries = AUDIO_BUFFER_CHANNELS
                .map(ch => [ch, stemsMap && stemsMap[ch]])
                .filter(([, src]) => Boolean(src));

            if (entries.length === 0) {
                this._applyOriginalAudioState();
                this._notify();
                return Promise.resolve();
            }

            const ctx = this._ensureAudioContext();
            if (ctx && ctx.audioWorklet && !this._soundTouchReady && !this._soundTouchInitPromise) {
                this._soundTouchInitPromise = this.enablePitchPreservingWorklet().catch(() => false);
            }
            const loadPromises = entries.map(async ([ch, src]) => {
                this.channels[ch].available = true;
                this.channels[ch].loading = true;
                try {
                    const buffer = await this._decodeSourceToBuffer(src, ctx, gen);
                    if (gen !== this._loadGeneration) return;
                    if (buffer) {
                        this.audioBuffers[ch] = buffer;
                        this.channels[ch].decoded = true;
                        this.channels[ch].loading = false;
                        this._ensureGainNode(ch);
                        this._applyGain(ch);
                        if (ch === 'original') {
                            this._applyOriginalAudioState();
                        }
                        // If clock is currently playing, join lockstep immediately
                        if (this.clock && this.clock.state === 'PLAYING') {
                            this._startBufferSourcesAt(this.clock.currentTime, this.clock.playbackRate || 1.0);
                        }
                    } else {
                        this.channels[ch].loading = false;
                        this._attachFallbackAudio(ch, src);
                    }
                } catch (err) {
                    if (gen !== this._loadGeneration) return;
                    this.channels[ch].loading = false;
                    this.channelLoadErrors[ch] = err && err.message ? err.message : 'Audio decode failed';
                    if (ch !== 'original' && typeof src === 'string') {
                        this._attachFallbackAudio(ch, src);
                    }
                } finally {
                    if (gen === this._loadGeneration) {
                        this._notify();
                    }
                }
            });

            this._applyOriginalAudioState();
            this._notify();
            return Promise.all(loadPromises);
        }

        async _decodeSourceToBuffer(src, ctx, gen) {
            if (!ctx || typeof ctx.decodeAudioData !== 'function') return null;

            let arrayBuffer = null;
            if (typeof File !== 'undefined' && src instanceof File && typeof src.arrayBuffer === 'function') {
                arrayBuffer = await src.arrayBuffer();
            } else if (typeof Blob !== 'undefined' && src instanceof Blob && typeof src.arrayBuffer === 'function') {
                arrayBuffer = await src.arrayBuffer();
            } else if (typeof src === 'string' && typeof fetch === 'function') {
                const ac = typeof AbortController !== 'undefined' ? new AbortController() : null;
                if (ac) this._abortControllers.push(ac);
                const resp = await fetch(src, ac ? { signal: ac.signal } : undefined);
                if (!resp.ok) {
                    throw new Error(`HTTP ${resp.status} loading stem`);
                }
                arrayBuffer = await resp.arrayBuffer();
            } else {
                return null;
            }

            if (gen !== this._loadGeneration) return null;
            return ctx.decodeAudioData(arrayBuffer);
        }

        _attachFallbackAudio(stemKey, url) {
            if (stemKey === 'original' || typeof url !== 'string' || typeof Audio === 'undefined') return;
            const audio = new Audio(url);
            audio.preload = 'auto';
            if ('preservesPitch' in audio) audio.preservesPitch = true;
            if ('webkitPreservesPitch' in audio) audio.webkitPreservesPitch = true;
            this.stemAudios[stemKey] = audio;
        }

        bindClock(clock) {
            if (this._clockUnsub) {
                this._clockUnsub();
                this._clockUnsub = null;
            }
            this.clock = clock;
            if (!clock) return;

            let prevState = clock.state;
            this._lastRate = clock.playbackRate || 1.0;

            this._clockUnsub = clock.subscribe(snap => {
                const t = snap.currentTime;
                const rate = snap.playbackRate || 1.0;
                const timeJumped = Math.abs(t - this._lastClockTime) > 0.15 || t < this._lastClockTime;
                const rateChanged = Math.abs(rate - this._lastRate) > 0.001;

                if (timeJumped || snap.state !== 'PLAYING') {
                    this._triggeredNoteIds.clear();
                }

                if (snap.state === 'PLAYING') {
                    this._scheduleArrangementNotes(this._lastClockTime, t, rate);
                    if (prevState !== 'PLAYING' || timeJumped || rateChanged || !this._isPlayingBuffers) {
                        this._startBufferSourcesAt(t, rate);
                    }
                    this._syncFallbackStemAudios(t, rate, true);
                } else if (prevState === 'PLAYING' && snap.state !== 'PLAYING') {
                    this._stopAllBufferSources();
                    this._syncFallbackStemAudios(t, rate, false);
                }

                prevState = snap.state;
                this._lastClockTime = t;
                this._lastRate = rate;
            });
        }

        _startBufferSourcesAt(timelineSec, playbackRate = 1.0) {
            const ctx = this._ensureAudioContext();
            if (!ctx || typeof ctx.createBufferSource !== 'function') return;

            if (ctx.state === 'suspended' && typeof ctx.resume === 'function') {
                ctx.resume().catch(() => {});
            }

            this._stopAllBufferSources();

            const clampedRate = Math.max(0.25, Math.min(1.5, Number(playbackRate) || 1.0));
            const startWhen = (ctx.currentTime || 0) + 0.005;
            const safeOffset = Math.max(0, Number(timelineSec) || 0);
            let startedAny = false;

            Object.entries(this.audioBuffers).forEach(([ch, buffer]) => {
                if (!buffer || safeOffset >= buffer.duration) return;
                const gainNode = this._ensureGainNode(ch);
                if (!gainNode) return;

                const src = ctx.createBufferSource();
                src.buffer = buffer;
                if (src.playbackRate) {
                    src.playbackRate.value = clampedRate;
                }

                // Route through SoundTouch pitch-preserving AudioWorklet when enabled and ready
                const useWorklet = (
                    this.pitchPreservingEnabled &&
                    this._soundTouchReady &&
                    typeof global.AudioWorkletNode === 'function' &&
                    (Math.abs(clampedRate - 1.0) > 0.003 || this.pitchShift !== 0)
                );
                if (useWorklet) {
                    try {
                        const stNode = new global.AudioWorkletNode(ctx, 'soundtouch-processor');
                        const pitchFactor = (1.0 / clampedRate) * Math.pow(2, this.pitchShift / 12);
                        const param = stNode.parameters && stNode.parameters.get('pitchFactor');
                        if (param) {
                            param.setValueAtTime(Math.max(0.5, Math.min(2.5, pitchFactor)), startWhen);
                        }
                        src.connect(stNode);
                        stNode.connect(gainNode);
                        this._soundTouchNodes[ch] = stNode;
                    } catch (e) {
                        src.connect(gainNode);
                    }
                } else {
                    src.connect(gainNode);
                }

                this._applyGain(ch);
                src.start(startWhen, safeOffset);
                this.activeSources[ch] = src;
                startedAny = true;
            });

            this._isPlayingBuffers = startedAny;
            if (startedAny) {
                this._lastSyncAnchor = {
                    audioCtxStartTime: startWhen,
                    timelineOffset: safeOffset,
                    playbackRate: clampedRate,
                    channels: Object.keys(this.activeSources)
                };
            }
            this._applyOriginalAudioState();
        }

        _isChannelAudible(chName) {
            const ch = this.channels[chName];
            if (!ch || !ch.available) return false;
            const anySolo = Object.values(this.channels).some(c => c.solo);
            if (anySolo) return ch.solo && !ch.muted && ch.volume > 0.005;
            return !ch.muted && ch.volume > 0.005;
        }

        _applyOriginalAudioState() {
            const songCtrl = global.SongAudioController;
            if (!songCtrl) return;
            // If Web Audio buffer is decoded for 'original', mute HTMLAudioElement fallback to avoid double audio
            const hasWebAudioOriginal = Boolean(this.audioBuffers.original);
            const origAudible = !hasWebAudioOriginal && this._isChannelAudible('original');
            songCtrl.setEnabled(origAudible);
            if (songCtrl.audioEl) {
                songCtrl.audioEl.volume = origAudible ? this.channels.original.volume : 0;
                songCtrl.audioEl.muted = !origAudible;
            }
        }

        _scheduleArrangementNotes(prevTime, curTime, playbackRate) {
            if (!this._isChannelAudible('piano') || !this.adapter || !this.pianoService) return;

            const windowStart = Math.min(prevTime, curTime);
            const windowEnd = Math.max(prevTime, curTime) + 0.025;
            const notes = this.adapter.getNotes();
            const pianoVol = this.channels.piano.volume;

            for (let i = 0; i < notes.length; i++) {
                const n = notes[i];
                if (n.start >= windowStart - 0.01 && n.start <= windowEnd) {
                    if (!this._triggeredNoteIds.has(n.id)) {
                        this._triggeredNoteIds.add(n.id);
                        const normVel = Math.max(0.05, Math.min(1.0, (n.velocity / 127) * pianoVol));
                        const scaledDur = Math.max(0.08, n.duration / Math.max(0.25, playbackRate));
                        this.pianoService.playNote(n.midi, normVel, scaledDur);
                    }
                }
            }
        }

        _syncFallbackStemAudios(currentTime, playbackRate, isPlaying) {
            this._applyOriginalAudioState();

            Object.entries(this.stemAudios).forEach(([stemKey, audio]) => {
                if (!audio || this.audioBuffers[stemKey]) return;
                const audible = isPlaying && this._isChannelAudible(stemKey);
                const targetVol = audible ? this.channels[stemKey].volume : 0;
                audio.volume = audio.volume + (targetVol - audio.volume) * 0.35;
                audio.muted = !audible;
                audio.playbackRate = playbackRate;

                if (audible) {
                    if (Math.abs(audio.currentTime - currentTime) > 0.10) {
                        try { audio.currentTime = currentTime; } catch (e) {}
                    }
                    if (audio.paused) {
                        audio.play().catch(() => {});
                    }
                } else if (!audio.paused) {
                    audio.pause();
                }
            });
        }

        /**
         * Registers an optional SoundTouch AudioWorklet processor for pitch-preserving
         * speed changes (0.25x-1.5x) while keeping PlaybackClock as sole time authority.
         */
        async enablePitchPreservingWorklet(workletUrl = '/js/audio/soundtouch-processor.js') {
            const ctx = this._ensureAudioContext();
            if (!ctx || !ctx.audioWorklet || typeof ctx.audioWorklet.addModule !== 'function') {
                this._soundTouchReady = false;
                return false;
            }
            try {
                await ctx.audioWorklet.addModule(workletUrl);
                this._soundTouchReady = true;
                this.pitchPreservingEnabled = true;
                return true;
            } catch (e) {
                this._soundTouchReady = false;
                return false;
            }
        }

        /**
         * Sets channel volume in range [0.0, 1.0] (or percentage [0..100] if > 1.0).
         */
        setChannelVolume(channelName, volume) {
            const ch = this.channels[channelName];
            if (!ch) return 0;
            const raw = Number(volume) || 0;
            const norm = raw > 1.0 ? Math.max(0, Math.min(1, raw / 100)) : Math.max(0, Math.min(1, raw));
            ch.volume = Math.round(norm * 100) / 100;
            if (ch.volume > 0.005 && ch.muted) {
                ch.muted = false;
            } else if (ch.volume <= 0.005) {
                ch.muted = true;
            }

            if (channelName === 'original') {
                this._applyGain('original');
                this._applyOriginalAudioState();
            } else if (channelName === 'piano' && global.UnifiedPianoPlaybackController) {
                global.UnifiedPianoPlaybackController.setEnabled(this._isChannelAudible('piano'));
            } else {
                this._applyGain(channelName);
            }
            this._notify();
            return ch.volume;
        }

        getChannelPercent(channelName) {
            const ch = this.channels[channelName];
            if (!ch || ch.muted) return 0;
            return Math.round(ch.volume * 100);
        }

        setChannelMute(channelName, muted) {
            const ch = this.channels[channelName];
            if (!ch) return false;
            ch.muted = Boolean(muted);
            if (!ch.muted && ch.volume < 0.05) {
                ch.volume = 0.75;
            }
            if (channelName === 'original') {
                this._applyGain('original');
                this._applyOriginalAudioState();
            } else if (channelName === 'piano' && global.UnifiedPianoPlaybackController) {
                global.UnifiedPianoPlaybackController.setEnabled(this._isChannelAudible('piano'));
            } else {
                this._applyGain(channelName);
            }
            this._notify();
            return ch.muted;
        }

        toggleChannelMute(channelName) {
            const ch = this.channels[channelName];
            if (!ch) return false;
            return this.setChannelMute(channelName, !ch.muted);
        }

        setChannelSolo(channelName, solo) {
            if (!this.channels[channelName]) return;
            this.channels[channelName].solo = Boolean(solo);
            AUDIO_BUFFER_CHANNELS.forEach(ch => this._applyGain(ch));
            this._applyOriginalAudioState();
            this._notify();
        }

        setPitchShift(semitones) {
            const clamped = Math.max(-12, Math.min(12, Math.round(Number(semitones) || 0)));
            this.pitchShift = clamped;
            if (this.adapter) {
                this.adapter.setPitchShift(clamped);
            }
            this._triggeredNoteIds.clear();
            this._notify();
            return this.pitchShift;
        }

        dispose() {
            this._loadGeneration += 1;
            this._cancelPendingLoads();
            this._stopAllBufferSources();
            if (this._clockUnsub) {
                this._clockUnsub();
                this._clockUnsub = null;
            }
            Object.values(this.gainNodes).forEach(g => {
                try { g.disconnect(); } catch (e) {}
            });
            this.gainNodes = {};
            this.audioBuffers = {};
            Object.values(this.stemAudios).forEach(a => {
                try { a.pause(); a.src = ''; } catch (e) {}
            });
            this.stemAudios = {};
        }

        subscribe(fn) {
            if (typeof fn === 'function') {
                this.listeners.add(fn);
                return () => this.listeners.delete(fn);
            }
            return () => {};
        }

        _notify() {
            const state = this.getState();
            this.listeners.forEach(fn => {
                try { fn(state); } catch (e) {}
            });
        }

        getState() {
            return {
                pitchShift: this.pitchShift,
                isPlayingBuffers: this._isPlayingBuffers,
                syncAnchor: this._lastSyncAnchor,
                loadErrors: Object.assign({}, this.channelLoadErrors),
                channels: JSON.parse(JSON.stringify(this.channels))
            };
        }
    }

    const instance = new StemMixerController();
    global.StemMixerController = instance;
    global.StemMixerControllerClass = StemMixerController;

    if (typeof module !== 'undefined' && module.exports) {
        module.exports = { StemMixerController, instance };
    }
})(typeof window !== 'undefined' ? window : global);
