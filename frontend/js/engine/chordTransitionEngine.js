/**
 * chordTransitionEngine.js
 * 
 * Production Deterministic Chord Transition Engine for HotChords Phase 6C.
 * 
 * Responsibilities:
 * Answers: "How should the beginner move from the current chord to the next chord?"
 * Consumes: Two beginner ChordEvents (or chord names / dicts) and optional available preparation time.
 * 
 * Invariants:
 * - Uses PianoFingeringEngine to derive deterministic voicings (zero duplicate fingering systems).
 * - Zero mutation of SongTimeline, ChordEvents, or Clock state.
 * - Pure query / calculation engine with 100% deterministic output.
 * - Measurable physical MIDI-based difficulty evaluation (EASY, MODERATE, HARD).
 */

(function(global) {
    'use strict';

    const PITCH_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];

    const DIFFICULTY_LEVELS = Object.freeze({
        EASY: 'EASY',
        MODERATE: 'MODERATE',
        HARD: 'HARD'
    });

    const DIRECTION = Object.freeze({
        UP: 'UP',
        DOWN: 'DOWN',
        STATIONARY: 'STATIONARY'
    });

    /**
     * Resolves the fingering engine from environment.
     * @returns {Object} PianoFingeringEngine instance/module
     */
    function resolveFingeringEngine() {
        if (typeof global !== 'undefined' && global.PianoFingeringEngine) {
            return global.PianoFingeringEngine;
        }
        if (typeof window !== 'undefined' && window.PianoFingeringEngine) {
            return window.PianoFingeringEngine;
        }
        if (typeof require !== 'undefined') {
            try {
                const mod = require('./pianoFingeringEngine.js');
                return mod.PianoFingeringEngine || mod;
            } catch (e) {
                // Ignore fallback
            }
        }
        return null;
    }

    /**
     * Extracts chord name string from various input formats.
     * @param {Object|string} chordInput
     * @returns {string|null}
     */
    function extractChordName(chordInput) {
        if (!chordInput) return null;
        if (typeof chordInput === 'string') {
            const clean = chordInput.trim();
            return (clean && clean !== 'N' && clean !== 'null' && clean !== 'undefined') ? clean : null;
        }
        if (typeof chordInput === 'object') {
            const name = chordInput.chordName || chordInput.chord || chordInput.name || '';
            const clean = String(name).trim();
            return (clean && clean !== 'N' && clean !== 'null' && clean !== 'undefined') ? clean : null;
        }
        return null;
    }

    /**
     * Resolves available preparation time in seconds from input chords or options.
     * @param {Object|string} fromChord
     * @param {Object|string} toChord
     * @param {number|Object} [timeOrOptions]
     * @returns {number|null}
     */
    function resolvePreparationTime(fromChord, toChord, timeOrOptions) {
        if (typeof timeOrOptions === 'number' && !isNaN(timeOrOptions) && timeOrOptions >= 0) {
            return timeOrOptions;
        }
        if (timeOrOptions && typeof timeOrOptions === 'object') {
            if (typeof timeOrOptions.availableTimeSeconds === 'number') {
                return Math.max(0, timeOrOptions.availableTimeSeconds);
            }
            if (typeof timeOrOptions.preparationTime === 'number') {
                return Math.max(0, timeOrOptions.preparationTime);
            }
        }
        if (fromChord && typeof fromChord === 'object' && toChord && typeof toChord === 'object') {
            const toStart = typeof toChord.startTime === 'number' ? toChord.startTime : (typeof toChord.time === 'number' ? toChord.time : null);
            const fromEnd = typeof fromChord.endTime === 'number' ? fromChord.endTime : (typeof fromChord.end === 'number' ? fromChord.end : null);
            const fromStart = typeof fromChord.startTime === 'number' ? fromChord.startTime : (typeof fromChord.time === 'number' ? fromChord.time : null);

            if (toStart !== null && fromEnd !== null) {
                // If there is an explicit gap or contiguous transition
                return Math.max(0, toStart - fromStart);
            }
        }
        return null;
    }

    /**
     * Analyzes movement for a single hand (LH or RH) between two voicings.
     * @param {Array} fromHand - Array of note objects from PianoFingeringEngine
     * @param {Array} toHand - Array of note objects from PianoFingeringEngine
     * @returns {Object}
     */
    function analyzeSingleHandMovement(fromHand, toHand) {
        const fromItems = Array.isArray(fromHand) ? fromHand : [];
        const toItems = Array.isArray(toHand) ? toHand : [];

        const fromNotes = fromItems.map(x => x.note);
        const toNotes = toItems.map(x => x.note);
        const fromMidi = fromItems.map(x => x.midi);
        const toMidi = toItems.map(x => x.midi);

        if (fromItems.length === 0 && toItems.length === 0) {
            return {
                fromNotes: [],
                toNotes: [],
                fromMidi: [],
                toMidi: [],
                movement: [],
                movementDistance: 0,
                maxMovement: 0,
                sharedNotes: [],
                stationaryNotes: [],
                changedNotes: []
            };
        }

        if (fromItems.length === 0) {
            return {
                fromNotes: [],
                toNotes: toNotes,
                fromMidi: [],
                toMidi: toMidi,
                movement: toItems.map(item => ({
                    fromNote: null,
                    toNote: item.note,
                    fromMidi: null,
                    toMidi: item.midi,
                    fromFinger: null,
                    toFinger: item.finger,
                    distance: 0,
                    direction: DIRECTION.STATIONARY,
                    isStationary: false
                })),
                movementDistance: 0,
                maxMovement: 0,
                sharedNotes: [],
                stationaryNotes: [],
                changedNotes: []
            };
        }

        if (toItems.length === 0) {
            return {
                fromNotes: fromNotes,
                toNotes: [],
                fromMidi: fromMidi,
                toMidi: [],
                movement: fromItems.map(item => ({
                    fromNote: item.note,
                    toNote: null,
                    fromMidi: item.midi,
                    toMidi: null,
                    fromFinger: item.finger,
                    toFinger: null,
                    distance: 0,
                    direction: DIRECTION.STATIONARY,
                    isStationary: false
                })),
                movementDistance: 0,
                maxMovement: 0,
                sharedNotes: [],
                stationaryNotes: [],
                changedNotes: []
            };
        }

        const movements = [];
        let totalDistance = 0;
        let maxDist = 0;
        const stationaryNotes = [];
        const changedNotes = [];

        const pairCount = Math.max(fromItems.length, toItems.length);
        for (let i = 0; i < pairCount; i++) {
            const f = fromItems[i] || null;
            const t = toItems[i] || null;

            if (f && t) {
                const diff = t.midi - f.midi;
                const absDiff = Math.abs(diff);
                totalDistance += absDiff;
                if (absDiff > maxDist) maxDist = absDiff;

                let dir = DIRECTION.STATIONARY;
                if (diff > 0) dir = DIRECTION.UP;
                else if (diff < 0) dir = DIRECTION.DOWN;

                const isStat = (diff === 0);
                if (isStat) {
                    stationaryNotes.push(f.note);
                } else {
                    changedNotes.push({
                        fromNote: f.note,
                        toNote: t.note,
                        fromMidi: f.midi,
                        toMidi: t.midi,
                        distance: diff
                    });
                }

                movements.push({
                    fromNote: f.note,
                    toNote: t.note,
                    fromMidi: f.midi,
                    toMidi: t.midi,
                    fromFinger: f.finger,
                    toFinger: t.finger,
                    distance: diff,
                    direction: dir,
                    isStationary: isStat
                });
            } else if (f && !t) {
                movements.push({
                    fromNote: f.note,
                    toNote: null,
                    fromMidi: f.midi,
                    toMidi: null,
                    fromFinger: f.finger,
                    toFinger: null,
                    distance: 0,
                    direction: DIRECTION.STATIONARY,
                    isStationary: false
                });
            } else if (!f && t) {
                movements.push({
                    fromNote: null,
                    toNote: t.note,
                    fromMidi: null,
                    toMidi: t.midi,
                    fromFinger: null,
                    toFinger: t.finger,
                    distance: 0,
                    direction: DIRECTION.STATIONARY,
                    isStationary: false
                });
            }
        }

        // Also check if any notes in target hand share identical MIDI notes with fromHand (even if voice index differed)
        fromItems.forEach(f => {
            if (toMidi.includes(f.midi) && !stationaryNotes.includes(f.note)) {
                stationaryNotes.push(f.note);
            }
        });

        // Common pitch classes for this hand
        const fromPcs = new Set(fromMidi.map(m => m % 12));
        const toPcs = new Set(toMidi.map(m => m % 12));
        const handSharedPcs = [...fromPcs].filter(pc => toPcs.has(pc));
        const handSharedNotes = handSharedPcs.map(pc => PITCH_NAMES[pc]);

        return {
            fromNotes,
            toNotes,
            fromMidi,
            toMidi,
            movement: movements,
            movementDistance: totalDistance,
            maxMovement: maxDist,
            sharedNotes: handSharedNotes,
            stationaryNotes: Array.from(new Set(stationaryNotes)),
            changedNotes: changedNotes
        };
    }

    /**
     * Determines overall transition difficulty based on measurable physical properties.
     * 
     * Properties:
     * - totalMovement: total semitones moved across both hands
     * - maxMovement: maximum single-note jump in semitones
     * - sharedNotesCount: number of shared pitch classes
     * - stationaryNotesCount: number of exact stationary physical keys
     * - preparationTime: available seconds before next chord
     * 
     * @param {Object} metrics
     * @returns {{ difficulty: string, reason: string }}
     */
    function calculateDifficulty(metrics) {
        const {
            totalMovement,
            maxMovement,
            sharedNotesCount,
            stationaryNotesCount,
            preparationTime,
            isIdentical
        } = metrics;

        if (isIdentical || totalMovement === 0) {
            return {
                difficulty: DIFFICULTY_LEVELS.EASY,
                reason: 'Same chord / zero hand movement required.'
            };
        }

        // Base difficulty score based on max movement (semitones)
        let score = 0;
        if (maxMovement <= 2) {
            score = 1.0;
        } else if (maxMovement <= 4) {
            score = 2.0;
        } else if (maxMovement <= 7) {
            score = 3.0;
        } else if (maxMovement <= 11) {
            score = 4.0;
        } else {
            // Octave leap or larger (>= 12 semitones)
            score = 5.5;
        }

        // Bonus for shared harmonic foundation & stationary anchor fingers
        if (stationaryNotesCount >= 2) {
            score -= 1.0;
        } else if (stationaryNotesCount === 1) {
            score -= 0.5;
        }

        if (sharedNotesCount >= 2) {
            score -= 1.0;
        } else if (sharedNotesCount === 0) {
            score += 0.5;
        }

        // Preparation time modifier (tempo / clock aware)
        if (typeof preparationTime === 'number' && preparationTime > 0) {
            if (preparationTime < 0.6) {
                score += 2.0; // Very rapid switch
            } else if (preparationTime < 1.0) {
                score += 1.0; // Fast switch
            } else if (preparationTime >= 3.0) {
                score -= 1.0; // Generous preparation window
            }
        }

        let difficulty = DIFFICULTY_LEVELS.EASY;
        let reason = 'Minimal hand movement with comfortable finger positioning.';

        if (score > 4.2) {
            difficulty = DIFFICULTY_LEVELS.HARD;
            reason = maxMovement >= 12
                ? `Large hand shift (${maxMovement} semitones jump).`
                : (preparationTime && preparationTime < 0.8
                    ? `Rapid chord switch with ${totalMovement} semitones movement in ${preparationTime.toFixed(2)}s.`
                    : `Complex chord transition requiring wide hand repositioning.`);
        } else if (score >= 2.5) {
            difficulty = DIFFICULTY_LEVELS.MODERATE;
            reason = sharedNotesCount > 0
                ? `Moderate hand shift with anchor finger support (${maxMovement} semitones max shift).`
                : `Moderate hand repositioning (${maxMovement} semitones shift).`;
        }

        return { difficulty, reason };
    }

    const ChordTransitionEngine = {
        DIFFICULTY_LEVELS,
        DIRECTION,

        /**
         * Analyzes the transition between two beginner chord events.
         * 
         * @param {Object|string|null} fromChordInput - Current ChordEvent or chord name
         * @param {Object|string|null} toChordInput - Next ChordEvent or chord name
         * @param {number|Object} [optionsOrTime] - Optional preparation time in seconds or options object
         * @returns {Object} ChordTransition analysis result
         */
        analyzeTransition(fromChordInput, toChordInput, optionsOrTime = null) {
            const engine = resolveFingeringEngine();
            const fromName = extractChordName(fromChordInput);
            const toName = extractChordName(toChordInput);
            const preparationTime = resolvePreparationTime(fromChordInput, toChordInput, optionsOrTime);

            const fromVoicing = (engine && fromName) ? engine.getChordVoicing(fromChordInput) : null;
            const toVoicing = (engine && toName) ? engine.getChordVoicing(toChordInput) : null;

            // Analyze Left and Right Hand Movements
            const leftHand = analyzeSingleHandMovement(
                fromVoicing ? fromVoicing.leftHand : [],
                toVoicing ? toVoicing.leftHand : []
            );

            const rightHand = analyzeSingleHandMovement(
                fromVoicing ? fromVoicing.rightHand : [],
                toVoicing ? toVoicing.rightHand : []
            );

            // Compute global shared pitch classes across voicings
            const allFromMidi = [
                ...(fromVoicing && fromVoicing.leftHand ? fromVoicing.leftHand.map(x => x.midi) : []),
                ...(fromVoicing && fromVoicing.rightHand ? fromVoicing.rightHand.map(x => x.midi) : [])
            ];
            const allToMidi = [
                ...(toVoicing && toVoicing.leftHand ? toVoicing.leftHand.map(x => x.midi) : []),
                ...(toVoicing && toVoicing.rightHand ? toVoicing.rightHand.map(x => x.midi) : [])
            ];

            const fromPcs = new Set(allFromMidi.map(m => m % 12));
            const toPcs = new Set(allToMidi.map(m => m % 12));
            const sharedPcs = [...fromPcs].filter(pc => toPcs.has(pc));
            const commonNotes = sharedPcs.map(pc => PITCH_NAMES[pc]);

            const totalMovement = leftHand.movementDistance + rightHand.movementDistance;
            const maxMovement = Math.max(leftHand.maxMovement, rightHand.maxMovement);
            const isIdentical = Boolean(fromName && toName && fromName === toName);

            const stationaryNotesCount = leftHand.stationaryNotes.length + rightHand.stationaryNotes.length;
            const changedNotesCount = leftHand.changedNotes.length + rightHand.changedNotes.length;

            const { difficulty, reason } = calculateDifficulty({
                totalMovement,
                maxMovement,
                sharedNotesCount: commonNotes.length,
                stationaryNotesCount,
                preparationTime,
                isIdentical
            });

            return {
                fromChord: fromName,
                toChord: toName,
                fromVoicing: fromVoicing,
                toVoicing: toVoicing,

                leftHand: {
                    fromNotes: leftHand.fromNotes,
                    toNotes: leftHand.toNotes,
                    fromMidi: leftHand.fromMidi,
                    toMidi: leftHand.toMidi,
                    movement: leftHand.movement,
                    movementDistance: leftHand.movementDistance,
                    maxMovement: leftHand.maxMovement,
                    sharedNotes: leftHand.sharedNotes,
                    stationaryNotes: leftHand.stationaryNotes,
                    changedNotes: leftHand.changedNotes
                },

                rightHand: {
                    fromNotes: rightHand.fromNotes,
                    toNotes: rightHand.toNotes,
                    fromMidi: rightHand.fromMidi,
                    toMidi: rightHand.toMidi,
                    movement: rightHand.movement,
                    movementDistance: rightHand.movementDistance,
                    maxMovement: rightHand.maxMovement,
                    sharedNotes: rightHand.sharedNotes,
                    stationaryNotes: rightHand.stationaryNotes,
                    changedNotes: rightHand.changedNotes
                },

                difficulty: difficulty,
                difficultyReason: reason,
                preparationTime: preparationTime,
                sharedNotes: commonNotes,
                commonNotes: commonNotes,

                totalMovement: totalMovement,
                maxMovement: maxMovement,
                changedNotesCount: changedNotesCount
            };
        },

        /**
         * Convenience alias for analyzeTransition.
         * @param {Object|string} fromChord
         * @param {Object|string} toChord
         * @param {number|Object} [options]
         * @returns {Object}
         */
        getTransition(fromChord, toChord, options = null) {
            return this.analyzeTransition(fromChord, toChord, options);
        }
    };

    // Export for Browser and Node environments
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = { ChordTransitionEngine, DIFFICULTY_LEVELS, DIRECTION };
    }
    if (typeof window !== 'undefined') {
        window.ChordTransitionEngine = ChordTransitionEngine;
    }
})(typeof globalThis !== 'undefined' ? globalThis : (typeof window !== 'undefined' ? window : this));
