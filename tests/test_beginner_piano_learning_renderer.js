/**
 * tests/test_beginner_piano_learning_renderer.js
 * 
 * Focused unit test suite for BeginnerPianoLearningRenderer (Phase 6D-1) covering:
 * 1. C chord rendering
 * 2. G chord rendering
 * 3. Am chord rendering
 * 4. F chord rendering
 * 5. current/next rendering
 * 6. keyboard highlighting
 * 7. finger display
 * 8. progress display
 * 9. transition difficulty
 * 10. approaching-next state
 * 11. empty timeline
 * 12. missing fingering
 * 13. seek
 * 14. pause
 * 15. stop/restart
 */

const assert = require('assert');
require('../frontend/js/audio/playbackClock.js');
const PlaybackClock = global.PlaybackClockClass;
const { CurrentChordEngine } = require('../frontend/js/engine/currentChordEngine.js');
const { PianoFingeringEngine } = require('../frontend/js/engine/pianoFingeringEngine.js');
const { ChordTransitionEngine } = require('../frontend/js/engine/chordTransitionEngine.js');
const { BeginnerPianoLearningRenderer } = require('../frontend/js/ui/beginnerPianoLearningRenderer.js');

function runTests() {
    console.log('Running BeginnerPianoLearningRenderer unit test suite...');

    const SAMPLE_TIMELINE = {
        beginner_chords: [
            { chordName: 'C', startTime: 0.0, endTime: 2.0 },
            { chordName: 'G', startTime: 2.0, endTime: 4.0 },
            { chordName: 'Am', startTime: 4.0, endTime: 6.0 },
            { chordName: 'F', startTime: 6.0, endTime: 8.0 }
        ]
    };

    // Helper mock keyboard
    class MockKeyboard {
        constructor() {
            this.voicing = null;
            this.appliedCount = 0;
        }
        applyVoicingDOM() {
            this.appliedCount++;
        }
    }

    // 1. C Chord Rendering
    {
        let mockTime = 0.5;
        const clock = new PlaybackClock({ timeProvider: () => mockTime * 1000, duration: 8.0 });
        const chordEngine = new CurrentChordEngine(clock);
        chordEngine.loadTimeline(SAMPLE_TIMELINE);
        const mockKb = new MockKeyboard();

        const renderer = new BeginnerPianoLearningRenderer({
            clock,
            chordEngine,
            fingeringEngine: PianoFingeringEngine,
            transitionEngine: ChordTransitionEngine,
            keyboard: mockKb
        });

        const vm = renderer.getViewModel();
        assert.strictEqual(vm.currentChordName, 'C');
        assert.strictEqual(vm.nextChordName, 'G');
        assert(vm.currentVoicing);
        assert.deepStrictEqual(vm.currentVoicing.rightHand.notes, ['C4', 'E4', 'G4']);
        assert.deepStrictEqual(vm.currentVoicing.leftHand.notes, ['C2', 'G2']);
        console.log('✓ Scenario 1: C Chord Rendering passed');
    }

    // 2. G Chord Rendering
    {
        const clock = new PlaybackClock({ duration: 8.0 });
        clock.seek(2.5);
        const chordEngine = new CurrentChordEngine(clock);
        chordEngine.loadTimeline(SAMPLE_TIMELINE);

        const renderer = new BeginnerPianoLearningRenderer({
            clock,
            chordEngine,
            fingeringEngine: PianoFingeringEngine,
            transitionEngine: ChordTransitionEngine
        });

        const vm = renderer.getViewModel();
        assert.strictEqual(vm.currentChordName, 'G');
        assert.strictEqual(vm.nextChordName, 'Am');
        assert.deepStrictEqual(vm.currentVoicing.rightHand.notes, ['G4', 'B4', 'D5']);
        assert.deepStrictEqual(vm.currentVoicing.leftHand.notes, ['G2', 'D3']);
        console.log('✓ Scenario 2: G Chord Rendering passed');
    }

    // 3. Am Chord Rendering
    {
        const clock = new PlaybackClock({ duration: 8.0 });
        clock.seek(4.5);
        const chordEngine = new CurrentChordEngine(clock);
        chordEngine.loadTimeline(SAMPLE_TIMELINE);

        const renderer = new BeginnerPianoLearningRenderer({
            clock,
            chordEngine,
            fingeringEngine: PianoFingeringEngine,
            transitionEngine: ChordTransitionEngine
        });

        const vm = renderer.getViewModel();
        assert.strictEqual(vm.currentChordName, 'Am');
        assert.strictEqual(vm.nextChordName, 'F');
        assert.deepStrictEqual(vm.currentVoicing.rightHand.notes, ['A4', 'C5', 'E5']);
        assert.deepStrictEqual(vm.currentVoicing.leftHand.notes, ['A2', 'E3']);
        console.log('✓ Scenario 3: Am Chord Rendering passed');
    }

    // 4. F Chord Rendering
    {
        const clock = new PlaybackClock({ duration: 8.0 });
        clock.seek(6.5);
        const chordEngine = new CurrentChordEngine(clock);
        chordEngine.loadTimeline(SAMPLE_TIMELINE);

        const renderer = new BeginnerPianoLearningRenderer({
            clock,
            chordEngine,
            fingeringEngine: PianoFingeringEngine,
            transitionEngine: ChordTransitionEngine
        });

        const vm = renderer.getViewModel();
        assert.strictEqual(vm.currentChordName, 'F');
        assert.strictEqual(vm.nextChordName, null);
        assert.deepStrictEqual(vm.currentVoicing.rightHand.notes, ['F4', 'A4', 'C5']);
        assert.deepStrictEqual(vm.currentVoicing.leftHand.notes, ['F2', 'C3']);
        console.log('✓ Scenario 4: F Chord Rendering passed');
    }

    // 5. Current/Next Rendering
    {
        const clock = new PlaybackClock({ duration: 8.0 });
        clock.seek(0.5);
        const chordEngine = new CurrentChordEngine(clock);
        chordEngine.loadTimeline(SAMPLE_TIMELINE);

        const renderer = new BeginnerPianoLearningRenderer({
            clock,
            chordEngine,
            fingeringEngine: PianoFingeringEngine,
            transitionEngine: ChordTransitionEngine
        });

        const vm = renderer.getViewModel();
        assert.strictEqual(vm.currentChord.chordName, 'C');
        assert.strictEqual(vm.nextChord.chordName, 'G');
        console.log('✓ Scenario 5: Current/Next Rendering passed');
    }

    // 6. Keyboard Highlighting
    {
        const clock = new PlaybackClock({ duration: 8.0 });
        clock.seek(1.0);
        const chordEngine = new CurrentChordEngine(clock);
        chordEngine.loadTimeline(SAMPLE_TIMELINE);
        const mockKb = new MockKeyboard();

        const renderer = new BeginnerPianoLearningRenderer({
            clock,
            chordEngine,
            fingeringEngine: PianoFingeringEngine,
            transitionEngine: ChordTransitionEngine,
            keyboard: mockKb
        });

        renderer.update();
        assert(mockKb.voicing);
        assert.deepStrictEqual(mockKb.voicing.rightHand.midiNotes, [60, 64, 67]);
        assert.deepStrictEqual(mockKb.voicing.leftHand.midiNotes, [36, 43]);
        assert(mockKb.appliedCount > 0);
        console.log('✓ Scenario 6: Keyboard Highlighting passed');
    }

    // 7. Finger Display
    {
        const clock = new PlaybackClock({ duration: 8.0 });
        clock.seek(0.5);
        const chordEngine = new CurrentChordEngine(clock);
        chordEngine.loadTimeline(SAMPLE_TIMELINE);

        const renderer = new BeginnerPianoLearningRenderer({
            clock,
            chordEngine,
            fingeringEngine: PianoFingeringEngine,
            transitionEngine: ChordTransitionEngine
        });

        const vm = renderer.getViewModel();
        assert.deepStrictEqual(vm.currentVoicing.rightHand.fingers, [1, 3, 5]);
        assert.deepStrictEqual(vm.currentVoicing.leftHand.fingers, [5, 1]);
        assert.strictEqual(vm.currentVoicing.rightHand[0].color, '#FF4D4F'); // Thumb red
        console.log('✓ Scenario 7: Finger Display passed');
    }

    // 8. Progress Display
    {
        const clock = new PlaybackClock({ duration: 8.0 });
        clock.seek(1.0); // 1.0s into [0.0, 2.0] is 50%
        const chordEngine = new CurrentChordEngine(clock);
        chordEngine.loadTimeline(SAMPLE_TIMELINE);

        const renderer = new BeginnerPianoLearningRenderer({
            clock,
            chordEngine,
            fingeringEngine: PianoFingeringEngine,
            transitionEngine: ChordTransitionEngine
        });

        const vm = renderer.getViewModel();
        assert.strictEqual(vm.progress, 0.5);
        console.log('✓ Scenario 8: Progress Display passed');
    }

    // 9. Transition Difficulty
    {
        const clock = new PlaybackClock({ duration: 8.0 });
        clock.seek(4.5); // Am -> F
        const chordEngine = new CurrentChordEngine(clock);
        chordEngine.loadTimeline(SAMPLE_TIMELINE);

        const renderer = new BeginnerPianoLearningRenderer({
            clock,
            chordEngine,
            fingeringEngine: PianoFingeringEngine,
            transitionEngine: ChordTransitionEngine
        });

        const vm = renderer.getViewModel();
        assert(vm.transition);
        assert.strictEqual(vm.difficulty, 'EASY');
        assert(vm.transitionTip.length > 0);
        console.log('✓ Scenario 9: Transition Difficulty passed');
    }

    // 10. Approaching-Next State
    {
        const clock = new PlaybackClock({ duration: 8.0 });
        const chordEngine = new CurrentChordEngine(clock, { anticipationThreshold: 0.75 });
        chordEngine.loadTimeline(SAMPLE_TIMELINE);

        const renderer = new BeginnerPianoLearningRenderer({
            clock,
            chordEngine,
            fingeringEngine: PianoFingeringEngine,
            transitionEngine: ChordTransitionEngine
        });

        // At 1.0s (1.0s remaining > 0.75s) -> not approaching
        clock.seek(1.0);
        let vm = renderer.getViewModel();
        assert.strictEqual(vm.isApproachingNext, false);

        // At 1.5s (0.5s remaining <= 0.75s) -> approaching next chord
        clock.seek(1.5);
        vm = renderer.getViewModel();
        assert.strictEqual(vm.isApproachingNext, true);
        console.log('✓ Scenario 10: Approaching-Next State passed');
    }

    // 11. Empty Timeline
    {
        const clock = new PlaybackClock({ duration: 8.0 });
        const chordEngine = new CurrentChordEngine(clock);
        const renderer = new BeginnerPianoLearningRenderer({
            clock,
            chordEngine,
            fingeringEngine: PianoFingeringEngine,
            transitionEngine: ChordTransitionEngine
        });

        const vm = renderer.getViewModel();
        assert.strictEqual(vm.currentChordName, null);
        assert.strictEqual(vm.nextChordName, null);
        assert.strictEqual(vm.currentVoicing, null);
        assert.strictEqual(vm.progress, 0.0);
        console.log('✓ Scenario 11: Empty Timeline passed');
    }

    // 12. Missing Fingering / Unsupported Chord
    {
        const oddTimeline = {
            beginner_chords: [
                { chordName: 'Unknown999', startTime: 0.0, endTime: 2.0 }
            ]
        };
        const clock = new PlaybackClock({ duration: 4.0 });
        clock.seek(0.5);
        const chordEngine = new CurrentChordEngine(clock);
        chordEngine.loadTimeline(oddTimeline);

        const renderer = new BeginnerPianoLearningRenderer({
            clock,
            chordEngine,
            fingeringEngine: PianoFingeringEngine,
            transitionEngine: ChordTransitionEngine
        });

        const vm = renderer.getViewModel();
        assert.strictEqual(vm.currentChordName, 'Unknown999');
        assert.strictEqual(vm.currentVoicing, null); // Handled gracefully
        console.log('✓ Scenario 12: Missing Fingering passed');
    }

    // 13. Seek
    {
        const clock = new PlaybackClock({ duration: 8.0 });
        const chordEngine = new CurrentChordEngine(clock);
        chordEngine.loadTimeline(SAMPLE_TIMELINE);

        const renderer = new BeginnerPianoLearningRenderer({
            clock,
            chordEngine,
            fingeringEngine: PianoFingeringEngine,
            transitionEngine: ChordTransitionEngine
        });

        clock.seek(0.5);
        assert.strictEqual(renderer.getViewModel().currentChordName, 'C');

        clock.seek(2.5);
        assert.strictEqual(renderer.getViewModel().currentChordName, 'G');

        clock.seek(4.5);
        assert.strictEqual(renderer.getViewModel().currentChordName, 'Am');

        clock.seek(6.5);
        assert.strictEqual(renderer.getViewModel().currentChordName, 'F');
        console.log('✓ Scenario 13: Seek passed');
    }

    // 14. Pause
    {
        let mockTime = 1000;
        const clock = new PlaybackClock({ timeProvider: () => mockTime, duration: 8.0 });
        const chordEngine = new CurrentChordEngine(clock);
        chordEngine.loadTimeline(SAMPLE_TIMELINE);

        const renderer = new BeginnerPianoLearningRenderer({
            clock,
            chordEngine,
            fingeringEngine: PianoFingeringEngine,
            transitionEngine: ChordTransitionEngine
        });

        clock.play();
        assert.strictEqual(renderer.getViewModel().clockState, 'PLAYING');
        
        clock.pause();
        assert.strictEqual(renderer.getViewModel().clockState, 'PAUSED');
        console.log('✓ Scenario 14: Pause passed');
    }

    // 15. Stop / Restart
    {
        const clock = new PlaybackClock({ duration: 8.0 });
        clock.seek(5.0);
        const chordEngine = new CurrentChordEngine(clock);
        chordEngine.loadTimeline(SAMPLE_TIMELINE);

        const renderer = new BeginnerPianoLearningRenderer({
            clock,
            chordEngine,
            fingeringEngine: PianoFingeringEngine,
            transitionEngine: ChordTransitionEngine
        });

        assert.strictEqual(renderer.getViewModel().currentChordName, 'Am');

        clock.stop();
        assert.strictEqual(renderer.getViewModel().clockState, 'STOPPED');
        assert.strictEqual(renderer.getViewModel().currentTime, 0);
        assert.strictEqual(renderer.getViewModel().currentChordName, 'C');
        console.log('✓ Scenario 15: Stop/Restart passed');
    }

    console.log('All BeginnerPianoLearningRenderer tests passed successfully!');
}

if (require.main === module) {
    runTests();
}

module.exports = { runTests };
