/**
 * currentChordEngine.js
 * 
 * Production Deterministic Current Chord Engine for HotChords Phase 6A.
 * 
 * Responsibilities:
 * Answers: "What chord should the beginner be playing at the current PlaybackClock time?"
 * Consumes: SongTimeline.beginner_chords and PlaybackClock.currentTime (or query time).
 * 
 * Invariants:
 * - Pure query / state engine (zero clocks, zero timers, zero AudioContexts, zero audio playback).
 * - Never modifies SongTimeline or ChordEvents.
 * - Never duplicates or permanently copies chord arrays.
 * - Monotonic seconds-based mathematical calculations.
 */

(function(global) {
    'use strict';

    const DEFAULT_ANTICIPATION_THRESHOLD = 0.75; // seconds

    function getChordStart(c) {
        if (!c) return 0;
        if (typeof c.startTime === 'number') return c.startTime;
        if (typeof c.time === 'number') return c.time;
        if (typeof c.start === 'number') return c.start;
        return 0;
    }

    function getChordEnd(c) {
        if (!c) return 0;
        if (typeof c.endTime === 'number') return c.endTime;
        if (typeof c.end === 'number') return c.end;
        return 0;
    }

    class CurrentChordEngine {
        /**
         * @param {Object} [clock] - PlaybackClock instance (optional at instantiation)
         * @param {Object} [options] - Configuration options { anticipationThreshold: 0.75 }
         */
        constructor(clock = null, options = {}) {
            this.clock = clock || (typeof global !== 'undefined' && global.PlaybackClock ? global.PlaybackClock : null);
            this.anticipationThreshold = typeof options.anticipationThreshold === 'number' && options.anticipationThreshold >= 0
                ? options.anticipationThreshold
                : DEFAULT_ANTICIPATION_THRESHOLD;

            this._timeline = null;
            this.mode = options.mode || 'beginner'; // 'beginner' | 'original'
        }

        /**
         * Sets chord query mode.
         * @param {'beginner'|'original'} mode
         */
        setMode(mode) {
            this.mode = mode === 'original' ? 'original' : 'beginner';
        }

        /**
         * Sets or updates the PlaybackClock instance.
         * @param {Object} clock
         */
        setClock(clock) {
            this.clock = clock;
        }

        /**
         * Loads a SongTimeline reference. Does NOT copy chord events.
         * @param {Object} songTimeline
         */
        loadTimeline(songTimeline) {
            this._timeline = songTimeline || null;
        }

        /**
         * Clears loaded timeline and resets state.
         */
        clear() {
            this._timeline = null;
        }

        /**
         * Sets the anticipation threshold in seconds.
         * @param {number} seconds
         */
        setAnticipationThreshold(seconds) {
            this.anticipationThreshold = Math.max(0, Number(seconds) || 0);
        }

        /**
         * Returns the current anticipation threshold in seconds.
         * @returns {number}
         */
        getAnticipationThreshold() {
            return this.anticipationThreshold;
        }

        /**
         * Returns the active array of chord events from the loaded timeline based on current mode.
         * Resolves both beginner and original chord arrays.
         * @returns {Array|null}
         * @private
         */
        _getBeginnerChords() {
            if (!this._timeline) return null;
            if (this.mode === 'original') {
                if (Array.isArray(this._timeline.originalChords)) return this._timeline.originalChords;
                if (Array.isArray(this._timeline.original_chords)) return this._timeline.original_chords;
                if (Array.isArray(this._timeline.chords)) return this._timeline.chords;
            }
            if (Array.isArray(this._timeline.beginnerChords)) {
                return this._timeline.beginnerChords;
            }
            if (Array.isArray(this._timeline.beginner_chords)) {
                return this._timeline.beginner_chords;
            }
            if (Array.isArray(this._timeline.chords)) {
                return this._timeline.chords;
            }
            return null;
        }

        /**
         * Resolves the current evaluation time in seconds.
         * @param {number|null} [timeOverride]
         * @returns {number}
         * @private
         */
        _resolveTime(timeOverride) {
            if (typeof timeOverride === 'number' && !isNaN(timeOverride)) {
                return Math.max(0, timeOverride);
            }
            if (this.clock) {
                if (typeof this.clock.getCurrentTime === 'function') {
                    return Math.max(0, this.clock.getCurrentTime());
                }
                if (typeof this.clock.currentTime === 'number') {
                    return Math.max(0, this.clock.currentTime);
                }
            }
            return 0;
        }

        /**
         * Internal query helper that evaluates chords at a given time.
         * Handles exact boundary semantics deterministically:
         * Interval is [startTime, endTime).
         * For example: C [0, 2), G [2, 4) -> at 2.0s, current is G.
         * At exactly final chord endTime -> current is null.
         * @param {number} t - Time in seconds
         * @returns {Object} { currentChord, nextChord, previousChord, currentChordIndex }
         * @private
         */
        _queryAtTime(t) {
            const chords = this._getBeginnerChords();
            if (!chords || chords.length === 0) {
                return {
                    currentChord: null,
                    nextChord: null,
                    previousChord: null,
                    currentChordIndex: -1
                };
            }

            const n = chords.length;
            const firstStart = getChordStart(chords[0]);
            const lastEnd = getChordEnd(chords[n - 1]);

            // Time strictly before first chord
            if (t < firstStart) {
                return {
                    currentChord: null,
                    nextChord: chords[0],
                    previousChord: null,
                    currentChordIndex: -1
                };
            }

            // Time at or after final chord end
            if (t >= lastEnd) {
                return {
                    currentChord: null,
                    nextChord: null,
                    previousChord: chords[n - 1],
                    currentChordIndex: -1
                };
            }

            // Binary search for the matching interval [start, end)
            let low = 0;
            let high = n - 1;

            while (low <= high) {
                const mid = Math.floor((low + high) / 2);
                const start = getChordStart(chords[mid]);
                const end = getChordEnd(chords[mid]);

                if (t >= start && t < end) {
                    return {
                        currentChord: chords[mid],
                        nextChord: mid < n - 1 ? chords[mid + 1] : null,
                        previousChord: mid > 0 ? chords[mid - 1] : null,
                        currentChordIndex: mid
                    };
                } else if (t < start) {
                    high = mid - 1;
                } else {
                    low = mid + 1;
                }
            }

            // If time falls in an inter-chord gap
            const prevChord = high >= 0 && high < n ? chords[high] : null;
            const nextChord = low >= 0 && low < n ? chords[low] : null;

            return {
                currentChord: null,
                nextChord: nextChord,
                previousChord: prevChord,
                currentChordIndex: -1
            };
        }

        /**
         * Returns the current chord event at time T, or null.
         * @param {number|null} [timeOverride]
         * @returns {Object|null}
         */
        getCurrentChord(timeOverride = null) {
            const t = this._resolveTime(timeOverride);
            return this._queryAtTime(t).currentChord;
        }

        /**
         * Returns the immediately following chord event at time T, or null.
         * @param {number|null} [timeOverride]
         * @returns {Object|null}
         */
        getNextChord(timeOverride = null) {
            const t = this._resolveTime(timeOverride);
            return this._queryAtTime(t).nextChord;
        }

        /**
         * Returns the immediately preceding chord event at time T, or null.
         * @param {number|null} [timeOverride]
         * @returns {Object|null}
         */
        getPreviousChord(timeOverride = null) {
            const t = this._resolveTime(timeOverride);
            return this._queryAtTime(t).previousChord;
        }

        /**
         * Returns the 0-based index of the current chord in beginner_chords, or -1.
         * @param {number|null} [timeOverride]
         * @returns {number}
         */
        getCurrentChordIndex(timeOverride = null) {
            const t = this._resolveTime(timeOverride);
            return this._queryAtTime(t).currentChordIndex;
        }

        /**
         * Returns the elapsed time into the current chord in seconds (>= 0).
         * @param {number|null} [timeOverride]
         * @returns {number}
         */
        getTimeIntoChord(timeOverride = null) {
            const t = this._resolveTime(timeOverride);
            const query = this._queryAtTime(t);
            if (!query.currentChord) return 0;
            const start = getChordStart(query.currentChord);
            return Math.max(0, t - start);
        }

        /**
         * Returns the remaining time in the current chord in seconds (>= 0).
         * @param {number|null} [timeOverride]
         * @returns {number}
         */
        getTimeRemaining(timeOverride = null) {
            const t = this._resolveTime(timeOverride);
            const query = this._queryAtTime(t);
            if (!query.currentChord) return 0;
            const end = getChordEnd(query.currentChord);
            return Math.max(0, end - t);
        }

        /**
         * Returns the normalized progress through the current chord [0.0, 1.0].
         * @param {number|null} [timeOverride]
         * @returns {number}
         */
        getProgress(timeOverride = null) {
            const t = this._resolveTime(timeOverride);
            const query = this._queryAtTime(t);
            if (!query.currentChord) return 0.0;

            const start = getChordStart(query.currentChord);
            const end = getChordEnd(query.currentChord);
            const duration = Math.max(0.0001, end - start);
            const elapsed = t - start;

            return Math.min(1.0, Math.max(0.0, elapsed / duration));
        }

        /**
         * Returns whether a chord change is approaching within the anticipation threshold.
         * Evaluates true if:
         * 1. Currently inside a chord with a nextChord and timeRemaining <= anticipationThreshold.
         * 2. Or currently before a nextChord and (nextChord.startTime - t) <= anticipationThreshold.
         * @param {number|null} [timeOverride]
         * @returns {boolean}
         */
        isApproachingNextChord(timeOverride = null) {
            const t = this._resolveTime(timeOverride);
            const query = this._queryAtTime(t);

            if (query.currentChord && query.nextChord) {
                const end = getChordEnd(query.currentChord);
                const timeRemaining = end - t;
                return timeRemaining <= this.anticipationThreshold && timeRemaining >= 0;
            }

            if (!query.currentChord && query.nextChord) {
                const nextStart = getChordStart(query.nextChord);
                const timeToNext = nextStart - t;
                return timeToNext <= this.anticipationThreshold && timeToNext >= 0;
            }

            return false;
        }

        /**
         * Returns a full snapshot of the engine query state at time T.
         * @param {number|null} [timeOverride]
         * @returns {Object}
         */
        getState(timeOverride = null) {
            const t = this._resolveTime(timeOverride);
            const query = this._queryAtTime(t);

            let timeIntoChord = 0;
            let timeRemaining = 0;
            let progress = 0.0;
            let isApproaching = false;

            if (query.currentChord) {
                const start = getChordStart(query.currentChord);
                const end = getChordEnd(query.currentChord);
                const duration = Math.max(0.0001, end - start);
                
                timeIntoChord = Math.max(0, t - start);
                timeRemaining = Math.max(0, end - t);
                progress = Math.min(1.0, Math.max(0.0, (t - start) / duration));

                if (query.nextChord) {
                    isApproaching = timeRemaining <= this.anticipationThreshold && timeRemaining >= 0;
                }
            } else if (query.nextChord) {
                const nextStart = getChordStart(query.nextChord);
                const timeToNext = nextStart - t;
                isApproaching = timeToNext <= this.anticipationThreshold && timeToNext >= 0;
            }

            return {
                currentTime: t,
                currentChord: query.currentChord,
                nextChord: query.nextChord,
                previousChord: query.previousChord,
                currentChordIndex: query.currentChordIndex,
                timeIntoCurrentChord: timeIntoChord,
                timeIntoChord: timeIntoChord,
                timeRemaining: timeRemaining,
                progress: progress,
                isApproachingNextChord: isApproaching,
                anticipationThreshold: this.anticipationThreshold
            };
        }
    }

    // Export for Browser and Node environments
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = { CurrentChordEngine };
    }
    if (typeof window !== 'undefined') {
        window.CurrentChordEngine = CurrentChordEngine;
    }
})(typeof globalThis !== 'undefined' ? globalThis : (typeof window !== 'undefined' ? window : this));
