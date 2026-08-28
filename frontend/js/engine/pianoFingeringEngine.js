/**
 * pianoFingeringEngine.js
 * 
 * Production Pedagogical Piano Fingering Engine for HotChords Phase 6B.
 * 
 * Philosophy: ONE VOICING PER HAND (Deterministic Beginner Standard)
 * - Left Hand: Bass root + 5th power foundation in Octave 2 (MIDI 36-47 base).
 * - Right Hand: Harmonic triad / 7th in comfortable Middle Octave (Octave 4, MIDI 60-71 base).
 * 
 * Responsibilities:
 * - Consumes a beginner ChordEvent (or chordName string) and produces a deterministic playable representation.
 * - Provides note names, MIDI notes, finger numbers (1=Thumb..5=Pinky), and finger colors.
 * - Zero random behavior, zero mutations of SongTimeline.
 */

(function(global) {
    'use strict';

    const FINGER_COLORS = Object.freeze({
        1: '#FF4D4F', // Thumb (Red)
        2: '#FAAD14', // Index (Orange/Yellow)
        3: '#52C41A', // Middle (Green)
        4: '#13C2C2', // Ring (Cyan)
        5: '#1677FF'  // Pinky (Blue)
    });

    const SHARP_NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
    const FLAT_NOTE_NAMES  = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B'];

    const FINGERING_DB = Object.freeze({
        'TRIAD_MAJOR': {
            RH: [1, 3, 5],
            LH: [5, 1],
            VOICING_RH: [0, 4, 7],
            VOICING_LH: [0, 7]
        },
        'TRIAD_MINOR': {
            RH: [1, 3, 5],
            LH: [5, 1],
            VOICING_RH: [0, 3, 7],
            VOICING_LH: [0, 7]
        },
        'TRIAD_DIM': {
            RH: [1, 3, 5],
            LH: [5, 1],
            VOICING_RH: [0, 3, 6],
            VOICING_LH: [0, 6]
        },
        'SUS2': {
            RH: [1, 2, 5],
            LH: [5, 1],
            VOICING_RH: [0, 2, 7],
            VOICING_LH: [0, 7]
        },
        'SUS4': {
            RH: [1, 4, 5],
            LH: [5, 1],
            VOICING_RH: [0, 5, 7],
            VOICING_LH: [0, 7]
        },
        'SEVENTH_DOM': {
            RH: [1, 2, 3, 5],
            LH: [5, 1],
            VOICING_RH: [0, 4, 7, 10],
            VOICING_LH: [0, 10]
        },
        'SEVENTH_MAJ': {
            RH: [1, 2, 3, 5],
            LH: [5, 1],
            VOICING_RH: [0, 4, 7, 11],
            VOICING_LH: [0, 7]
        },
        'SEVENTH_MIN': {
            RH: [1, 2, 3, 5],
            LH: [5, 1],
            VOICING_RH: [0, 3, 7, 10],
            VOICING_LH: [0, 10]
        },
        'SINGLE_NOTE': {
            RH: [1],
            LH: [5],
            VOICING_RH: [0],
            VOICING_LH: [0]
        }
    });

    /**
     * Resolves root pitch class (0-11) from chord name.
     * @param {string} chordName
     * @returns {{ rootPc: number, preferFlats: boolean }|null}
     */
    function parseRootFromChordName(chordName) {
        if (!chordName || typeof chordName !== 'string') return null;
        const clean = chordName.trim();
        if (!clean || clean === 'N' || clean === 'null' || clean === 'undefined') return null;

        const match = clean.match(/^([A-Ga-g][#b]?)/);
        if (!match) return null;

        let root = match[1];
        root = root.charAt(0).toUpperCase() + root.slice(1);

        let idx = FLAT_NOTE_NAMES.indexOf(root);
        let preferFlats = true;
        if (idx === -1) {
            idx = SHARP_NOTE_NAMES.indexOf(root);
            preferFlats = false;
        } else if (root.includes('#')) {
            preferFlats = false;
        } else if (root.includes('b')) {
            preferFlats = true;
        } else {
            // Default natural roots
            preferFlats = ['F', 'Bb', 'Eb', 'Ab', 'Db'].includes(root);
        }

        if (idx === -1) return null;
        return { rootPc: idx, preferFlats };
    }

    /**
     * Determines chord fingering configuration key from chord symbol.
     * @param {string} chordName
     * @returns {string}
     */
    function getFingeringConfigKey(chordName) {
        if (!chordName || typeof chordName !== 'string') return 'TRIAD_MAJOR';
        const lower = chordName.toLowerCase().replace(/^[a-g][#b]?/, '');

        if (lower.includes('dim') || lower.includes('°') || lower.includes('m7b5') || lower.includes('o')) {
            return 'TRIAD_DIM';
        }
        if (lower.includes('sus2')) {
            return 'SUS2';
        }
        if (lower.includes('sus4') || lower.includes('sus')) {
            return 'SUS4';
        }
        if (lower.includes('maj7') || lower.includes('m7+')) {
            return 'SEVENTH_MAJ';
        }
        if (lower.includes('m7') || lower.includes('min7')) {
            return 'SEVENTH_MIN';
        }
        if (lower.includes('7')) {
            return 'SEVENTH_DOM';
        }
        if (lower.includes('m') || lower.includes('min') || lower.includes('-')) {
            return 'TRIAD_MINOR';
        }
        return 'TRIAD_MAJOR';
    }

    /**
     * Converts MIDI note number to standardized Note Name (e.g. 60 -> 'C4', 70 -> 'Bb4').
     * @param {number} midi
     * @param {boolean} preferFlats
     * @returns {string}
     */
    function midiToNoteName(midi, preferFlats = false) {
        const noteNum = Math.floor(midi);
        const pitch = noteNum % 12;
        const octave = Math.floor(noteNum / 12) - 1;
        const nameTable = preferFlats ? FLAT_NOTE_NAMES : SHARP_NOTE_NAMES;
        return `${nameTable[pitch]}${octave}`;
    }

    /**
     * Packages a hand voicing array with metadata properties.
     * @param {Array} items
     * @returns {Array}
     */
    function createHandVoicingArray(items) {
        const arr = [...items];
        arr.notes = items.map(x => x.note);
        arr.midiNotes = items.map(x => x.midi);
        arr.fingers = items.map(x => x.finger);
        arr.colors = items.map(x => x.color);
        return arr;
    }

    const PianoFingeringEngine = {
        getFINGER_COLORS() {
            return FINGER_COLORS;
        },

        midiToNoteName(midi, preferFlats = false) {
            return midiToNoteName(midi, preferFlats);
        },

        /**
         * Resolves chord input to standard string name and pitch classes.
         * Accepts a ChordEvent object, legacy chord dict, or string name.
         * @param {Object|string} chordInput
         * @param {Array<number>} [explicitNotes]
         * @returns {{ chordName: string, notes: Array<number>|null }|null}
         */
        parseChordInput(chordInput, explicitNotes = null) {
            if (!chordInput) return null;

            let chordName = '';
            let notes = Array.isArray(explicitNotes) && explicitNotes.length > 0 ? explicitNotes : null;

            if (typeof chordInput === 'string') {
                chordName = chordInput.trim();
            } else if (typeof chordInput === 'object') {
                chordName = chordInput.chordName || chordInput.chord || chordInput.name || '';
                if (!notes && Array.isArray(chordInput.notes) && chordInput.notes.length > 0) {
                    notes = chordInput.notes;
                }
            }

            if (!chordName || chordName === 'N' || chordName === 'null') return null;

            // Normalize enharmonics if MusicTheoryFormatter is available
            if (global && global.MusicTheoryFormatter && typeof global.MusicTheoryFormatter.normalizeChordName === 'function') {
                chordName = global.MusicTheoryFormatter.normalizeChordName(chordName);
            }

            return { chordName, notes };
        },

        /**
         * Primary Fingering API:
         * Consumes a beginner ChordEvent (or chordName + notes) and produces a deterministic playable representation.
         * 
         * @param {Object|string} chordInput - ChordEvent, chord dict, or chord symbol string (e.g. 'C', 'Am', 'Bb')
         * @param {Array<number>} [notes] - Optional array of pitch classes [0, 4, 7]
         * @returns {Object|null} Deterministic hand voicing and fingering configuration
         */
        getChordVoicing(chordInput, notes = null) {
            const parsed = this.parseChordInput(chordInput, notes);
            if (!parsed) return null;

            const { chordName } = parsed;
            const rootInfo = parseRootFromChordName(chordName);
            if (!rootInfo) return null;

            const { rootPc, preferFlats } = rootInfo;
            let configKey = getFingeringConfigKey(chordName);

            // Handle explicit single-note / bass case
            if (parsed.notes && parsed.notes.length === 1) {
                configKey = 'SINGLE_NOTE';
            }

            const config = FINGERING_DB[configKey] || FINGERING_DB['TRIAD_MAJOR'];

            // 1. Right Hand Voicing: Middle Octave 4 (MIDI 60-71 base)
            const rhItems = [];
            config.VOICING_RH.forEach((interval, i) => {
                const midi = 60 + rootPc + interval;
                const finger = config.RH[i];
                rhItems.push({
                    note: midiToNoteName(midi, preferFlats),
                    midi: midi,
                    finger: finger,
                    color: FINGER_COLORS[finger]
                });
            });

            // 2. Left Hand Voicing: Lower Octave 2 (MIDI 36-47 base)
            const lhItems = [];
            config.VOICING_LH.forEach((interval, i) => {
                const midi = 36 + rootPc + interval;
                const finger = config.LH[i];
                lhItems.push({
                    note: midiToNoteName(midi, preferFlats),
                    midi: midi,
                    finger: finger,
                    color: FINGER_COLORS[finger]
                });
            });

            const leftHandVoicing = createHandVoicingArray(lhItems);
            const rightHandVoicing = createHandVoicingArray(rhItems);

            return {
                chordName: chordName,
                leftHand: leftHandVoicing,
                rightHand: rightHandVoicing
            };
        },

        /**
         * Convenience alias for getChordVoicing.
         * @param {Object|string} chordInput
         * @param {Array<number>} [notes]
         * @returns {Object|null}
         */
        getFingering(chordInput, notes = null) {
            return this.getChordVoicing(chordInput, notes);
        }
    };

    // Export for Browser and Node environments
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = { PianoFingeringEngine, FINGER_COLORS, FINGERING_DB };
    }
    if (typeof window !== 'undefined') {
        window.PianoFingeringEngine = PianoFingeringEngine;
    }
})(typeof globalThis !== 'undefined' ? globalThis : (typeof window !== 'undefined' ? window : this));
