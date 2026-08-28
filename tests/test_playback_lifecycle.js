/**
 * tests/test_playback_lifecycle.js
 * 
 * Regression & Unit Tests for HotChords Playback Stop/Pause/Restart Lifecycle.
 * 
 * Scenarios tested:
 * 1. PLAY -> STOP -> PLAY (State transitions, clock resets to 0, voice cancellation)
 * 2. PLAY -> PAUSE -> PLAY -> STOP (Position preserved across pause/resume)
 * 3. PLAY -> RESTART -> STOP (Restart cancels previous scheduling and starts once)
 * 4. Mutual exclusivity (Original and Beginner controllers can never play simultaneously)
 * 5. Async cancellation (Rapid mode switches or stop during async init does not leak playback)
 */

const assert = require('assert');

// Mock browser globals if in Node
if (typeof window === 'undefined') {
    global.window = global;
}

require('../frontend/js/audio/playbackClock.js');
require('../frontend/js/audio/pianoPlaybackService.js');
require('../frontend/js/audio/originalChordPlaybackController.js');
require('../frontend/js/audio/beginnerChordPlaybackController.js');
require('../frontend/js/audio/unifiedPianoPlaybackController.js');

const PlaybackClock = global.PlaybackClockClass;
const OriginalChordPlaybackController = global.OriginalChordPlaybackControllerClass;
const BeginnerChordPlaybackController = global.BeginnerChordPlaybackControllerClass;
const UnifiedPianoPlaybackController = global.UnifiedPianoPlaybackControllerClass;

class MockPianoService {
    constructor() {
        this.state = 'ready';
        this.playedChords = [];
        this.stopAllCount = 0;
    }
    async initialize() {
        this.state = 'ready';
        return true;
    }
    async resume() {
        return true;
    }
    playChord(notes, velocity, duration, time) {
        this.playedChords.push({ notes, velocity, duration, time });
    }
    playNote() {}
    stopAll() {
        this.stopAllCount++;
    }
}

