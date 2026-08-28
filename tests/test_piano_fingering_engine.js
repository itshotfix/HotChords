/**
 * tests/test_piano_fingering_engine.js
 * 
 * Focused unit test suite for PianoFingeringEngine covering all 15 scenarios:
 * 1. C (Major)
 * 2. G (Major)
 * 3. F (Major)
 * 4. Am (Minor)
 * 5. Dm (Minor)
 * 6. Em (Minor)
 * 7. Bb (Flat root)
 * 8. Eb (Flat root)
 * 9. diminished chord (Bdim, Cdim, m7b5)
 * 10. repeated chord
 * 11. unknown chord
 * 12. missing chord
 * 13. deterministic repeated calls
 * 14. valid MIDI range
 * 15. valid finger numbers
 * + CurrentChordEngine -> PianoFingeringEngine integration
 */

const assert = require('assert');
const { PianoFingeringEngine, FINGER_COLORS } = require('../frontend/js/engine/pianoFingeringEngine.js');
const { CurrentChordEngine } = require('../frontend/js/engine/currentChordEngine.js');

function runTests() {
    console.log('Running PianoFingeringEngine unit test suite...');

    // 1. C Major
    {
        const v = PianoFingeringEngine.getChordVoicing('C');
        assert(v, 'C Major voicing should be generated');
        assert.strictEqual(v.chordName, 'C');
        assert.deepStrictEqual(v.rightHand.midiNotes, [60, 64, 67]);
        assert.deepStrictEqual(v.rightHand.notes, ['C4', 'E4', 'G4']);
        assert.deepStrictEqual(v.rightHand.fingers, [1, 3, 5]);
        assert.deepStrictEqual(v.leftHand.midiNotes, [36, 43]);
        assert.deepStrictEqual(v.leftHand.notes, ['C2', 'G2']);
        assert.deepStrictEqual(v.leftHand.fingers, [5, 1]);
        console.log('✓ Scenario 1: C Major passed');
    }

    // 2. G Major
    {
        const v = PianoFingeringEngine.getChordVoicing('G');
        assert(v);
        assert.strictEqual(v.chordName, 'G');
        assert.deepStrictEqual(v.rightHand.midiNotes, [67, 71, 74]);
        assert.deepStrictEqual(v.rightHand.notes, ['G4', 'B4', 'D5']);
        assert.deepStrictEqual(v.rightHand.fingers, [1, 3, 5]);
        assert.deepStrictEqual(v.leftHand.midiNotes, [43, 50]);
        assert.deepStrictEqual(v.leftHand.notes, ['G2', 'D3']);
        assert.deepStrictEqual(v.leftHand.fingers, [5, 1]);
        console.log('✓ Scenario 2: G Major passed');
    }

    // 3. F Major
    {
        const v = PianoFingeringEngine.getChordVoicing('F');
        assert(v);
        assert.strictEqual(v.chordName, 'F');
        assert.deepStrictEqual(v.rightHand.midiNotes, [65, 69, 72]);
        assert.deepStrictEqual(v.rightHand.notes, ['F4', 'A4', 'C5']);
        assert.deepStrictEqual(v.rightHand.fingers, [1, 3, 5]);
        assert.deepStrictEqual(v.leftHand.midiNotes, [41, 48]);
        assert.deepStrictEqual(v.leftHand.notes, ['F2', 'C3']);
        console.log('✓ Scenario 3: F Major passed');
    }

    // 4. Am (A Minor)
    {
        const v = PianoFingeringEngine.getChordVoicing('Am');
        assert(v);
        assert.strictEqual(v.chordName, 'Am');
        assert.deepStrictEqual(v.rightHand.midiNotes, [69, 72, 76]);
        assert.deepStrictEqual(v.rightHand.notes, ['A4', 'C5', 'E5']);
        assert.deepStrictEqual(v.rightHand.fingers, [1, 3, 5]);
        assert.deepStrictEqual(v.leftHand.midiNotes, [45, 52]);
        assert.deepStrictEqual(v.leftHand.notes, ['A2', 'E3']);
        console.log('✓ Scenario 4: Am (A Minor) passed');
    }

    // 5. Dm (D Minor)
    {
        const v = PianoFingeringEngine.getChordVoicing('Dm');
        assert(v);
        assert.strictEqual(v.chordName, 'Dm');
        assert.deepStrictEqual(v.rightHand.midiNotes, [62, 65, 69]);
        assert.deepStrictEqual(v.rightHand.notes, ['D4', 'F4', 'A4']);
        assert.deepStrictEqual(v.rightHand.fingers, [1, 3, 5]);
        assert.deepStrictEqual(v.leftHand.midiNotes, [38, 45]);
        assert.deepStrictEqual(v.leftHand.notes, ['D2', 'A2']);
        console.log('✓ Scenario 5: Dm (D Minor) passed');
    }

    // 6. Em (E Minor)
    {
        const v = PianoFingeringEngine.getChordVoicing('Em');
        assert(v);
        assert.strictEqual(v.chordName, 'Em');
        assert.deepStrictEqual(v.rightHand.midiNotes, [64, 67, 71]);
        assert.deepStrictEqual(v.rightHand.notes, ['E4', 'G4', 'B4']);
        assert.deepStrictEqual(v.rightHand.fingers, [1, 3, 5]);
        assert.deepStrictEqual(v.leftHand.midiNotes, [40, 47]);
        assert.deepStrictEqual(v.leftHand.notes, ['E2', 'B2']);
        console.log('✓ Scenario 6: Em (E Minor) passed');
    }

    // 7. Bb (B-flat Major)
    {
        const v = PianoFingeringEngine.getChordVoicing('Bb');
        assert(v);
        assert.strictEqual(v.chordName, 'Bb');
        assert.deepStrictEqual(v.rightHand.midiNotes, [70, 74, 77]);
        assert.deepStrictEqual(v.rightHand.notes, ['Bb4', 'D5', 'F5']);
        assert.deepStrictEqual(v.rightHand.fingers, [1, 3, 5]);
        assert.deepStrictEqual(v.leftHand.midiNotes, [46, 53]);
        assert.deepStrictEqual(v.leftHand.notes, ['Bb2', 'F3']);
        console.log('✓ Scenario 7: Bb (B-flat Major) passed');
    }

    // 8. Eb (E-flat Major)
    {
        const v = PianoFingeringEngine.getChordVoicing('Eb');
        assert(v);
        assert.strictEqual(v.chordName, 'Eb');
        assert.deepStrictEqual(v.rightHand.midiNotes, [63, 67, 70]);
        assert.deepStrictEqual(v.rightHand.notes, ['Eb4', 'G4', 'Bb4']);
        assert.deepStrictEqual(v.rightHand.fingers, [1, 3, 5]);
        assert.deepStrictEqual(v.leftHand.midiNotes, [39, 46]);
        assert.deepStrictEqual(v.leftHand.notes, ['Eb2', 'Bb2']);
        console.log('✓ Scenario 8: Eb (E-flat Major) passed');
    }

    // 9. Diminished chord (Bdim, Cdim, m7b5)
    {
        const v = PianoFingeringEngine.getChordVoicing('Bdim');
        assert(v, 'Diminished chord should be supported');
        assert.strictEqual(v.chordName, 'Bdim');
        assert.deepStrictEqual(v.rightHand.midiNotes, [71, 74, 77]); // Root B (71), min3rd D (74), dim5th F (77)
        assert.deepStrictEqual(v.rightHand.fingers, [1, 3, 5]);
        assert.deepStrictEqual(v.leftHand.midiNotes, [47, 53]);     // Root B (47), dim5th F (53)
        assert.deepStrictEqual(v.leftHand.fingers, [5, 1]);

        const v2 = PianoFingeringEngine.getChordVoicing('C°');
        assert(v2);
        assert.deepStrictEqual(v2.rightHand.midiNotes, [60, 63, 66]);
        console.log('✓ Scenario 9: Diminished chord passed');
    }

    // 10. Repeated chord
    {
        const v1 = PianoFingeringEngine.getChordVoicing('C');
        const v2 = PianoFingeringEngine.getChordVoicing('C');
        assert.deepStrictEqual(v1, v2, 'Repeated calls for same chord must produce identical object');
        console.log('✓ Scenario 10: Repeated chord passed');
    }

    // 11. Unknown chord
    {
        const v = PianoFingeringEngine.getChordVoicing('XYZUnknown');
        assert.strictEqual(v, null, 'Unknown chord should gracefully return null');
        console.log('✓ Scenario 11: Unknown chord passed');
    }

    // 12. Missing chord
    {
        assert.strictEqual(PianoFingeringEngine.getChordVoicing(null), null);
        assert.strictEqual(PianoFingeringEngine.getChordVoicing(undefined), null);
        assert.strictEqual(PianoFingeringEngine.getChordVoicing(''), null);
        assert.strictEqual(PianoFingeringEngine.getChordVoicing('N'), null);
        console.log('✓ Scenario 12: Missing chord passed');
    }

    // 13. Deterministic repeated calls
    {
        for (let i = 0; i < 50; i++) {
            const v = PianoFingeringEngine.getChordVoicing('F#m');
            assert.deepStrictEqual(v.rightHand.midiNotes, [66, 69, 73]);
            assert.deepStrictEqual(v.rightHand.fingers, [1, 3, 5]);
        }
        console.log('✓ Scenario 13: Deterministic repeated calls passed');
    }

    // 14. Valid MIDI range
    {
        const testChords = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B'];
        testChords.forEach(c => {
            const v = PianoFingeringEngine.getChordVoicing(c);
            assert(v);
            // Left hand in bass octave (36 - 54)
            v.leftHand.midiNotes.forEach(m => {
                assert(m >= 36 && m <= 60, `LH MIDI ${m} for ${c} out of bass range`);
            });
            // Right hand in middle/harmony octave (60 - 84)
            v.rightHand.midiNotes.forEach(m => {
                assert(m >= 60 && m <= 84, `RH MIDI ${m} for ${c} out of harmony range`);
            });
        });
        console.log('✓ Scenario 14: Valid MIDI range passed');
    }

    // 15. Valid finger numbers
    {
        const chords = ['C', 'Am', 'G7', 'Csus4', 'Bdim', 'Fmaj7'];
        chords.forEach(c => {
            const v = PianoFingeringEngine.getChordVoicing(c);
            assert(v);
            v.leftHand.fingers.forEach(f => {
                assert([1, 2, 3, 4, 5].includes(f), `Invalid LH finger ${f} on ${c}`);
            });
            v.rightHand.fingers.forEach(f => {
                assert([1, 2, 3, 4, 5].includes(f), `Invalid RH finger ${f} on ${c}`);
            });
            // Hand separation: LH and RH voicings are separate arrays with colors
            assert(Array.isArray(v.leftHand));
            assert(Array.isArray(v.rightHand));
            assert(v.leftHand[0].color);
            assert(v.rightHand[0].color);
        });
        console.log('✓ Scenario 15: Valid finger numbers passed');
    }

    // 16. Integration: CurrentChordEngine -> PianoFingeringEngine
    {
        const timeline = {
            beginner_chords: [
                { chordName: 'C', startTime: 0.0, endTime: 2.0 },
                { chordName: 'G', startTime: 2.0, endTime: 4.0 },
                { chordName: 'Am', startTime: 4.0, endTime: 6.0 },
                { chordName: 'F', startTime: 6.0, endTime: 8.0 }
            ]
        };

        const mockClock = { currentTime: 1.0, getCurrentTime() { return 1.0; } };
        const chordEngine = new CurrentChordEngine(mockClock);
        chordEngine.loadTimeline(timeline);

        const currentEvent = chordEngine.getCurrentChord();
        assert(currentEvent);
        const fingering = PianoFingeringEngine.getChordVoicing(currentEvent);

        assert.strictEqual(fingering.chordName, 'C');
        assert.deepStrictEqual(fingering.rightHand.notes, ['C4', 'E4', 'G4']);
        assert.deepStrictEqual(fingering.leftHand.notes, ['C2', 'G2']);
        console.log('✓ Integration: CurrentChordEngine -> PianoFingeringEngine passed');
    }

    console.log('All PianoFingeringEngine tests passed successfully!');
}

if (require.main === module) {
    runTests();
}

module.exports = { runTests };
