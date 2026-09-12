/**
 * frontend/js/audio/practiceMetricsTracker.js
 * 
 * Client-Side Real-Time Practice Metrics & Pedagogy Engine for HotChords (Phase 12).
 * 
 * Invariants:
 * - Bounded memory: Ring buffer of max 50 recent events; zero unbounded array growth.
 * - Multi-metric objective evaluation without single misleading composite accuracy numbers.
 * - Real-time per-chord mastery tracking.
 * - Actionable targeted practice recommendations and conservative adaptive tempo advice.
 */

(function(global) {
    'use strict';

    const PlayerFeedbackEventType = {
        CHORD_READY: 'CHORD_READY',
        CHORD_MATCHED: 'CHORD_MATCHED',
        CHORD_PARTIAL: 'CHORD_PARTIAL',
        CHORD_MISSED: 'CHORD_MISSED',
        WRONG_NOTES: 'WRONG_NOTES',
        NO_INPUT: 'NO_INPUT',
        LOW_CONFIDENCE: 'LOW_CONFIDENCE',
        INPUT_PROBLEM: 'INPUT_PROBLEM'
    };

    class PracticeMetricsTracker {
        constructor(maxRecentEvents = 50) {
            this.maxRecentEvents = maxRecentEvents;
            this.recentEvents = [];
            this.listeners = [];

            // Session Aggregates
            this.sessionStartTime = 0;
            this.totalPracticeDurationSeconds = 0;
            this.completedLoops = 0;
            this.chordsAttempted = 0;
            this.chordsMatched = 0;
            this.chordsPartial = 0;
            this.chordsMissed = 0;
            this.wrongNoteEvents = 0;
            this.noInputEvents = 0;
            this.lowConfidenceEvents = 0;

            this.timingOffsets = [];
            this.notePrecisions = [];
            this.noteRecalls = [];
            this.noteF1s = [];

            this.chordStats = new Map();
            this.loopHistory = [];
            this._currentLoopMatches = 0;
            this._currentLoopAttempts = 0;
        }

        subscribe(callback) {
            if (typeof callback === 'function') {
                this.listeners.push(callback);
            }
            return () => {
                this.listeners = this.listeners.filter(cb => cb !== callback);
            };
        }

        _notify(event) {
            for (let i = 0; i < this.listeners.length; i++) {
                try {
                    this.listeners[i](event);
                } catch (e) {
                    console.error('[PracticeMetricsTracker] Listener error:', e);
                }
            }
        }

        startSession(currentPlaybackTime = 0.0) {
            this.sessionStartTime = currentPlaybackTime;
        }

        recordEvent(event) {
            // Bounded ring buffer
            if (this.recentEvents.length >= this.maxRecentEvents) {
                this.recentEvents.shift();
            }
            this.recentEvents.push(event);

            const chordName = event.chordName || 'N';

            if (chordName !== 'N' && !this.chordStats.has(chordName)) {
                this.chordStats.set(chordName, {
                    attempts: 0,
                    matches: 0,
                    partials: 0,
                    misses: 0,
                    timingOffsets: [],
                    recalls: [],
                    precisions: []
                });
            }

            if (event.eventType === PlayerFeedbackEventType.CHORD_MATCHED) {
                this.chordsAttempted++;
                this.chordsMatched++;
                this._currentLoopAttempts++;
                this._currentLoopMatches++;
                this.timingOffsets.push(event.timingOffsetMs || 0);
                this.notePrecisions.push(event.notePrecision || 1.0);
                this.noteRecalls.push(event.noteRecall || 1.0);
                this.noteF1s.push(event.noteF1 || 1.0);

                if (this.chordStats.has(chordName)) {
                    const st = this.chordStats.get(chordName);
                    st.attempts++;
                    st.matches++;
                    st.timingOffsets.push(event.timingOffsetMs || 0);
                    st.recalls.push(event.noteRecall || 1.0);
                    st.precisions.push(event.notePrecision || 1.0);
                }
            } else if (event.eventType === PlayerFeedbackEventType.CHORD_PARTIAL) {
                this.chordsAttempted++;
                this.chordsPartial++;
                this._currentLoopAttempts++;
                this.timingOffsets.push(event.timingOffsetMs || 0);
                this.notePrecisions.push(event.notePrecision || 0.5);
                this.noteRecalls.push(event.noteRecall || 0.5);
                this.noteF1s.push(event.noteF1 || 0.5);

                if (this.chordStats.has(chordName)) {
                    const st = this.chordStats.get(chordName);
                    st.attempts++;
                    st.partials++;
                    st.timingOffsets.push(event.timingOffsetMs || 0);
                    st.recalls.push(event.noteRecall || 0.5);
                    st.precisions.push(event.notePrecision || 0.5);
                }
            } else if (event.eventType === PlayerFeedbackEventType.CHORD_MISSED) {
                this.chordsAttempted++;
                this.chordsMissed++;
                this._currentLoopAttempts++;
                this.noteRecalls.push(0.0);

                if (this.chordStats.has(chordName)) {
                    const st = this.chordStats.get(chordName);
                    st.attempts++;
                    st.misses++;
                    st.recalls.push(0.0);
                }
            } else if (event.eventType === PlayerFeedbackEventType.WRONG_NOTES) {
                this.wrongNoteEvents++;
            } else if (event.eventType === PlayerFeedbackEventType.NO_INPUT) {
                this.noInputEvents++;
            } else if (event.eventType === PlayerFeedbackEventType.LOW_CONFIDENCE) {
                this.lowConfidenceEvents++;
            }

            this._notify({ type: 'METRICS_UPDATED', summary: this.getSessionSummary() });
        }

        recordLoopCompleted() {
            this.completedLoops++;
            const matchRate = this._currentLoopAttempts > 0 ? (this._currentLoopMatches / this._currentLoopAttempts) : 0.0;
            this.loopHistory.push({
                loopNumber: this.completedLoops,
                attempts: this._currentLoopAttempts,
                matches: this._currentLoopMatches,
                matchRate: Math.round(matchRate * 1000) / 1000
            });
            this._currentLoopMatches = 0;
            this._currentLoopAttempts = 0;
        }

        updateDuration(currentTime) {
            if (this.sessionStartTime > 0 && currentTime >= this.sessionStartTime) {
                this.totalPracticeDurationSeconds = Math.round((currentTime - this.sessionStartTime) * 10) / 10;
            }
        }

        getSessionSummary() {
            const avg = (arr) => arr.length > 0 ? (arr.reduce((a, b) => a + b, 0) / arr.length) : 0;
            const med = (arr) => {
                if (arr.length === 0) return 0;
                const sorted = [...arr].sort((a, b) => a - b);
                return sorted[Math.floor(sorted.length / 2)];
            };

            return {
                practiceDurationSeconds: this.totalPracticeDurationSeconds,
                completedLoops: this.completedLoops,
                chordsAttempted: this.chordsAttempted,
                chordsMatched: this.chordsMatched,
                chordsPartial: this.chordsPartial,
                chordsMissed: this.chordsMissed,
                wrongNoteEvents: this.wrongNoteEvents,
                noInputEvents: this.noInputEvents,
                lowConfidenceEvents: this.lowConfidenceEvents,
                averageTimingOffsetMs: Math.round(avg(this.timingOffsets) * 10) / 10,
                medianTimingOffsetMs: Math.round(med(this.timingOffsets) * 10) / 10,
                notePrecision: Math.round(avg(this.notePrecisions) * 1000) / 1000,
                noteRecall: Math.round(avg(this.noteRecalls) * 1000) / 1000,
                noteF1: Math.round(avg(this.noteF1s) * 1000) / 1000
            };
        }

        getChordMasteryMap() {
            const res = {};
            const avg = (arr) => arr.length > 0 ? (arr.reduce((a, b) => a + b, 0) / arr.length) : 0;

            for (const [chordName, st] of this.chordStats.entries()) {
                res[chordName] = {
                    chordName: chordName,
                    attempts: st.attempts,
                    matches: st.matches,
                    partials: st.partials,
                    misses: st.misses,
                    avgTimingOffsetMs: Math.round(avg(st.timingOffsets) * 10) / 10,
                    avgNoteRecall: Math.round(avg(st.recalls) * 1000) / 1000,
                    avgNotePrecision: Math.round(avg(st.precisions) * 1000) / 1000
                };
            }
            return res;
        }

        getTargetedRecommendations() {
            const recs = [];
            const mastery = this.getChordMasteryMap();

            // 1. Weak Chord detection
            for (const [cName, stats] of Object.entries(mastery)) {
                if (stats.attempts >= 2 && stats.avgNoteRecall < 0.60) {
                    recs.push({
                        type: 'CHORD_FOCUS',
                        chord: cName,
                        priority: 'HIGH',
                        message: `Focus on ${cName}: note recall is ${Math.round(stats.avgNoteRecall * 100)}%. Practice individual hand shape.`
                    });
                }
            }

            // 2. Timing Lag
            const summary = this.getSessionSummary();
            if (summary.averageTimingOffsetMs > 150.0 && summary.chordsAttempted >= 4) {
                recs.push({
                    type: 'TIMING',
                    priority: 'MEDIUM',
                    message: `Late chord transitions observed (avg +${Math.round(summary.averageTimingOffsetMs)}ms). Consider slowing tempo.`
                });
            }

            // 3. Extra Notes
            if (summary.notePrecision < 0.70 && summary.chordsAttempted >= 4) {
                recs.push({
                    type: 'ACCURACY',
                    priority: 'MEDIUM',
                    message: 'Extraneous notes detected. Verify finger placement and arch.'
                });
            }

            return recs;
        }

        getAdaptiveTempoRecommendation(currentBpm, originalBpm) {
            if (this.loopHistory.length < 2) {
                return {
                    recommendation: 'MAINTAIN',
                    recommendedBpm: currentBpm,
                    reason: 'Continue practice at current tempo to establish muscle memory.'
                };
            }

            const recent = this.loopHistory.slice(-2);
            const avgMatch = (recent[0].matchRate + recent[1].matchRate) / 2;

            if (avgMatch >= 0.88 && currentBpm < originalBpm) {
                const nextBpm = Math.min(originalBpm, Math.round((currentBpm + 3.0) * 10) / 10);
                return {
                    recommendation: 'INCREASE_TEMPO',
                    recommendedBpm: nextBpm,
                    reason: `High accuracy across last 2 loops (${Math.round(avgMatch * 100)}% match). Ready for ${nextBpm} BPM.`
                };
            } else if (avgMatch <= 0.45 && currentBpm > 35.0) {
                const nextBpm = Math.max(30.0, Math.round((currentBpm - 5.0) * 10) / 10);
                return {
                    recommendation: 'DECREASE_TEMPO',
                    recommendedBpm: nextBpm,
                    reason: `High error rate across last 2 loops (${Math.round(avgMatch * 100)}% match). Slow down to ${nextBpm} BPM.`
                };
            }

            return {
                recommendation: 'MAINTAIN',
                recommendedBpm: currentBpm,
                reason: 'Steady progress. Maintain current tempo.'
            };
        }

        exportSessionReport() {
            return {
                summary: this.getSessionSummary(),
                chordMastery: this.getChordMasteryMap(),
                loopHistory: this.loopHistory,
                recommendations: this.getTargetedRecommendations(),
                recentEventsCount: this.recentEvents.length
            };
        }

        resetSession() {
            this.recentEvents = [];
            this.sessionStartTime = 0;
            this.totalPracticeDurationSeconds = 0;
            this.completedLoops = 0;
            this.chordsAttempted = 0;
            this.chordsMatched = 0;
            this.chordsPartial = 0;
            this.chordsMissed = 0;
            this.wrongNoteEvents = 0;
            this.noInputEvents = 0;
            this.lowConfidenceEvents = 0;
            this.timingOffsets = [];
            this.notePrecisions = [];
            this.noteRecalls = [];
            this.noteF1s = [];
            this.chordStats.clear();
            this.loopHistory = [];
            this._currentLoopMatches = 0;
            this._currentLoopAttempts = 0;
        }
    }

    // Export module
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = {
            PracticeMetricsTracker,
            PlayerFeedbackEventType
        };
    } else {
        global.PracticeMetricsTracker = PracticeMetricsTracker;
        global.PlayerFeedbackEventType = PlayerFeedbackEventType;
    }

})(typeof window !== 'undefined' ? window : this);
