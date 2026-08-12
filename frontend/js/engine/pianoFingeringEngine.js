/**
 * pianoFingeringEngine.js
 * Production-quality pedagogical fingering engine.
 * 
 * Philosophy: ONE VOICING PER HAND
 * Instead of computing complex dynamic voice leading, this engine locks
 * the left hand to the bass/power octave (Octave 2) and the right hand
 * to the harmony octave (Octave 4). This guarantees consistent, playable
 * fingerings for beginners.
 */

const FINGER_COLORS = {
    1: '#FF4D4F', // Thumb
    2: '#FAAD14', // Index
    3: '#52C41A', // Middle
    4: '#13C2C2', // Ring
    5: '#1677FF'  // Pinky
};

const FINGERING_DB = {
    'TRIAD': {
        RH: [1, 3, 5],        // Thumb, Middle, Pinky (Standard closed position)
        LH: [5, 3, 1],        // Pinky, Middle, Thumb
        VOICING_RH: [0, 4, 7], // Root, 3rd, 5th
        VOICING_LH: [0, 7]     // Power chord (Root, 5th) in bass
    },
    'SEVENTH': {
        RH: [1, 2, 3, 5],
        LH: [5, 2, 1],
        VOICING_RH: [0, 4, 7, 10],
        VOICING_LH: [0, 10]
    },
    'SUS2': {
        RH: [1, 2, 5],
        LH: [5, 4, 1],
        VOICING_RH: [0, 2, 7],
        VOICING_LH: [0, 7]
    },
    'SUS4': {
        RH: [1, 4, 5],
        LH: [5, 2, 1],
        VOICING_RH: [0, 5, 7],
        VOICING_LH: [0, 7]
    }
};

const PianoFingeringEngine = {
    getFINGER_COLORS() { return FINGER_COLORS; },

    getChordVoicing(chordName, notes) {
        if (!chordName || chordName === 'N' || !notes || notes.length === 0) return null;

        const lower = chordName.toLowerCase();
        let type = 'TRIAD';
        if (lower.includes('7')) type = 'SEVENTH';
        else if (lower.includes('sus2')) type = 'SUS2';
        else if (lower.includes('sus4')) type = 'SUS4';

        const isMinor = lower.includes('m') && !lower.includes('maj');
        const config = FINGERING_DB[type] || FINGERING_DB['TRIAD'];
        const root = notes[0];

        const lhVoicing = [];
        const rhVoicing = [];

        // Right Hand: Middle Octave (Octave 4, MIDI 60 is Middle C)
        // Provides harmonic clarity in a comfortable range.
        config.VOICING_RH.forEach((interval, i) => {
            let actualInterval = interval;
            // Automatically flatten the 3rd for minor chords
            if (isMinor && interval === 4) actualInterval = 3;
            const midi = 60 + ((root + actualInterval) % 12);
            rhVoicing.push({ midi, finger: config.RH[i], color: FINGER_COLORS[config.RH[i]] });
        });

        // Left Hand: Lower Octave (Octave 2, MIDI 36 is C2)
        // Provides bass support without muddying the midrange.
        config.VOICING_LH.forEach((interval, i) => {
            const midi = 36 + ((root + interval) % 12);
            lhVoicing.push({ midi, finger: config.LH[i], color: FINGER_COLORS[config.LH[i]] });
        });

        return { chordName, leftHand: lhVoicing, rightHand: rhVoicing };
    }
};

window.PianoFingeringEngine = PianoFingeringEngine;
