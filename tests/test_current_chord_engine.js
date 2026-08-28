/**
 * tests/test_current_chord_engine.js
 * 
 * Focused unit test suite for CurrentChordEngine covering all 15 scenarios:
 * 1. empty timeline
 * 2. first chord
 * 3. middle chord
 * 4. exact chord boundary
 * 5. final chord
 * 6. before first chord
 * 7. after final chord
 * 8. time remaining
 * 9. progress
 * 10. anticipation threshold
 * 11. previous chord
 * 12. next chord
 * 13. repeated identical chords
 * 14. timeline replacement
 * 15. clear()
 */

const assert = require('assert');
const { CurrentChordEngine } = require('../frontend/js/engine/currentChordEngine.js');

function createMockClock(initialTime = 0.0) {
    let currentTime = initialTime;
    return {
        get currentTime() { return currentTime; },
        getCurrentTime() { return currentTime; },
        setTime(t) { currentTime = t; }
    };
}

function runTests() {
    console.log('Running CurrentChordEngine unit test suite...');

    const sampleTimeline = {
        beginner_chords: [
            { chordName: 'C', startTime: 0.0, endTime: 2.0 },
            { chordName: 'G', startTime: 2.0, endTime: 4.0 },
            { chordName: 'Am', startTime: 4.0, endTime: 6.0 },
            { chordName: 'F', startTime: 6.0, endTime: 8.0 }
        ]
    };

    // 1. Empty timeline
    {
        const clock = createMockClock(1.0);
        const engine = new CurrentChordEngine(clock);
        assert.strictEqual(engine.getCurrentChord(), null, 'Empty timeline should return null for current chord');
        assert.strictEqual(engine.getNextChord(), null, 'Empty timeline should return null for next chord');
        assert.strictEqual(engine.getPreviousChord(), null, 'Empty timeline should return null for previous chord');
        assert.strictEqual(engine.getCurrentChordIndex(), -1, 'Empty timeline should return -1 for chord index');
        assert.strictEqual(engine.getTimeRemaining(), 0, 'Empty timeline should return 0 for time remaining');
        assert.strictEqual(engine.getTimeIntoChord(), 0, 'Empty timeline should return 0 for time into chord');
        assert.strictEqual(engine.getProgress(), 0.0, 'Empty timeline should return 0.0 for progress');
        assert.strictEqual(engine.isApproachingNextChord(), false, 'Empty timeline should return false for isApproachingNextChord');

        // Test with empty array
        engine.loadTimeline({ beginnerChords: [] });
        assert.strictEqual(engine.getCurrentChord(), null, 'Timeline with empty beginnerChords array should return null');
        console.log('✓ Scenario 1: Empty timeline passed');
    }

    // 2. First chord
    {
        const clock = createMockClock(0.5);
        const engine = new CurrentChordEngine(clock);
        engine.loadTimeline(sampleTimeline);

        const current = engine.getCurrentChord();
        assert(current, 'Should find first chord');
        assert.strictEqual(current.chordName, 'C');
        assert.strictEqual(engine.getCurrentChordIndex(), 0);
        assert.strictEqual(engine.getPreviousChord(), null, 'First chord should have no previous chord');
        assert.strictEqual(engine.getNextChord().chordName, 'G', 'Next chord should be G');
        console.log('✓ Scenario 2: First chord passed');
    }

    // 3. Middle chord
    {
        const clock = createMockClock(3.0);
        const engine = new CurrentChordEngine(clock);
        engine.loadTimeline(sampleTimeline);

        const current = engine.getCurrentChord();
        assert(current, 'Should find middle chord');
        assert.strictEqual(current.chordName, 'G');
        assert.strictEqual(engine.getCurrentChordIndex(), 1);
        assert.strictEqual(engine.getPreviousChord().chordName, 'C');
        assert.strictEqual(engine.getNextChord().chordName, 'Am');
        console.log('✓ Scenario 3: Middle chord passed');
    }

    // 4. Exact chord boundary
    {
        const clock = createMockClock(2.0);
        const engine = new CurrentChordEngine(clock);
        engine.loadTimeline(sampleTimeline);

        // At exactly 2.0s, boundary transition must select G
        const current = engine.getCurrentChord();
        assert.strictEqual(current.chordName, 'G', 'At 2.0s boundary, current chord must be G');
        assert.strictEqual(engine.getCurrentChordIndex(), 1);
        assert.strictEqual(engine.getPreviousChord().chordName, 'C');
        assert.strictEqual(engine.getTimeIntoChord(), 0.0);
        assert.strictEqual(engine.getTimeRemaining(), 2.0);
        assert.strictEqual(engine.getProgress(), 0.0);
        console.log('✓ Scenario 4: Exact chord boundary passed');
    }

    // 5. Final chord
    {
        const clock = createMockClock(7.0);
        const engine = new CurrentChordEngine(clock);
        engine.loadTimeline(sampleTimeline);

        const current = engine.getCurrentChord();
        assert.strictEqual(current.chordName, 'F');
        assert.strictEqual(engine.getCurrentChordIndex(), 3);
        assert.strictEqual(engine.getPreviousChord().chordName, 'Am');
        assert.strictEqual(engine.getNextChord(), null, 'Final chord must have null for next chord');
        assert.strictEqual(engine.isApproachingNextChord(), false, 'Final chord cannot approach next chord');
        console.log('✓ Scenario 5: Final chord passed');
    }

    // 6. Before first chord
    {
        const clock = createMockClock(0.0);
        const offsetTimeline = {
            beginnerChords: [
                { chordName: 'D', startTime: 2.0, endTime: 4.0 },
                { chordName: 'A', startTime: 4.0, endTime: 6.0 }
            ]
        };
        const engine = new CurrentChordEngine(clock);
        engine.loadTimeline(offsetTimeline);

        clock.setTime(0.5);
        assert.strictEqual(engine.getCurrentChord(), null, 'Before first chord, current chord is null');
        assert.strictEqual(engine.getCurrentChordIndex(), -1);
        assert.strictEqual(engine.getPreviousChord(), null);
        assert.strictEqual(engine.getNextChord().chordName, 'D', 'Next chord should be first chord D');
        assert.strictEqual(engine.isApproachingNextChord(), false, 'At 0.5s with first chord at 2.0s (delta 1.5s > 0.75s), should not approach');

        clock.setTime(1.5);
        assert.strictEqual(engine.isApproachingNextChord(), true, 'At 1.5s with first chord at 2.0s (delta 0.5s <= 0.75s), should approach');
        console.log('✓ Scenario 6: Before first chord passed');
    }

    // 7. After final chord
    {
        const clock = createMockClock(8.0);
        const engine = new CurrentChordEngine(clock);
        engine.loadTimeline(sampleTimeline);

        // At exact end of final chord (8.0s)
        assert.strictEqual(engine.getCurrentChord(), null, 'At exact end of final chord, current chord is null');
        assert.strictEqual(engine.getCurrentChordIndex(), -1);
        assert.strictEqual(engine.getPreviousChord().chordName, 'F');
        assert.strictEqual(engine.getNextChord(), null);

        // Well after final chord (10.0s)
        clock.setTime(10.0);
        assert.strictEqual(engine.getCurrentChord(), null);
        assert.strictEqual(engine.getPreviousChord().chordName, 'F');
        assert.strictEqual(engine.getNextChord(), null);
        console.log('✓ Scenario 7: After final chord passed');
    }

    // 8. Time remaining
    {
        const clock = createMockClock(1.25);
        const engine = new CurrentChordEngine(clock);
        engine.loadTimeline(sampleTimeline);

        // Chord C is 0.0 -> 2.0. At 1.25s, remaining = 0.75s
        assert.strictEqual(Math.round(engine.getTimeRemaining() * 1000) / 1000, 0.75);
        
        clock.setTime(1.9);
        assert.strictEqual(Math.round(engine.getTimeRemaining() * 1000) / 1000, 0.1);
        console.log('✓ Scenario 8: Time remaining passed');
    }

    // 9. Progress
    {
        const clock = createMockClock(1.0);
        const engine = new CurrentChordEngine(clock);
        engine.loadTimeline(sampleTimeline);

        // Chord C is 0.0 -> 2.0. At 1.0s, progress = 0.5
        assert.strictEqual(engine.getProgress(), 0.5);

        clock.setTime(0.0);
        assert.strictEqual(engine.getProgress(), 0.0);

        clock.setTime(1.5);
        assert.strictEqual(engine.getProgress(), 0.75);
        console.log('✓ Scenario 9: Progress calculation passed');
    }

    // 10. Anticipation threshold
    {
        const clock = createMockClock(1.0);
        const engine = new CurrentChordEngine(clock, { anticipationThreshold: 0.75 });
        engine.loadTimeline(sampleTimeline);

        // At 1.0s (1.0s remaining > 0.75s): false
        assert.strictEqual(engine.isApproachingNextChord(), false);

        // At 1.25s (0.75s remaining == 0.75s): true
        clock.setTime(1.25);
        assert.strictEqual(engine.isApproachingNextChord(), true);

        // At 1.5s (0.5s remaining < 0.75s): true
        clock.setTime(1.5);
        assert.strictEqual(engine.isApproachingNextChord(), true);

        // Configurable threshold: change to 0.4s
        engine.setAnticipationThreshold(0.4);
        assert.strictEqual(engine.getAnticipationThreshold(), 0.4);
        assert.strictEqual(engine.isApproachingNextChord(), false, 'At 1.5s (0.5s remaining > 0.4s), should be false');

        clock.setTime(1.7);
        assert.strictEqual(engine.isApproachingNextChord(), true, 'At 1.7s (0.3s remaining <= 0.4s), should be true');
        console.log('✓ Scenario 10: Anticipation threshold passed');
    }

    // 11. Previous chord
    {
        const clock = createMockClock(5.0);
        const engine = new CurrentChordEngine(clock);
        engine.loadTimeline(sampleTimeline);

        // Chord at 5.0s is Am (index 2). Previous chord is G (index 1).
        assert.strictEqual(engine.getPreviousChord().chordName, 'G');
        console.log('✓ Scenario 11: Previous chord passed');
    }

    // 12. Next chord
    {
        const clock = createMockClock(5.0);
        const engine = new CurrentChordEngine(clock);
        engine.loadTimeline(sampleTimeline);

        // Chord at 5.0s is Am (index 2). Next chord is F (index 3).
        assert.strictEqual(engine.getNextChord().chordName, 'F');
        console.log('✓ Scenario 12: Next chord passed');
    }

    // 13. Repeated identical chords
    {
        const clock = createMockClock(1.0);
        const repeatedTimeline = {
            beginner_chords: [
                { chordName: 'C', startTime: 0.0, endTime: 2.0 },
                { chordName: 'C', startTime: 2.0, endTime: 4.0 },
                { chordName: 'G', startTime: 4.0, endTime: 6.0 }
            ]
        };
        const engine = new CurrentChordEngine(clock);
        engine.loadTimeline(repeatedTimeline);

        // At 1.0s: index 0
        assert.strictEqual(engine.getCurrentChordIndex(), 0);
        assert.strictEqual(engine.getCurrentChord().chordName, 'C');
        assert.strictEqual(engine.getNextChord().chordName, 'C');
        assert.strictEqual(engine.getPreviousChord(), null);

        // At 2.0s: index 1
        clock.setTime(2.0);
        assert.strictEqual(engine.getCurrentChordIndex(), 1);
        assert.strictEqual(engine.getCurrentChord().chordName, 'C');
        assert.strictEqual(engine.getNextChord().chordName, 'G');
        assert.strictEqual(engine.getPreviousChord().chordName, 'C');
        console.log('✓ Scenario 13: Repeated identical chords passed');
    }

    // 14. Timeline replacement
    {
        const clock = createMockClock(1.0);
        const engine = new CurrentChordEngine(clock);
        engine.loadTimeline(sampleTimeline);
        assert.strictEqual(engine.getCurrentChord().chordName, 'C');

        const newTimeline = {
            beginnerChords: [
                { chordName: 'Em', startTime: 0.0, endTime: 3.0 }
            ]
        };
        engine.loadTimeline(newTimeline);
        assert.strictEqual(engine.getCurrentChord().chordName, 'Em');
        assert.strictEqual(engine.getTimeRemaining(), 2.0);
        console.log('✓ Scenario 14: Timeline replacement passed');
    }

    // 15. Clear()
    {
        const clock = createMockClock(1.0);
        const engine = new CurrentChordEngine(clock);
        engine.loadTimeline(sampleTimeline);
        assert.strictEqual(engine.getCurrentChord().chordName, 'C');

        engine.clear();
        assert.strictEqual(engine.getCurrentChord(), null);
        assert.strictEqual(engine.getNextChord(), null);
        assert.strictEqual(engine.getPreviousChord(), null);
        assert.strictEqual(engine.getCurrentChordIndex(), -1);
        assert.strictEqual(engine.getTimeRemaining(), 0);
        assert.strictEqual(engine.getProgress(), 0);

        const state = engine.getState();
        assert.strictEqual(state.currentChord, null);
        assert.strictEqual(state.currentChordIndex, -1);
        console.log('✓ Scenario 15: Clear() passed');
    }

    console.log('All 15 CurrentChordEngine scenarios passed successfully!');
}

if (require.main === module) {
    runTests();
}

module.exports = { runTests };
