/**
 * musicTheoryFormatter.js
 * Strict normalization for musician-friendly chord naming.
 */

const ENHARMONIC_MAP = {
    'G#': 'Ab', 'G#m': 'Abm', 'G#7': 'Ab7', 'G#maj7': 'Abmaj7', 'G#m7': 'Abm7',
    'D#': 'Eb', 'D#m': 'Ebm', 'D#7': 'Eb7', 'D#maj7': 'Ebmaj7', 'D#m7': 'Ebm7',
    'A#': 'Bb', 'A#m': 'Bbm', 'A#7': 'Bb7', 'A#maj7': 'Bbmaj7', 'A#m7': 'Bbm7',
    'Gb': 'F#', 'Gbm': 'F#m', 'Gb7': 'F#7', 'Gbmaj7': 'F#maj7', 'Gbm7': 'F#m7',
    'Db': 'C#'
};

const MusicTheoryFormatter = {
    normalizeChordName(name) {
        if (!name || name === 'N') return 'N';
        
        // Handle specific rules: Never Gbm, D#m, G# Major
        if (name.startsWith('G#') && !name.includes('m')) return name.replace('G#', 'Ab');
        if (name.startsWith('Gb') && name.includes('m')) return name.replace('Gb', 'F#');
        if (name.startsWith('D#') && name.includes('m')) return name.replace('D#', 'Eb');
        
        return ENHARMONIC_MAP[name] || name;
    },

    getNoteName(index, preferFlats = false) {
        const sharps = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
        const flats = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B'];
        return preferFlats ? flats[index % 12] : sharps[index % 12];
    }
};

window.MusicTheoryFormatter = MusicTheoryFormatter;