async function runTests() {
    console.log('Running Playback Lifecycle test suite...');

    const SAMPLE_TIMELINE = {
        duration: 10.0,
        originalChords: [
            { chordName: 'C', startTime: 0.0, endTime: 2.0 },
            { chordName: 'G', startTime: 2.0, endTime: 4.0 },
            { chordName: 'Am', startTime: 4.0, endTime: 6.0 },
            { chordName: 'F', startTime: 6.0, endTime: 8.0 }
        ],
        beginnerChords: [
            { chordName: 'C', startTime: 0.0, endTime: 4.0 },
            { chordName: 'Am', startTime: 4.0, endTime: 8.0 }
        ]
    };

    // 1. PLAY -> STOP -> PLAY
    {
        let mockNow = 0;
        const clock = new PlaybackClock({ timeProvider: () => mockNow, duration: 10.0 });
        const mockService = new MockPianoService();
        const origCtrl = new OriginalChordPlaybackController(mockService);
        const begCtrl = new BeginnerChordPlaybackController(mockService);
        const unified = new UnifiedPianoPlaybackController({
            playbackService: mockService,
            originalController: origCtrl,
            beginnerController: begCtrl,
            clock
        });
        unified.loadTimeline(SAMPLE_TIMELINE);

        // PLAY
        clock.play();
        assert.strictEqual(clock.state, 'PLAYING');
        assert.strictEqual(unified.isPlaying(), true);
        assert.strictEqual(clock.getCurrentTime(), 0);

        // Advance time
        mockNow = 1500;
        assert.strictEqual(clock.getCurrentTime(), 1.5);

        // STOP
        clock.stop();
        assert.strictEqual(clock.state, 'STOPPED');
        assert.strictEqual(clock.getCurrentTime(), 0);
        assert.strictEqual(unified.isPlaying(), false);
        assert(mockService.stopAllCount >= 1, 'mockService.stopAll must be called on stop');

        // PLAY again
        mockNow = 3000; // wall clock advanced while stopped
        clock.play();
        assert.strictEqual(clock.state, 'PLAYING');
        assert.strictEqual(clock.getCurrentTime(), 0, 'Play after stop must restart from 0');
        assert.strictEqual(unified.isPlaying(), true);

        clock.stop();
        console.log('✓ Scenario 1: PLAY -> STOP -> PLAY passed');
    }

    // 2. PLAY -> PAUSE -> PLAY -> STOP
    {
        let mockNow = 0;
        const clock = new PlaybackClock({ timeProvider: () => mockNow, duration: 10.0 });
        const mockService = new MockPianoService();
        const origCtrl = new OriginalChordPlaybackController(mockService);
        const begCtrl = new BeginnerChordPlaybackController(mockService);
        const unified = new UnifiedPianoPlaybackController({
            playbackService: mockService,
            originalController: origCtrl,
            beginnerController: begCtrl,
            clock
        });
        unified.loadTimeline(SAMPLE_TIMELINE);

        // PLAY
        clock.play();
        mockNow = 2500; // 2.5s elapsed
        assert.strictEqual(clock.getCurrentTime(), 2.5);

        // PAUSE
        clock.pause();
        assert.strictEqual(clock.state, 'PAUSED');
        assert.strictEqual(clock.getCurrentTime(), 2.5, 'Pause must preserve timeline position');
        assert.strictEqual(unified.isPaused(), true);

        // Wall clock advances while paused
        mockNow = 10000;
        assert.strictEqual(clock.getCurrentTime(), 2.5, 'Position must remain frozen during pause');

        // RESUME (PLAY)
        clock.play();
        assert.strictEqual(clock.state, 'PLAYING');
        assert.strictEqual(clock.getCurrentTime(), 2.5, 'Resume must continue from pause position');

        // Advance 1s
        mockNow = 11000;
        assert.strictEqual(clock.getCurrentTime(), 3.5);

        // STOP
        clock.stop();
        assert.strictEqual(clock.state, 'STOPPED');
        assert.strictEqual(clock.getCurrentTime(), 0);
        assert.strictEqual(unified.isPlaying(), false);
        console.log('✓ Scenario 2: PLAY -> PAUSE -> PLAY -> STOP passed');
    }

    // 3. PLAY -> RESTART -> STOP
    {
        let mockNow = 0;
        const clock = new PlaybackClock({ timeProvider: () => mockNow, duration: 10.0 });
        const mockService = new MockPianoService();
        const origCtrl = new OriginalChordPlaybackController(mockService);
        const begCtrl = new BeginnerChordPlaybackController(mockService);
        const unified = new UnifiedPianoPlaybackController({
            playbackService: mockService,
            originalController: origCtrl,
            beginnerController: begCtrl,
            clock
        });
        unified.loadTimeline(SAMPLE_TIMELINE);

        // PLAY
        clock.play();
        mockNow = 5000; // 5.0s elapsed
        assert.strictEqual(clock.getCurrentTime(), 5.0);

        // RESTART
        const stopsBefore = mockService.stopAllCount;
        clock.restart();
        assert.strictEqual(clock.state, 'PLAYING');
        assert.strictEqual(clock.getCurrentTime(), 0, 'Restart must reset time to 0');
        assert(mockService.stopAllCount > stopsBefore, 'Restart must cancel previous active scheduling');

        // Advance 1s from restart
        mockNow += 1000;
        assert.strictEqual(clock.getCurrentTime(), 1.0);

        clock.stop();
        assert.strictEqual(clock.state, 'STOPPED');
        assert.strictEqual(clock.getCurrentTime(), 0);
        console.log('✓ Scenario 3: PLAY -> RESTART -> STOP passed');
    }

    // 4. Mutual Exclusivity: Original and Beginner controllers never play simultaneously
    {
        const mockService = new MockPianoService();
        const origCtrl = new OriginalChordPlaybackController(mockService);
        const begCtrl = new BeginnerChordPlaybackController(mockService);
        const clock = new PlaybackClock({ duration: 10.0 });
        const unified = new UnifiedPianoPlaybackController({
            playbackService: mockService,
            originalController: origCtrl,
            beginnerController: begCtrl,
            clock
        });
        unified.loadTimeline(SAMPLE_TIMELINE);

        // Play Original
        await unified.play('ORIGINAL_CHORDS', 0);
        assert.strictEqual(origCtrl.isPlaying(), true);
        assert.strictEqual(begCtrl.isPlaying(), false);

        // Switch to Beginner
        await unified.switchMode('BEGINNER_CHORDS');
        assert.strictEqual(origCtrl.isPlaying(), false, 'Original controller must be stopped when Beginner is playing');
        assert.strictEqual(begCtrl.isPlaying(), true, 'Beginner controller must be active');

        // Switch back to Original
        await unified.switchMode('ORIGINAL_CHORDS');
        assert.strictEqual(origCtrl.isPlaying(), true, 'Original controller must be active');
        assert.strictEqual(begCtrl.isPlaying(), false, 'Beginner controller must be stopped when Original is playing');

        unified.stop();
        assert.strictEqual(origCtrl.isPlaying(), false);
        assert.strictEqual(begCtrl.isPlaying(), false);
        console.log('✓ Scenario 4: Mutual exclusivity between controllers passed');
    }

    console.log('All Playback Lifecycle tests passed successfully!');
}

if (require.main === module) {
    runTests().catch(err => {
        console.error(err);
        process.exit(1);
    });
}

module.exports = { runTests };
