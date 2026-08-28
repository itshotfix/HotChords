/**
 * unifiedPianoPlaybackController.js
 * 
 * Unified Piano Playback Controller for HotChords.
 * Single public orchestration interface for controlling piano playback across modes.
 * 
 * Architecture:
 *                     SongTimeline
 *                          │
 *               ┌──────────┴──────────┐
 *               ↓                     ↓
 *        Original Chords       Beginner Chords
 *               ↓                     ↓
 *        Original Controller   Beginner Controller
 *               └──────────┬──────────┘
 *                          ↓
 *             UnifiedPianoPlaybackController
 *                          ↓
 *               PianoPlaybackService
 *                          ↓
 *                     Tone.Sampler
 * 
 * Supported Modes:
 * - ORIGINAL_CHORDS
 * - BEGINNER_CHORDS
 */

(function(global) {
    'use strict';

    const PianoPlaybackMode = Object.freeze({
        ORIGINAL_CHORDS: 'ORIGINAL_CHORDS',
        BEGINNER_CHORDS: 'BEGINNER_CHORDS'
    });

    class UnifiedPianoPlaybackController {
        constructor(options = {}) {
            this.service = options.playbackService || global.PianoPlaybackService;
            this.originalController = options.originalController || global.OriginalChordPlaybackController || new (global.OriginalChordPlaybackControllerClass || Object)(this.service);
            this.beginnerController = options.beginnerController || global.BeginnerChordPlaybackController || new (global.BeginnerChordPlaybackControllerClass || Object)(this.service);
            this.clock = options.clock || global.PlaybackClock || null;

            this.timeline = null;
            this.currentMode = PianoPlaybackMode.ORIGINAL_CHORDS;
            this.playbackRate = 1.0;
            this._isPlaying = false;
            this._isPaused = false;
            this._pauseOffset = 0;
            this._clockUnsub = null;

            this.stateListeners = [];
            this.modeListeners = [];
            this.chordListeners = [];

            // Wire child controller events
            if (this.originalController && this.originalController.onChordTrigger) {
                this.originalController.onChordTrigger((chord, idx) => {
                    if (this.currentMode === PianoPlaybackMode.ORIGINAL_CHORDS && this._isPlaying) {
                        this._notifyChordTrigger(chord, idx, PianoPlaybackMode.ORIGINAL_CHORDS);
                    }
                });
            }

            if (this.beginnerController && this.beginnerController.onChordTrigger) {
                this.beginnerController.onChordTrigger((chord, idx) => {
                    if (this.currentMode === PianoPlaybackMode.BEGINNER_CHORDS && this._isPlaying) {
                        this._notifyChordTrigger(chord, idx, PianoPlaybackMode.BEGINNER_CHORDS);
                    }
                });
            }

            if (this.clock) {
                this.bindClock(this.clock);
            }
        }

        /**
         * Loads a canonical SongTimeline.
         * @param {Object} songTimeline
         */
        loadTimeline(songTimeline) {
            if (!songTimeline) {
                console.warn('[UnifiedPianoPlaybackController] No SongTimeline provided to loadTimeline.');
                this.timeline = null;
                return;
            }
            this.stop();
            this.timeline = songTimeline;
            this._pauseOffset = 0;
            if (this.clock && songTimeline.duration) {
                this.clock.setDuration(songTimeline.duration);
            }
        }

        /**
         * Binds this controller to follow a central PlaybackClock instance.
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
                if (!this.timeline) return;

                const rateChanged = snap.playbackRate !== prevRate;
                const stateChanged = snap.state !== prevState;
                const timeJump = Math.abs(snap.currentTime - prevTime) > 0.1;

                this.playbackRate = snap.playbackRate;

                // 1. Playback State Synchronization
                if (stateChanged) {
                    if (snap.state === 'PLAYING') {
                        this.play(this.currentMode, snap.currentTime, snap.playbackRate);
                    } else if (snap.state === 'PAUSED') {
                        this.pause();
                    } else if (snap.state === 'STOPPED') {
                        this.stop();
                    }
                    prevState = snap.state;
                } else if (snap.state === 'PLAYING') {
                    // 2. Dynamic Rate Change or Seek while playing
                    if (rateChanged || timeJump) {
                        // Cancel future notes & reschedule from current timeline position at new rate
                        this.play(this.currentMode, snap.currentTime, snap.playbackRate);
                    }
                }

                prevRate = snap.playbackRate;
                prevTime = snap.currentTime;
            });
        }

        /**
         * Starts playback in the specified mode from the given offset with optional rate scaling.
         * @param {string} mode - PianoPlaybackMode.ORIGINAL_CHORDS or PianoPlaybackMode.BEGINNER_CHORDS
         * @param {number} startOffset - Offset in seconds (default: 0 or current pause offset)
         * @param {number} playbackRate - Playback rate multiplier (default: 1.0)
         */
        async play(mode = null, startOffset = null, playbackRate = null) {
            if (!this.timeline) {
                console.warn('[UnifiedPianoPlaybackController] Cannot play: No SongTimeline loaded.');
                return false;
            }

            // Validate mode
            const targetMode = mode || this.currentMode;
            if (targetMode !== PianoPlaybackMode.ORIGINAL_CHORDS && targetMode !== PianoPlaybackMode.BEGINNER_CHORDS) {
                console.error(`[UnifiedPianoPlaybackController] Invalid playback mode: ${targetMode}. Must be ORIGINAL_CHORDS or BEGINNER_CHORDS.`);
                return false;
            }

            // Determine offset & rate
            const offset = (startOffset !== null && startOffset !== undefined)
                ? Math.max(0, startOffset)
                : (this._isPaused ? this._pauseOffset : 0);

            const rate = (playbackRate !== null && playbackRate !== undefined)
                ? Math.max(0.1, Number(playbackRate) || 1.0)
                : (this.clock ? this.clock.playbackRate : this.playbackRate);

            // 1. Ensure zero overlap: stop all active voices across both controllers
            this._silenceAll();

            this.currentMode = targetMode;
            this.playbackRate = rate;
            this._isPlaying = true;
            this._isPaused = false;
            this._pauseOffset = offset;

            try {
                if (targetMode === PianoPlaybackMode.ORIGINAL_CHORDS) {
                    await this.originalController.playOriginalChords(this.timeline, offset, rate);
                } else if (targetMode === PianoPlaybackMode.BEGINNER_CHORDS) {
                    await this.beginnerController.playBeginnerChords(this.timeline, offset, rate);
                }

                this._notifyStateChange('playing');
                this._notifyModeChange(this.currentMode);
                return true;
            } catch (err) {
                console.error('[UnifiedPianoPlaybackController] Play error:', err);
                this.stop();
                return false;
            }
        }

        /**
         * Switches the active mode during playback or while stopped.
         * If currently playing, seamlessly restarts in the new mode at the current timestamp.
         * @param {string} newMode
         */
        async switchMode(newMode) {
            if (newMode !== PianoPlaybackMode.ORIGINAL_CHORDS && newMode !== PianoPlaybackMode.BEGINNER_CHORDS) {
                console.warn(`[UnifiedPianoPlaybackController] Invalid mode: ${newMode}`);
                return false;
            }

            if (newMode === this.currentMode) return true;

            const wasPlaying = this._isPlaying;
            const currentPosition = this.getCurrentTime();
            const currentRate = this.playbackRate;

            // Stop current playback cleanly
            this.stop();
            this.currentMode = newMode;
            this._notifyModeChange(newMode);

            if (wasPlaying) {
                return await this.play(newMode, currentPosition, currentRate);
            }
            return true;
        }

        /**
         * Immediately stops playback, silences active voices, and cancels scheduled notes.
         */
        stop() {
            this._silenceAll();
            this._isPlaying = false;
            this._isPaused = false;
            this._pauseOffset = 0;
            this._notifyStateChange('stopped');
        }

        /**
         * Pauses playback and remembers current position.
         */
        pause() {
            if (!this._isPlaying) return;
            this._pauseOffset = this.getCurrentTime();
            this._silenceAll();
            this._isPlaying = false;
            this._isPaused = true;
            this._notifyStateChange('paused');
        }

        /**
         * Restarts playback from 0.0 seconds in the current mode.
         */
        async restart() {
            return await this.play(this.currentMode, 0);
        }

        isPlaying() {
            return this._isPlaying;
        }

        isPaused() {
            return this._isPaused;
        }

        getCurrentMode() {
            return this.currentMode;
        }

        getCurrentTime() {
            if (this._isPaused) return this._pauseOffset;
            if (!this._isPlaying) return 0;
            if (this.currentMode === PianoPlaybackMode.ORIGINAL_CHORDS && this.originalController) {
                return this.originalController.getCurrentTime();
            }
            if (this.currentMode === PianoPlaybackMode.BEGINNER_CHORDS && this.beginnerController) {
                return this.beginnerController.getCurrentTime();
            }
            return 0;
        }

        onStateChange(cb) {
            if (typeof cb === 'function') this.stateListeners.push(cb);
        }

        onModeChange(cb) {
            if (typeof cb === 'function') this.modeListeners.push(cb);
        }

        onChordTrigger(cb) {
            if (typeof cb === 'function') this.chordListeners.push(cb);
        }

        _silenceAll() {
            if (this.originalController && this.originalController.stopOriginalChords) {
                this.originalController.stopOriginalChords();
            }
            if (this.beginnerController && this.beginnerController.stopBeginnerChords) {
                this.beginnerController.stopBeginnerChords();
            }
            if (this.service && this.service.stopAll) {
                this.service.stopAll();
            }
        }

        _notifyStateChange(state) {
            this.stateListeners.forEach(cb => {
                try { cb(state); } catch (e) {}
            });
        }

        _notifyModeChange(mode) {
            this.modeListeners.forEach(cb => {
                try { cb(mode); } catch (e) {}
            });
        }

        _notifyChordTrigger(chord, index, mode) {
            this.chordListeners.forEach(cb => {
                try { cb(chord, index, mode); } catch (e) {}
            });
        }
    }

    // Export Constants, Class & Singleton Instance
    global.PianoPlaybackMode = PianoPlaybackMode;
    global.UnifiedPianoPlaybackControllerClass = UnifiedPianoPlaybackController;
    global.UnifiedPianoPlaybackController = new UnifiedPianoPlaybackController();

})(typeof window !== 'undefined' ? window : global);
