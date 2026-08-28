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
 * - Leaves continuous playback to browser media engine without clock fighting.
 * - Handles end-of-song and error states cleanly.
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

            this._isSeeking = false;
            this._clockUnsub = null;
            this.stateListeners = new Set();

            this._initAudioElement();

            if (this.clock) {
                this.bindClock(this.clock);
            }
        }

        _initAudioElement() {
            if (!this.audioEl) return;

            // Enforce pitch preservation across Chromium / WebKit (macOS WKWebView)
            this._enforcePitchPreservation();

            this.audioEl.addEventListener('loadedmetadata', () => {
                this.duration = this.audioEl.duration || 0;
                if (this.clock) {
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

            this.audioEl.addEventListener('ended', () => {
                if (this.clock && this.clock.state === 'PLAYING') {
                    this.clock.stop();
                }
            });

            this.audioEl.addEventListener('error', (e) => {
                const err = this.audioEl.error;
                const msg = err ? `Audio Error code ${err.code}: ${err.message || 'Failed to decode'}` : 'Audio load error';
                console.error('[SongAudioController]', msg);
                this.state = AudioLoadState.ERROR;
                this.error = msg;
                this._notifyState();
            });
        }

        _enforcePitchPreservation() {
            if (!this.audioEl) return;
            // Standard W3C & Chromium
            if ('preservesPitch' in this.audioEl) {
                this.audioEl.preservesPitch = true;
            }
            // WebKit / Apple WKWebView (macOS / iOS)
            if ('webkitPreservesPitch' in this.audioEl) {
                this.audioEl.webkitPreservesPitch = true;
            }
            // Gecko / Firefox
            if ('mozPreservesPitch' in this.audioEl) {
                this.audioEl.mozPreservesPitch = true;
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

            this._cleanupObjectUrl();
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
                    this.state = AudioLoadState.READY;
                    this._notifyState();
                    resolve(true);
                };

                const onLoadedMetadata = () => {
                    cleanup();
                    this.state = AudioLoadState.READY;
                    this._notifyState();
                    resolve(true);
                };

                const onError = () => {
                    cleanup();
                    resolve(false);
                };

                // 2.5s safety timeout to avoid hanging caller
                timeoutId = setTimeout(() => {
                    cleanup();
                    resolve(true);
                }, 2500);

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
                this.objectUrl = URL.createObjectURL(file);
                return await this.load(this.objectUrl);
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

                // 1. Playback Rate Synchronization & Pitch Preservation
                if (snap.playbackRate !== prevRate) {
                    this._enforcePitchPreservation();
                    this.audioEl.playbackRate = snap.playbackRate;
                    prevRate = snap.playbackRate;
                }

                // 2. Playback State Synchronization
                if (snap.state !== prevState) {
                    if (snap.state === 'PLAYING') {
                        // Align position before starting
                        const diff = Math.abs(this.audioEl.currentTime - snap.currentTime);
                        if (diff > 0.05) {
                            this.audioEl.currentTime = snap.currentTime;
                        }
                        this._enforcePitchPreservation();
                        this.audioEl.play().catch(e => {
                            console.warn('[SongAudioController] Audio play interrupted:', e);
                        });
                    } else if (snap.state === 'PAUSED') {
                        this.audioEl.pause();
                        this.audioEl.currentTime = snap.currentTime;
                    } else if (snap.state === 'STOPPED') {
                        this.audioEl.pause();
                        this.audioEl.currentTime = 0;
                    }
                    prevState = snap.state;
                } else if (snap.state === 'PLAYING') {
                    // Check for seek/jump in clock while playing
                    const expectedElapsed = snap.currentTime - prevTime;
                    const audioElapsed = this.audioEl.currentTime - prevTime;
                    const drift = Math.abs(this.audioEl.currentTime - snap.currentTime);
                    
                    // Only resync if significant seek jump occurred (> 150ms) to avoid fighting browser audio buffer
                    if (drift > 0.15) {
                        this.audioEl.currentTime = snap.currentTime;
                    }
                }
                prevTime = snap.currentTime;
            });
        }

        /**
         * Direct transport operations
         */
        play() {
            if (this.clock) {
                this.clock.play();
                return;
            }
            if (this.audioEl && this.state === AudioLoadState.READY) {
                this._enforcePitchPreservation();
                this.audioEl.play().catch(() => {});
            }
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

        seek(time) {
            if (this.clock) {
                this.clock.seek(time);
                return;
            }
            if (this.audioEl && this.state === AudioLoadState.READY) {
                this.audioEl.currentTime = Math.max(0, Math.min(this.duration, time));
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
