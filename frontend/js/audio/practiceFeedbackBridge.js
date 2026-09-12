/**
 * frontend/js/audio/practiceFeedbackBridge.js
 * 
 * Client-Side Real-Time Practice Feedback Bridge for HotChords (Phase 11).
 * 
 * Principles:
 * - PlaybackClock remains the sole temporal authority.
 * - Does NOT advance chords or alter timeline based on microphone.
 * - Compares expected chord voicings against observed microphone/test-signal notes.
 * - Dispatches clean feedback state to subscribers.
 */

(function(global) {
    'use strict';

    const FeedbackStatus = {
        NO_INPUT: 'NO_INPUT',
        LISTENING: 'LISTENING',
        PARTIAL: 'PARTIAL',
        MATCH: 'MATCH',
        WRONG_NOTES: 'WRONG_NOTES',
        LOW_CONFIDENCE: 'LOW_CONFIDENCE',
        EXPECTED_CHORD_UNAVAILABLE: 'EXPECTED_CHORD_UNAVAILABLE',
        INPUT_PERMISSION_DENIED: 'INPUT_PERMISSION_DENIED',
        INPUT_UNAVAILABLE: 'INPUT_UNAVAILABLE',
        INPUT_UNSUPPORTED: 'INPUT_UNSUPPORTED'
    };

    const MatchingMode = {
        EXACT_NOTE_MATCH: 'EXACT_NOTE_MATCH',
        PITCH_CLASS_MATCH: 'PITCH_CLASS_MATCH'
    };

    const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];

    function pitchClass(midi) {
        return ((midi % 12) + 12) % 12;
    }

    class PracticeFeedbackBridge {
        constructor() {
            this.matchingMode = MatchingMode.EXACT_NOTE_MATCH;
            this.graceWindowSeconds = 0.25;
            this.listeners = [];
            this.lastObserved = { notes: [], confidence: 0.0, status: 'NO_INPUT' };
            this.lastFeedback = null;
            this._unsubscribeInput = null;
            this._clockUnsubscribe = null;
        }

        subscribe(callback) {
            if (typeof callback === 'function') {
                this.listeners.push(callback);
            }
            return () => {
                this.listeners = this.listeners.filter(cb => cb !== callback);
            };
        }

        _notify(feedback) {
            this.lastFeedback = feedback;
            for (let i = 0; i < this.listeners.length; i++) {
                try {
                    this.listeners[i](feedback);
                } catch (e) {
                    console.error('[PracticeFeedbackBridge] Listener error:', e);
                }
            }
        }

        setMatchingMode(mode) {
            if (mode === MatchingMode.EXACT_NOTE_MATCH || mode === MatchingMode.PITCH_CLASS_MATCH) {
                this.matchingMode = mode;
            }
        }

        /**
         * Attach to input service and playback clock.
         */
        attach(inputService, playbackClock, currentChordEngine) {
            this.detach();

            if (inputService) {
                this._unsubscribeInput = inputService.subscribe((event) => {
                    if (event.type === 'NOTE_DETECTION') {
                        this.lastObserved = {
                            notes: event.notes || [],
                            confidence: event.confidence || 0.0,
                            status: event.status || 'NO_INPUT',
                            inputStatus: event.inputStatus || 'LISTENING'
                        };
                        this._evaluate(playbackClock, currentChordEngine);
                    } else if (event.type === 'STATUS_CHANGE') {
                        if (event.status.startsWith('INPUT_')) {
                            this._notify({
                                inputStatus: event.status,
                                feedbackStatus: event.status,
                                matchingMode: this.matchingMode,
                                expected: null,
                                observed: this.lastObserved,
                                comparison: null,
                                timing: null
                            });
                        }
                    }
                });
            }

            if (playbackClock && playbackClock.subscribe) {
                this._clockUnsubscribe = playbackClock.subscribe((clockState) => {
                    this._evaluate(playbackClock, currentChordEngine);
                });
            }
        }

        detach() {
            if (this._unsubscribeInput) {
                this._unsubscribeInput();
                this._unsubscribeInput = null;
            }
            if (this._clockUnsubscribe) {
                this._clockUnsubscribe();
                this._clockUnsubscribe = null;
            }
        }

        /**
         * Evaluate expected vs observed notes for the current playback clock position.
         */
        _evaluate(playbackClock, currentChordEngine) {
            const currentTime = playbackClock ? playbackClock.getCurrentTime() : 0.0;
            const currentChordData = currentChordEngine ? currentChordEngine.query(currentTime) : null;

            if (!currentChordData || !currentChordData.chord || currentChordData.chord === 'N') {
                this._notify({
                    inputStatus: this.lastObserved.inputStatus || 'LISTENING',
                    feedbackStatus: FeedbackStatus.EXPECTED_CHORD_UNAVAILABLE,
                    matchingMode: this.matchingMode,
                    expected: null,
                    observed: this.lastObserved,
                    comparison: null,
                    timing: { time: currentTime }
                });
                return;
            }

            const expectedMidi = currentChordData.notes || [];
            const observedMidi = (this.lastObserved.notes || []).map(n => n.midi);
            const obsConf = this.lastObserved.confidence || 0.0;
            const inputStat = this.lastObserved.status || 'NO_INPUT';

            // Check NO_INPUT
            if (inputStat === 'NO_INPUT' || (observedMidi.length === 0 && obsConf < 0.2)) {
                this._notify({
                    inputStatus: inputStat,
                    feedbackStatus: FeedbackStatus.NO_INPUT,
                    matchingMode: this.matchingMode,
                    expected: {
                        chord: currentChordData.chord,
                        midi: expectedMidi
                    },
                    observed: this.lastObserved,
                    comparison: {
                        correctNotes: [],
                        missingNotes: expectedMidi,
                        extraNotes: [],
                        notePrecision: 0.0,
                        noteRecall: 0.0,
                        noteF1: 0.0
                    },
                    timing: { time: currentTime }
                });
                return;
            }

            // Check LOW_CONFIDENCE
            if (obsConf < 0.35) {
                this._notify({
                    inputStatus: inputStat,
                    feedbackStatus: FeedbackStatus.LOW_CONFIDENCE,
                    matchingMode: this.matchingMode,
                    expected: {
                        chord: currentChordData.chord,
                        midi: expectedMidi
                    },
                    observed: this.lastObserved,
                    comparison: null,
                    timing: { time: currentTime }
                });
                return;
            }

            // Compute comparison
            const comparison = this.compareNotes(expectedMidi, observedMidi, this.matchingMode);

            // Determine chord match status
            let feedbackStatus = FeedbackStatus.WRONG_NOTES;
            if (comparison.noteRecall >= 0.80 && comparison.notePrecision >= 0.70) {
                feedbackStatus = FeedbackStatus.MATCH;
            } else if (comparison.noteRecall >= 0.50 && comparison.notePrecision >= 0.50) {
                feedbackStatus = FeedbackStatus.PARTIAL;
            }

            this._notify({
                inputStatus: inputStat,
                feedbackStatus: feedbackStatus,
                matchingMode: this.matchingMode,
                expected: {
                    chord: currentChordData.chord,
                    midi: expectedMidi
                },
                observed: this.lastObserved,
                comparison: comparison,
                timing: {
                    time: currentTime,
                    chordStart: currentChordData.start,
                    chordEnd: currentChordData.end
                }
            });
        }

        compareNotes(expectedMidi, observedMidi, mode = MatchingMode.EXACT_NOTE_MATCH) {
            let correct = [];
            let missing = [];
            let extra = [];

            if (mode === MatchingMode.EXACT_NOTE_MATCH) {
                const expSet = new Set(expectedMidi);
                const obsSet = new Set(observedMidi);

                correct = Array.from(expSet).filter(m => obsSet.has(m)).sort((a, b) => a - b);
                missing = Array.from(expSet).filter(m => !obsSet.has(m)).sort((a, b) => a - b);
                extra = Array.from(obsSet).filter(m => !expSet.has(m)).sort((a, b) => a - b);
            } else {
                const expPcSet = new Set(expectedMidi.map(pitchClass));
                const obsPcSet = new Set(observedMidi.map(pitchClass));

                const correctPc = Array.from(expPcSet).filter(pc => obsPcSet.has(pc));
                const missingPc = Array.from(expPcSet).filter(pc => !obsPcSet.has(pc));
                const extraPc = Array.from(obsPcSet).filter(pc => !expPcSet.has(pc));

                correct = correctPc.map(pc => NOTE_NAMES[pc]);
                missing = missingPc.map(pc => NOTE_NAMES[pc]);
                extra = extraPc.map(pc => NOTE_NAMES[pc]);
            }

            const nCorrect = correct.length;
            const nExp = expectedMidi.length;
            const nObs = observedMidi.length;

            const recall = nExp > 0 ? (nCorrect / nExp) : (nObs === 0 ? 1.0 : 0.0);
            const precision = (nCorrect + extra.length) > 0 ? (nCorrect / (nCorrect + extra.length)) : (nObs === 0 ? 1.0 : 0.0);
            const f1 = (precision + recall) > 0 ? (2.0 * precision * recall / (precision + recall)) : 0.0;

            return {
                matchingMode: mode,
                correctNotes: correct,
                missingNotes: missing,
                extraNotes: extra,
                notePrecision: Math.round(precision * 1000) / 1000,
                noteRecall: Math.round(recall * 1000) / 1000,
                noteF1: Math.round(f1 * 1000) / 1000
            };
        }
    }

    // Export module
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = {
            PracticeFeedbackBridge,
            FeedbackStatus,
            MatchingMode
        };
    } else {
        global.PracticeFeedbackBridge = PracticeFeedbackBridge;
        global.FeedbackStatus = FeedbackStatus;
        global.MatchingMode = MatchingMode;
    }

})(typeof window !== 'undefined' ? window : this);
