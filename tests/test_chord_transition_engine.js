/**
 * tests/test_chord_transition_engine.js
 * 
 * Focused unit test suite for ChordTransitionEngine (Phase 6C) covering all required scenarios:
 * 1. C -> G
 * 2. G -> C
 * 3. C -> Am
 * 4. Am -> F
 * 5. F -> G
 * 6. repeated C -> C
 * 7. shared-note transition
 * 8. no-shared-note transition
 * 9. large octave movement
 * 10. short preparation time
 * 11. long preparation time
 * 12. missing current chord / missing next chord
 * 13. identical MIDI voicing
 * 14. unsupported chord fallback
 * 15. deterministic repeated calls
 * 16. immutability check (zero mutation of ChordEvents)
 */

const assert = require('assert');
const { ChordTransitionEngine, DIFFICULTY_LEVELS, DIRECTION } = require('../frontend/js/engine/chordTransitionEngine.js');
const { PianoFingeringEngine } = require('../frontend/js/engine/pianoFingeringEngine.js');

function runTests() {
    console.log('Running ChordTransitionEngine unit test suite...');

    // 1. C -> G
    {
        const trans = ChordTransitionEngine.analyzeTransition('C', 'G');
        assert(trans, 'C -> G transition should be generated');
        assert.strictEqual(trans.fromChord, 'C');
        assert.strictEqual(trans.toChord, 'G');
        
        // RH: C4,E4,G4 (60,64,67) -> G4,B4,D5 (67,71,74)
        assert.deepStrictEqual(trans.rightHand.fromNotes, ['C4', 'E4', 'G4']);
        assert.deepStrictEqual(trans.rightHand.toNotes, ['G4', 'B4', 'D5']);
        assert.strictEqual(trans.rightHand.maxMovement, 7); // +7 semitones
        assert(trans.rightHand.stationaryNotes.includes('G4'));
        
        // LH: C2,G2 (36,43) -> G2,D3 (43,50)
        assert.deepStrictEqual(trans.leftHand.fromNotes, ['C2', 'G2']);
        assert.deepStrictEqual(trans.leftHand.toNotes, ['G2', 'D3']);
        assert(trans.leftHand.stationaryNotes.includes('G2'));

        // Shared pitch class G
        assert(trans.sharedNotes.includes('G'));
        assert(trans.commonNotes.includes('G'));
        assert(['EASY', 'MODERATE'].includes(trans.difficulty));
        console.log('✓ Scenario 1: C -> G passed');
    }

    // 2. G -> C
    {
        const trans = ChordTransitionEngine.analyzeTransition('G', 'C');
        assert(trans);
        assert.strictEqual(trans.fromChord, 'G');
        assert.strictEqual(trans.toChord, 'C');
        assert.strictEqual(trans.rightHand.movement[0].direction, DIRECTION.DOWN); // G4 -> C4 (-7)
        assert(trans.sharedNotes.includes('G'));
        console.log('✓ Scenario 2: G -> C passed');
    }

    // 3. C -> Am
    {
        const trans = ChordTransitionEngine.analyzeTransition('C', 'Am');
        assert(trans);
        assert.strictEqual(trans.fromChord, 'C');
        assert.strictEqual(trans.toChord, 'Am');
        
        // Pitch classes shared: C and E
        assert(trans.sharedNotes.includes('C'));
        assert(trans.sharedNotes.includes('E'));
        assert.strictEqual(trans.commonNotes.length >= 2, true);
        console.log('✓ Scenario 3: C -> Am passed');
    }

    // 4. Am -> F
    {
        const trans = ChordTransitionEngine.analyzeTransition('Am', 'F');
        assert(trans);
        assert.strictEqual(trans.fromChord, 'Am');
        assert.strictEqual(trans.toChord, 'F');
        
        // Am (A4=69, C5=72, E5=76) -> F (F4=65, A4=69, C5=72)
        // Shared pitch classes: A and C
        assert(trans.sharedNotes.includes('A'));
        assert(trans.sharedNotes.includes('C'));
        // Exact stationary MIDI keys: A4 (69) and C5 (72)
        assert(trans.rightHand.stationaryNotes.includes('A4') || trans.rightHand.stationaryNotes.includes('C5'));
        assert.strictEqual(trans.difficulty, DIFFICULTY_LEVELS.EASY);
        console.log('✓ Scenario 4: Am -> F passed');
    }

    // 5. F -> G
    {
        const trans = ChordTransitionEngine.analyzeTransition('F', 'G');
        assert(trans);
        assert.strictEqual(trans.fromChord, 'F');
        assert.strictEqual(trans.toChord, 'G');
        
        // Parallel shift up by 2 semitones
        assert.strictEqual(trans.rightHand.movement[0].distance, 2);
        assert.strictEqual(trans.rightHand.movement[0].direction, DIRECTION.UP);
        assert.strictEqual(trans.leftHand.movement[0].distance, 2);
        assert.strictEqual(trans.sharedNotes.length, 0); // No shared notes between F and G
        assert.strictEqual(trans.difficulty, DIFFICULTY_LEVELS.EASY);
        console.log('✓ Scenario 5: F -> G passed');
    }

    // 6. Repeated C -> C (same chord -> same chord)
    {
        const trans = ChordTransitionEngine.analyzeTransition('C', 'C');
        assert(trans);
        assert.strictEqual(trans.fromChord, 'C');
        assert.strictEqual(trans.toChord, 'C');
        assert.strictEqual(trans.totalMovement, 0);
        assert.strictEqual(trans.maxMovement, 0);
        assert.strictEqual(trans.difficulty, DIFFICULTY_LEVELS.EASY);
        assert.strictEqual(trans.rightHand.stationaryNotes.length, 3);
        assert.strictEqual(trans.leftHand.stationaryNotes.length, 2);
        console.log('✓ Scenario 6: Repeated C -> C passed');
    }

    // 7. Chords with shared notes (e.g. C -> Em)
    {
        const trans = ChordTransitionEngine.analyzeTransition('C', 'Em');
        assert(trans);
        // C (C,E,G) and Em (E,G,B) share E and G
        assert(trans.sharedNotes.includes('E'));
        assert(trans.sharedNotes.includes('G'));
        assert(trans.rightHand.stationaryNotes.includes('E4'));
        assert(trans.rightHand.stationaryNotes.includes('G4'));
        console.log('✓ Scenario 7: Chords with shared notes passed');
    }

    // 8. Chords with no shared notes (e.g. B -> C)
    {
        const trans = ChordTransitionEngine.analyzeTransition('B', 'C');
        assert(trans);
        assert.strictEqual(trans.sharedNotes.length, 0);
        assert.strictEqual(trans.leftHand.stationaryNotes.length, 0);
        assert.strictEqual(trans.rightHand.stationaryNotes.length, 0);
        console.log('✓ Scenario 8: Chords with no shared notes passed');
    }

    // 9. Large octave / wide movement
    {
        const trans = ChordTransitionEngine.analyzeTransition('C', 'B');
        assert(trans);
        // Root shifts from 0 (C) to 11 (B), +11 semitones
        assert(trans.maxMovement >= 11);
        console.log('✓ Scenario 9: Large movement passed');
    }

    // 10. Short preparation time escalation
    {
        const normalTrans = ChordTransitionEngine.analyzeTransition('C', 'G', { availableTimeSeconds: 2.0 });
        const rapidTrans = ChordTransitionEngine.analyzeTransition('C', 'G', { availableTimeSeconds: 0.4 });
        
        assert(normalTrans);
        assert(rapidTrans);
        assert.strictEqual(rapidTrans.preparationTime, 0.4);
        // Rapid transition should be classified as harder due to time pressure
        assert(['MODERATE', 'HARD'].includes(rapidTrans.difficulty));
        console.log('✓ Scenario 10: Short preparation time passed');
    }

    // 11. Long preparation time
    {
        const generousTrans = ChordTransitionEngine.analyzeTransition('C', 'G', { availableTimeSeconds: 4.0 });
        assert(generousTrans);
        assert.strictEqual(generousTrans.preparationTime, 4.0);
        assert.strictEqual(generousTrans.difficulty, DIFFICULTY_LEVELS.EASY);
        console.log('✓ Scenario 11: Long preparation time passed');
    }

    // 12. Missing current chord / missing next chord
    {
        const introTrans = ChordTransitionEngine.analyzeTransition(null, 'C');
        assert(introTrans);
        assert.strictEqual(introTrans.fromChord, null);
        assert.strictEqual(introTrans.toChord, 'C');
        assert.deepStrictEqual(introTrans.leftHand.toNotes, ['C2', 'G2']);

        const outroTrans = ChordTransitionEngine.analyzeTransition('C', null);
        assert(outroTrans);
        assert.strictEqual(outroTrans.fromChord, 'C');
        assert.strictEqual(outroTrans.toChord, null);
        assert.deepStrictEqual(outroTrans.leftHand.fromNotes, ['C2', 'G2']);

        const emptyTrans = ChordTransitionEngine.analyzeTransition(null, null);
        assert(emptyTrans);
        assert.strictEqual(emptyTrans.fromChord, null);
        assert.strictEqual(emptyTrans.toChord, null);
        console.log('✓ Scenario 12: Missing chord passed');
    }

    // 13. Identical MIDI voicing
    {
        const chordA = { chordName: 'C', startTime: 0, endTime: 2 };
        const chordB = { chordName: 'C', startTime: 2, endTime: 4 };
        const trans = ChordTransitionEngine.analyzeTransition(chordA, chordB);
        assert.strictEqual(trans.totalMovement, 0);
        assert.strictEqual(trans.difficulty, DIFFICULTY_LEVELS.EASY);
        console.log('✓ Scenario 13: Identical MIDI voicing passed');
    }

    // 14. Unsupported chord fallback
    {
        const trans = ChordTransitionEngine.analyzeTransition('UnknownChordX', 'C');
        assert(trans);
        assert.strictEqual(trans.fromVoicing, null);
        assert(trans.toVoicing);
        console.log('✓ Scenario 14: Unsupported chord fallback passed');
    }

    // 15. Deterministic repeated calls
    {
        for (let i = 0; i < 50; i++) {
            const t1 = ChordTransitionEngine.analyzeTransition('Am', 'F', 1.5);
            assert.strictEqual(t1.difficulty, DIFFICULTY_LEVELS.EASY);
            assert.strictEqual(t1.totalMovement, 19);
            assert.deepStrictEqual(t1.sharedNotes, ['A', 'C']);
        }
        console.log('✓ Scenario 15: Deterministic repeated calls passed');
    }

    // 16. Immutability check
    {
        const chord1 = Object.freeze({ chordName: 'C', startTime: 0.0, endTime: 2.0 });
        const chord2 = Object.freeze({ chordName: 'G', startTime: 2.0, endTime: 4.0 });
        assert.doesNotThrow(() => {
            ChordTransitionEngine.analyzeTransition(chord1, chord2);
        }, 'Engine must not mutate ChordEvent inputs');
        console.log('✓ Scenario 16: Immutability check passed');
    }

    console.log('All ChordTransitionEngine tests passed successfully!');
}

if (require.main === module) {
    runTests();
}

module.exports = { runTests };
