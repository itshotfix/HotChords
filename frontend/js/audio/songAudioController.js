/**
 * songAudioController.js
 *
 * Song Audio Controller for HotChords.
 * Bridges uploaded/local song audio tracks with the central PlaybackClock.
 *
 * Architecture:
 * PlaybackClock -> SongAudioController -> HTMLAudioElement (preservesPitch = true) -> Audio Output
 *
 * Responsibilities:
 * - Loads offline local audio files (URLs or File / Blob objects).
 * - Enforces hardware/OS-level pitch preservation (preservesPitch / webkitPreservesPitch).
 * - Synchronizes with PlaybackClock lifecycle (play, pause, stop, seek, rate change).
 * - Avoids clock fighting: reconciles drift smoothly without continuous per-frame seeks.
 * - Handles play() promises, error states, and end-of-track cleanly.
 */

(function(global) {
    'use strict';

    const AudioLoadState = Object.freeze({
        UNLOADED: 'UNLOADED',
        LOADING: 'LOADING',
        READY: 'READY',
        ERROR: 'ERROR'
    });

    class SongAudioController {
        constructor(options = {}) {
            this.clock = options.clock || global.PlaybackClock || null;
            this.audioEl = (typeof Audio !== 'undefined') ? new Audio() : null;
            this.state = AudioLoadState.UNLOADED;
            this.error = null;
            this.objectUrl = null;
            this.duration = 0;
            this.enabled = false;

            this._isSeeking = false;
            this._isPlayingMedia = false;
            this._lastResyncTime = 0;
            this._clockUnsub = null;
            this.stateListeners = new Set();

            this._initAudioElement();

            if (this.clock) {
                this.bindClock(this.clock);
            }
        }

        _initAudioElement() {
            if (!this.audioEl) return;

            this.audioEl.volume = 1.0;
            this.audioEl.muted = false;

            // Enforce pitch preservation across Chromium / WebKit (macOS WKWebView)
            this._enforcePitchPreservation();

            this.audioEl.addEventListener('loadedmetadata', () => {
                this.duration = this.audioEl.duration || 0;
                if (this.state === AudioLoadState.LOADING) {
                    this.state = AudioLoadState.READY;
                    this.error = null;
                    this._notifyState();
                }
                if (this.clock && (!this.clock.duration || this.clock.duration === 0)) {
                    this.clock.setDuration(this.duration);
                }
            });

            this.audioEl.addEventListener('canplay', () => {
                if (this.state === AudioLoadState.LOADING) {
                    this.state = AudioLoadState.READY;
                    this.error = null;
                    this._notifyState();
                }
            });

            this.audioEl.addEventListener('play', () => {
                this._isPlayingMedia = true;
            });

            this.audioEl.addEventListener('playing', () => {
                this._isPlayingMedia = true;
            });

            this.audioEl.addEventListener('pause', () => {
                this._isPlayingMedia = false;
            });

            this.audioEl.addEventListener('ended', () => {
                this._isPlayingMedia = false;
                if (this.clock) {
                    if (this.clock.isLooping()) {
                        // Let loop boundary control transition
                        const region = this.clock.getLoopRegion();
                        this.clock.seek(region.start || 0);
                    } else if (this.clock.state === 'PLAYING') {
                        this.clock.stop();
                    }
                }
            });

            this.audioEl.addEventListener('error', () => {
                this._isPlayingMedia = false;
                const err = this.audioEl.error;
                const msg = err ? `Audio Error code ${err.code}: ${err.message || 'Failed to decode audio file'}` : 'Audio load error';
                console.error('[SongAudioController]', msg);
                this.state = AudioLoadState.ERROR;
                this.error = msg;
                this._notifyState();
            });
        }

        _enforcePitchPreservation() {
            if (!this.audioEl) return;
            if ('preservesPitch' in this.audioEl) {
                this.audioEl.preservesPitch = true;
            }
            if ('webkitPreservesPitch' in this.audioEl) {
                this.audioEl.webkitPreservesPitch = true;
            }
            if ('mozPreservesPitch' in this.audioEl) {
                this.audioEl.mozPreservesPitch = true;
            }
            if (this.audioEl.volume !== undefined && this.audioEl.volume !== 1.0) {
                this.audioEl.volume = 1.0;
            }
            if (this.audioEl.muted) {
                this.audioEl.muted = false;
            }
        }

        /**
         * Loads an audio file by URL or local path.
         * @param {string} url
         */
        async load(url) {
            if (!url || typeof url !== 'string') {
                this.state = AudioLoadState.ERROR;
                this.error = 'Invalid audio URL provided.';
                this._notifyState();
                return false;
            }

            if (this.objectUrl && this.objectUrl !== url) {
                this._cleanupObjectUrl();
            }
            this.state = AudioLoadState.LOADING;
            this.error = null;
            this._notifyState();

            return new Promise((resolve) => {
                if (!this.audioEl) {
                    this.state = AudioLoadState.ERROR;
                    this.error = 'HTMLAudioElement not available in environment';
                    this._notifyState();
                    resolve(false);
                    return;
                }

                this.audioEl.src = url;
                this.audioEl.load();
                this._enforcePitchPreservation();

                if (this.audioEl.readyState >= 2) {
                    this.duration = this.audioEl.duration || 0;
                    this.state = AudioLoadState.READY;
                    this._notifyState();
                    resolve(true);
                    return;
                }

                let timeoutId = null;
                const cleanup = () => {
                    if (timeoutId) clearTimeout(timeoutId);
                    this.audioEl.removeEventListener('canplay', onCanPlay);
                    this.audioEl.removeEventListener('loadedmetadata', onLoadedMetadata);
                    this.audioEl.removeEventListener('error', onError);
                };

                const onCanPlay = () => {
                    cleanup();
                    this.duration = this.audioEl.duration || 0;
                    this.state = AudioLoadState.READY;
                    this._notifyState();
                    resolve(true);
                };

                const onLoadedMetadata = () => {
                    cleanup();
                    this.duration = this.audioEl.duration || 0;
                    this.state = AudioLoadState.READY;
                    this._notifyState();
                    resolve(true);
                };

                const onError = () => {
                    cleanup();
                    resolve(false);
                };

                timeoutId = setTimeout(() => {
                    cleanup();
                    if (this.audioEl.readyState >= 1) {
                        this.duration = this.audioEl.duration || 0;
                        this.state = AudioLoadState.READY;
                        this._notifyState();
                        resolve(true);
                    } else {
                        resolve(false);
                    }
                }, 3000);

                this.audioEl.addEventListener('canplay', onCanPlay);
                this.audioEl.addEventListener('loadedmetadata', onLoadedMetadata);
                this.audioEl.addEventListener('error', onError);
            });
        }

        /**
         * Loads an offline File or Blob from user upload.
         * @param {File|Blob} file
         */
        async loadFile(file) {
            if (!file || !(file instanceof Blob)) {
                this.state = AudioLoadState.ERROR;
                this.error = 'Invalid File/Blob provided.';
                this._notifyState();
                return false;
            }

            this._cleanupObjectUrl();
            if (typeof URL !== 'undefined' && URL.createObjectURL) {
                const newUrl = URL.createObjectURL(file);
                this.objectUrl = newUrl;
                return await this.load(newUrl);
            }
            return false;
        }

        /**
         * Binds this controller to follow a PlaybackClock instance.
         * @param {PlaybackClock} clock
         */
        bindClock(clock) {
            if (this._clockUnsub) {
                this._clockUnsub();
                this._clockUnsub = null;
            }

            this.clock = clock;
            if (!clock) return;

            let prevRate = clock.playbackRate;
            let prevState = clock.state;
            let prevTime = clock.currentTime;

            this._clockUnsub = clock.subscribe((snap) => {
                if (!this.audioEl || this.state !== AudioLoadState.READY) return;

                // When disabled, keep audio element paused and silent
                if (!this.enabled) {
                    if (!this.audioEl.paused) {
                        this.audioEl.pause();
                    }
                    prevState = snap.state;
                    prevRate = snap.playbackRate;
                    prevTime = snap.currentTime;
                    return;
                }

                // 1. Playback Rate Synchronization & Pitch Preservation
                if (snap.playbackRate !== prevRate) {
                    this._enforcePitchPreservation();
                    this.audioEl.playbackRate = snap.playbackRate;
                    prevRate = snap.playbackRate;
                }

                // 2. Playback State Synchronization
                if (snap.state !== prevState) {
                    if (snap.state === 'PLAYING') {
                        const diff = Math.abs(this.audioEl.currentTime - snap.currentTime);
                        if (diff > 0.08) {
                            this.audioEl.currentTime = snap.currentTime;
                        }
                        this._enforcePitchPreservation();
                        this.audioEl.playbackRate = snap.playbackRate;
                        this.audioEl.play().catch(e => {
                            console.warn('[SongAudioController] Play interrupted:', e);
                        });
                    } else if (snap.state === 'PAUSED') {
                        this.audioEl.pause();
                        this.audioEl.currentTime = snap.currentTime;
                    } else if (snap.state === 'STOPPED') {
                        this.audioEl.pause();
                        this.audioEl.currentTime = snap.currentTime;
                    }
                    prevState = snap.state;
                } else if (snap.state === 'PLAYING') {
                    // 3. Smooth Reconciliation during continuous playback
                    // Avoid per-frame seeks: only reconcile if large seek jump occurs (> 350ms)
                    const now = (typeof performance !== 'undefined') ? performance.now() : Date.now();
                    const drift = Math.abs(this.audioEl.currentTime - snap.currentTime);
                    const timeSinceResync = now - this._lastResyncTime;

                    if (drift > 0.35 && timeSinceResync > 500) {
                        this._lastResyncTime = now;
                        this.audioEl.currentTime = snap.currentTime;
                    }

                    // If clock is playing but audio got paused unexpectedly (and not seeking)
                    if (this.audioEl.paused && !this.audioEl.ended && this.enabled) {
                        this.audioEl.play().catch(() => {});
                    }
                }
                prevTime = snap.currentTime;
            });
        }

        /**
         * Enables or disables audio output for this controller.
         * @param {boolean} enabled
         */
        setEnabled(enabled) {
            const isEn = Boolean(enabled);
            if (this.enabled === isEn) return;
            this.enabled = isEn;

            if (!this.enabled) {
                if (this.audioEl && !this.audioEl.paused) {
                    this.audioEl.pause();
                }
            } else if (this.clock && this.clock.state === 'PLAYING' && this.state === AudioLoadState.READY) {
                if (this.audioEl) {
                    const diff = Math.abs(this.audioEl.currentTime - this.clock.currentTime);
                    if (diff > 0.08) {
                        this.audioEl.currentTime = this.clock.currentTime;
                    }
                    this._enforcePitchPreservation();
                    this.audioEl.playbackRate = this.clock.playbackRate || 1.0;
                    this.audioEl.play().catch(e => {
                        console.warn('[SongAudioController] Play enable failed:', e);
                    });
                }
            }
        }

        /**
         * Direct transport operations
         */
        async play() {
            if (!this.enabled) return false;
            if (this.clock) {
                this.clock.play();
                return true;
            }
            if (this.audioEl && this.state === AudioLoadState.READY) {
                this._enforcePitchPreservation();
                try {
                    await this.audioEl.play();
                    return true;
                } catch (err) {
                    console.warn('[SongAudioController] Direct play failed:', err);
                    return false;
                }
            }
            return false;
        }

        pause() {
            if (this.clock) {
                this.clock.pause();
                return;
            }
            if (this.audioEl) {
                this.audioEl.pause();
            }
        }

        stop() {
            if (this.clock) {
                this.clock.stop();
                return;
            }
            if (this.audioEl) {
                this.audioEl.pause();
                this.audioEl.currentTime = 0;
            }
        }

        restart() {
            if (this.clock) {
                this.clock.restart();
                return;
            }
            if (this.audioEl) {
                this.audioEl.pause();
                this.audioEl.currentTime = 0;
            }
        }

        seek(time) {
            const target = Math.max(0, Number(time) || 0);
            if (this.clock) {
                this.clock.seek(target);
                return;
            }
            if (this.audioEl && this.state === AudioLoadState.READY) {
                this.audioEl.currentTime = Math.min(this.duration, target);
            }
        }

        setPlaybackRate(rate) {
            if (this.clock) {
                return this.clock.setPlaybackRate(rate);
            }
            if (this.audioEl) {
                this._enforcePitchPreservation();
                this.audioEl.playbackRate = Number(rate) || 1.0;
                return true;
            }
            return false;
        }

        getCurrentTime() {
            if (this.clock) {
                return this.clock.getCurrentTime();
            }
            return this.audioEl ? this.audioEl.currentTime : 0;
        }

        getDuration() {
            return this.duration;
        }

        getState() {
            return this.state;
        }

        getDiagnostics() {
            return {
                state: this.state,
                enabled: this.enabled,
                error: this.error,
                duration: this.duration,
                currentTime: this.audioEl ? this.audioEl.currentTime : 0,
                paused: this.audioEl ? this.audioEl.paused : true,
                muted: this.audioEl ? this.audioEl.muted : false,
                readyState: this.audioEl ? this.audioEl.readyState : 0,
                networkState: this.audioEl ? this.audioEl.networkState : 0,
                src: this.audioEl ? (this.audioEl.currentSrc || this.audioEl.src) : null
            };
        }

        onStateChange(listener) {
            if (typeof listener === 'function') {
                this.stateListeners.add(listener);
                listener(this.state, this.error);
                return () => this.stateListeners.delete(listener);
            }
            return () => {};
        }

        _notifyState() {
            this.stateListeners.forEach(fn => {
                try { fn(this.state, this.error); } catch (e) {}
            });
        }

        _cleanupObjectUrl() {
            if (this.objectUrl && typeof URL !== 'undefined' && URL.revokeObjectURL) {
                URL.revokeObjectURL(this.objectUrl);
                this.objectUrl = null;
            }
        }

        dispose() {
            this.stop();
            if (this._clockUnsub) {
                this._clockUnsub();
                this._clockUnsub = null;
            }
            this._cleanupObjectUrl();
            if (this.audioEl) {
                this.audioEl.src = '';
            }
            this.state = AudioLoadState.UNLOADED;
            this._notifyState();
        }
    }

    // Export Constants, Class & Singleton Instance
    global.AudioLoadState = AudioLoadState;
    global.SongAudioControllerClass = SongAudioController;
    global.SongAudioController = new SongAudioController();

})(typeof window !== 'undefined' ? window : global);
