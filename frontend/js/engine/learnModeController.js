/**
 * learnModeController.js
 *
 * Interactive Learn Mode, Step-by-Step Note Navigation, Audition ("Hear it"),
 * One-Finger Simplification, Hand-Isolated Practice, and Rehearsal Markers
 * for HotChords.
 */

(function(global) {
    'use strict';

    class LearnModeController {
        constructor(options = {}) {
            this.clock = options.clock || global.PlaybackClock || null;
            this.adapter = options.adapter || global.StudioTimelineAdapter || null;

            this.enabled = false;
            this.practiceHand = 'both'; // 'both' | 'left' | 'right'
            this.oneFingerMode = false;
            this.octaveTolerant = true;

            this.waitingForInput = false;
            this.expectedNotes = [];
            this.matchedMidis = new Set();
            this.currentStepIndex = 1;
            this.totalSteps = 0;

            this.lastFeedback = {
                status: 'IDLE',
                message: 'Learn Mode Ready',
                callout: 'Listening — pause to try it yourself',
                expected: [],
                played: []
            };
            this._clearedClusterTimes = new Set();

            this.stats = {
                totalPrompts: 0,
                correctHits: 0,
                wrongAttempts: 0,
                streak: 0,
                bestStreak: 0
            };

            this.markers = [];
            this._nextMarkerId = 1;
            this.listeners = new Set();
            this._clockUnsub = null;

            if (this.clock) {
                this.bindClock(this.clock);
            }
        }

        bindClock(clock) {
            if (this._clockUnsub) {
                this._clockUnsub();
                this._clockUnsub = null;
            }
            this.clock = clock;
            if (!clock) return;

            this._clockUnsub = clock.subscribe(snap => {
                if (!this.enabled) return;
                this._updateStepCounters(snap.currentTime);
                if (snap.state === 'PLAYING') {
                    this.waitingForInput = false;
                    this._checkOnsetGate(snap.currentTime);
                }
            });
        }

        _getOnsetClusters() {
            if (!this.adapter) return [];
            const notes = this.adapter.getNotes(null, this.practiceHand);
            const clusters = [];
            for (let i = 0; i < notes.length; i++) {
                const n = notes[i];
                if (!clusters.length || Math.abs(n.start - clusters[clusters.length - 1][0].start) > 0.045) {
                    clusters.push([n]);
                } else {
                    clusters[clusters.length - 1].push(n);
                }
            }
            if (this.oneFingerMode) {
                return clusters.map(cl => [cl[cl.length - 1]]);
            }
            return clusters;
        }

        _updateStepCounters(currentTime) {
            const clusters = this._getOnsetClusters();
            this.totalSteps = clusters.length;
            if (clusters.length === 0) {
                this.currentStepIndex = 0;
                return;
            }
            let idx = clusters.findIndex(cl => cl[0].start >= currentTime - 0.05);
            if (idx === -1) idx = clusters.length - 1;
            this.currentStepIndex = idx + 1;
        }

        setEnabled(enabled) {
            this.enabled = Boolean(enabled);
            this.waitingForInput = false;
            this.expectedNotes = [];
            this.matchedMidis.clear();
            this._clearedClusterTimes.clear();

            const t = this.clock ? this.clock.currentTime : 0;
            this._updateStepCounters(t);

            if (this.enabled) {
                // Immediately gate on current or next note cluster so user sees step instruction
                const clusters = this._getOnsetClusters();
                const targetCluster = clusters[Math.max(0, this.currentStepIndex - 1)] || [];
                if (targetCluster.length > 0) {
                    this._engageClusterGate(targetCluster);
                } else {
                    this.lastFeedback = {
                        status: 'LISTENING',
                        message: 'Learn Mode Active',
                        callout: 'Listening — pause to try it yourself',
                        expected: [],
                        played: []
                    };
                }
            } else {
                this.lastFeedback = {
                    status: 'IDLE',
                    message: 'Learn Mode OFF',
                    callout: '',
                    expected: [],
                    played: []
                };
            }
            this._notify();
            return this.enabled;
        }

        setPracticeHand(hand) {
            const h = String(hand || 'both').toLowerCase();
            this.practiceHand = (h === 'left' || h === 'right') ? h : 'both';
            if (this.adapter) {
                this.adapter.setHandFilter(this.practiceHand);
            }
            this._clearedClusterTimes.clear();
            this._updateStepCounters(this.clock ? this.clock.currentTime : 0);
            this._notify();
            return this.practiceHand;
        }

        setOneFingerMode(enabled) {
            this.oneFingerMode = Boolean(enabled);
            this._clearedClusterTimes.clear();
            if (this.enabled) {
                const clusters = this._getOnsetClusters();
                const targetCluster = clusters[Math.max(0, this.currentStepIndex - 1)] || [];
                if (targetCluster.length > 0) {
                    this._engageClusterGate(targetCluster);
                }
            }
            this._notify();
            return this.oneFingerMode;
        }

        _buildCalloutText(cluster) {
            if (!cluster || cluster.length === 0) {
                return 'Listening — pause to try it yourself';
            }
            const topNote = cluster[cluster.length - 1];
            const finger = topNote.finger || 1;
            if (cluster.length > 1) {
                return `Keep holding ${cluster.length} keys · press the glowing key with finger ${finger}`;
            }
            return `Press the glowing key (${topNote.note || 'note'}) with finger ${finger}`;
        }

        _engageClusterGate(cluster) {
            this.waitingForInput = true;
            this.expectedNotes = cluster;
            this.matchedMidis.clear();
            this.stats.totalPrompts++;

            if (this.clock && this.clock.state === 'PLAYING') {
                this.clock.pause();
            }

            const callout = this._buildCalloutText(cluster);
            const noteNames = cluster.map(n => n.note || `MIDI ${n.midi}`).join(' + ');
            this.lastFeedback = {
                status: 'WAITING',
                message: `Play: ${noteNames}`,
                callout,
                expected: cluster.map(n => n.midi),
                played: []
            };
        }

        _checkOnsetGate(currentTime) {
            if (!this.adapter || this.waitingForInput) return;

            const clusters = this._getOnsetClusters();
            if (!clusters.length) return;

            const matchCluster = clusters.find(cl => Math.abs(cl[0].start - currentTime) <= 0.045);
            if (!matchCluster) return;

            const clusterKey = Math.round(matchCluster[0].start * 20);
            if (this._clearedClusterTimes.has(clusterKey)) return;

            this._engageClusterGate(matchCluster);
            this._notify();
        }

        /**
         * Steps backward to the previous note cluster in Learn Mode.
         */
        stepPrevNote() {
            const clusters = this._getOnsetClusters();
            if (!clusters.length || !this.clock) return null;
            this._clearedClusterTimes.clear();
            const targetIdx = Math.max(0, this.currentStepIndex - 2);
            const cl = clusters[targetIdx];
            this.currentStepIndex = targetIdx + 1;
            this.clock.seek(cl[0].start);
            this._engageClusterGate(cl);
            this._notify();
            return cl;
        }

        /**
         * Steps forward to the next note cluster in Learn Mode.
         */
        stepNextNote() {
            const clusters = this._getOnsetClusters();
            if (!clusters.length || !this.clock) return null;
            this._clearedClusterTimes.clear();
            const targetIdx = Math.min(clusters.length - 1, this.currentStepIndex);
            const cl = clusters[targetIdx];
            this.currentStepIndex = targetIdx + 1;
            this.clock.seek(cl[0].start);
            this._engageClusterGate(cl);
            this._notify();
            return cl;
        }

        /**
         * Auditions ("Hear it") the currently expected note cluster on the piano sampler.
         */
        hearCurrentNote() {
            const notesToPlay = this.expectedNotes && this.expectedNotes.length > 0
                ? this.expectedNotes
                : (() => {
                    const clusters = this._getOnsetClusters();
                    return clusters[Math.max(0, this.currentStepIndex - 1)] || [];
                })();

            if (notesToPlay.length > 0 && global.PianoPlaybackService) {
                const midis = notesToPlay.map(n => n.midi);
                global.PianoPlaybackService.playChord(midis, 0.85, 0.75);
            }
            return notesToPlay;
        }

        /**
         * Submits user-played MIDI note numbers (from Mic, WebMIDI, or UI Keyboard).
         */
        submitUserNotes(playedMidis) {
            const midis = (Array.isArray(playedMidis) ? playedMidis : [playedMidis])
                .map(Number)
                .filter(m => !isNaN(m) && m >= 21 && m <= 108);

            if (midis.length === 0) return this.lastFeedback;

            if (!this.waitingForInput || this.expectedNotes.length === 0) {
                const t = this.clock ? this.clock.currentTime : 0;
                const win = this.adapter ? this.adapter.getWindowState(t, 0.2, 0.1) : { activeNotes: [] };
                if (win.activeNotes.length > 0) {
                    this.expectedNotes = win.activeNotes;
                } else {
                    return this.lastFeedback;
                }
            }

            let anyWrong = false;
            midis.forEach(m => {
                const match = this.expectedNotes.find(exp =>
                    exp.midi === m || (this.octaveTolerant && (exp.midi % 12) === (m % 12))
                );
                if (match) {
                    this.matchedMidis.add(match.midi);
                } else {
                    anyWrong = true;
                }
            });

            const allMatched = this.expectedNotes.every(exp => this.matchedMidis.has(exp.midi));

            if (allMatched) {
                this.stats.correctHits++;
                this.stats.streak++;
                if (this.stats.streak > this.stats.bestStreak) {
                    this.stats.bestStreak = this.stats.streak;
                }

                const clusterKey = Math.round(this.expectedNotes[0].start * 20);
                this._clearedClusterTimes.add(clusterKey);

                this.waitingForInput = false;
                this.lastFeedback = {
                    status: 'CORRECT',
                    message: `✓ Correct! Streak: ${this.stats.streak}`,
                    callout: `✓ Great! Streak: ${this.stats.streak} — advancing to next note`,
                    expected: this.expectedNotes.map(n => n.midi),
                    played: midis
                };
                this._notify();

                if (this.enabled && this.clock && this.clock.state === 'PAUSED') {
                    this.clock.play();
                }
            } else if (anyWrong) {
                this.stats.wrongAttempts++;
                this.stats.streak = 0;
                const expNames = this.expectedNotes.map(n => n.note).join(', ');
                this.lastFeedback = {
                    status: 'INCORRECT',
                    message: `✗ Try again — Expected: ${expNames}`,
                    callout: this._buildCalloutText(this.expectedNotes),
                    expected: this.expectedNotes.map(n => n.midi),
                    played: midis
                };
                this._notify();
            }

            return this.lastFeedback;
        }

        getAccuracyPercent() {
            const total = this.stats.correctHits + this.stats.wrongAttempts;
            if (total === 0) return 100;
            return Math.round((this.stats.correctHits / total) * 100);
        }

        resetStats() {
            this.stats = {
                totalPrompts: 0,
                correctHits: 0,
                wrongAttempts: 0,
                streak: 0,
                bestStreak: 0
            };
            this._clearedClusterTimes.clear();
            this._notify();
        }

        // ─── Rehearsal Markers & Section Looping ─────────────────────────────
        addMarker(timeSec = null, label = null) {
            const t = timeSec !== null && timeSec !== undefined
                ? Math.max(0, Number(timeSec))
                : (this.clock ? this.clock.currentTime : 0);
            const id = this._nextMarkerId++;
            const marker = {
                id,
                time: Math.round(t * 100) / 100,
                label: label || `${id}`
            };
            this.markers.push(marker);
            this.markers.sort((a, b) => a.time - b.time);
            this._notify();
            return marker;
        }

        removeMarker(id) {
            const idx = this.markers.findIndex(m => m.id === Number(id));
            if (idx !== -1) {
                this.markers.splice(idx, 1);
                this._notify();
                return true;
            }
            return false;
        }

        clearMarkers() {
            this.markers = [];
            this._nextMarkerId = 1;
            this._notify();
        }

        jumpToMarker(id) {
            const m = this.markers.find(x => x.id === Number(id));
            if (m && this.clock) {
                this.clock.seek(m.time);
                return m;
            }
            return null;
        }

        subscribe(fn) {
            if (typeof fn === 'function') {
                this.listeners.add(fn);
                return () => this.listeners.delete(fn);
            }
            return () => {};
        }

        getState() {
            return {
                enabled: this.enabled,
                practiceHand: this.practiceHand,
                oneFingerMode: this.oneFingerMode,
                waitingForInput: this.waitingForInput,
                currentStepIndex: this.currentStepIndex,
                totalSteps: this.totalSteps,
                feedback: this.lastFeedback,
                lastFeedback: this.lastFeedback,
                stats: Object.assign({}, this.stats, { accuracyPct: this.getAccuracyPercent() }),
                markers: this.markers.slice()
            };
        }

        _notify() {
            const state = this.getState();
            this.listeners.forEach(fn => {
                try { fn(state); } catch (e) {}
            });
        }
    }

    const instance = new LearnModeController();
    global.LearnModeController = instance;
    global.LearnModeControllerClass = LearnModeController;

    if (typeof module !== 'undefined' && module.exports) {
        module.exports = { LearnModeController, instance };
    }
})(typeof window !== 'undefined' ? window : global);
