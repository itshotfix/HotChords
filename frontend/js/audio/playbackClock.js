/**
 * playbackClock.js
 * 
 * Central Playback Clock for HotChords.
 * Authoritative, high-resolution monotonic timeline clock that synchronizes:
 * - Uploaded song audio
 * - Original piano chords
 * - Beginner piano chords
 * - Chord highlighting
 * - Lyrics
 * - Piano fingering & hand animation
 * 
 * Architecture:
 * - Pure framework-agnostic JS (zero React dependencies).
 * - Monotonic performance.now() reference with rate scaling.
 * - Exact mathematical continuity: position never jumps on rate changes or pause/resume.
 */

(function(global) {
    'use strict';

    const PlaybackState = Object.freeze({
        STOPPED: 'STOPPED',
        PLAYING: 'PLAYING',
        PAUSED: 'PAUSED'
    });

    const SUPPORTED_RATES = Object.freeze([1.0, 0.75, 0.5]);

    class PlaybackClock {
        constructor(options = {}) {
            this.duration = Math.max(0, options.duration || 0);
            this.playbackRate = 1.0;
            this.state = PlaybackState.STOPPED;

            // Monotonic reference anchors
            this._timelinePosition = 0; // Canonical timeline seconds (T0)
            this._wallClockAnchor = 0;  // Monotonic wall-clock ms at last anchor (t0)
            
            // Injectable time source for deterministic testing
            this._getTime = options.timeProvider || (() => {
                if (typeof performance !== 'undefined' && performance.now) {
                    return performance.now();
                }
                return Date.now();
            });

            this._listeners = new Set();
            this._rafId = null;
            this._boundTick = this._tick.bind(this);
        }

        /**
         * Set the total duration of the song timeline in seconds.
         * @param {number} seconds
         */
        setDuration(seconds) {
            this.duration = Math.max(0, Number(seconds) || 0);
            if (this._timelinePosition > this.duration) {
                this.seek(this.duration);
            }
            this._notify();
        }

        /**
         * Returns the current canonical musical timeline time in seconds.
         */
        getCurrentTime() {
            if (this.state === PlaybackState.PLAYING) {
                const nowMs = this._getTime();
                const elapsedSec = ((nowMs - this._wallClockAnchor) / 1000.0) * this.playbackRate;
                const computed = this._timelinePosition + elapsedSec;
                
                if (this.duration > 0 && computed >= this.duration) {
                    this._timelinePosition = this.duration;
                    this.state = PlaybackState.STOPPED;
                    this._stopTickLoop();
                    return this.duration;
                }
                return Math.max(0, computed);
            }
            return this._timelinePosition;
        }


        get currentTime() {
            return this.getCurrentTime();
        }

        /**
         * Starts or resumes playback.
         */
        play() {
            if (this.state === PlaybackState.PLAYING) return;

            // If at or beyond duration, restart from 0
            if (this.duration > 0 && this._timelinePosition >= this.duration) {
                this._timelinePosition = 0;
            }

            this._wallClockAnchor = this._getTime();
            this.state = PlaybackState.PLAYING;

            this._startTickLoop();
            this._notify();
        }

        /**
         * Pauses playback and freezes current timeline position.
         */
        pause() {
            if (this.state !== PlaybackState.PLAYING) return;

            this._timelinePosition = this.getCurrentTime();
            this._wallClockAnchor = this._getTime();
            this.state = PlaybackState.PAUSED;

            this._stopTickLoop();
            this._notify();
        }

        /**
         * Stops playback and resets position to 0.0 seconds.
         */
        stop() {
            this._timelinePosition = 0;
            this._wallClockAnchor = this._getTime();
            this.state = PlaybackState.STOPPED;

            this._stopTickLoop();
            this._notify();
        }

        /**
         * Cancels previous scheduling, resets position to 0, and starts playback from 0.0s.
         */
        restart() {
            this.stop();
            this.play();
        }

        /**
         * Seeks immediately to a target timeline position in seconds.
         * @param {number} targetSeconds
         */
        seek(targetSeconds) {
            const raw = Number(targetSeconds);
            if (isNaN(raw)) return;

            const clamped = this.duration > 0
                ? Math.max(0, Math.min(this.duration, raw))
                : Math.max(0, raw);

            this._timelinePosition = clamped;
            this._wallClockAnchor = this._getTime();

            // If we reached the end while playing, stop
            if (this.duration > 0 && clamped >= this.duration && this.state === PlaybackState.PLAYING) {
                this.stop();
                return;
            }

            this._notify();
        }

        /**
         * Updates playback rate without jumping current timeline position.
         * @param {number} rate - 1.0, 0.75, or 0.5 (or any positive finite number)
         */
        setPlaybackRate(rate) {
            const numRate = Number(rate);
            if (isNaN(numRate) || numRate <= 0 || !isFinite(numRate)) {
                console.warn(`[PlaybackClock] Invalid playback rate rejected: ${rate}`);
                return false;
            }

            if (this.state === PlaybackState.PLAYING) {
                // Freeze current timeline position at moment of rate switch
                this._timelinePosition = this.getCurrentTime();
                this._wallClockAnchor = this._getTime();
            }

            this.playbackRate = numRate;
            this._notify();
            return true;
        }

        /**
         * Subscribes a listener to clock state updates.
         * @param {Function} listener
         * @returns {Function} Unsubscribe function
         */
        subscribe(listener) {
            if (typeof listener !== 'function') return () => {};
            this._listeners.add(listener);
            // Send initial state snapshot immediately
            listener(this.getSnapshot());
            return () => this.unsubscribe(listener);
        }

        /**
         * Unsubscribes a listener.
         * @param {Function} listener
         */
        unsubscribe(listener) {
            this._listeners.delete(listener);
        }

        /**
         * Returns an immutable snapshot of the current clock state.
         */
        getSnapshot() {
            return {
                currentTime: this.getCurrentTime(),
                duration: this.duration,
                playbackRate: this.playbackRate,
                state: this.state
            };
        }

        _notify() {
            if (this._listeners.size === 0) return;
            const snapshot = this.getSnapshot();
            this._listeners.forEach(fn => {
                try { fn(snapshot); } catch (e) { console.error(e); }
            });
        }

        _startTickLoop() {
            if (this._rafId) return;
            if (typeof requestAnimationFrame !== 'undefined') {
                this._rafId = requestAnimationFrame(this._boundTick);
            }
        }

        _stopTickLoop() {
            if (this._rafId && typeof cancelAnimationFrame !== 'undefined') {
                cancelAnimationFrame(this._rafId);
            }
            this._rafId = null;
        }

        _tick() {
            if (this.state !== PlaybackState.PLAYING) {
                this._stopTickLoop();
                return;
            }

            // Check if reached end of duration
            if (this.duration > 0 && this.getCurrentTime() >= this.duration) {
                this._timelinePosition = this.duration;
                this.stop();
                return;
            }

            this._notify();

            if (typeof requestAnimationFrame !== 'undefined') {
                this._rafId = requestAnimationFrame(this._boundTick);
            }
        }
    }

    // Export Constants, Class & Singleton Instance
    global.PlaybackState = PlaybackState;
    global.SUPPORTED_RATES = SUPPORTED_RATES;
    global.PlaybackClockClass = PlaybackClock;
    global.PlaybackClock = new PlaybackClock();

})(typeof window !== 'undefined' ? window : global);
