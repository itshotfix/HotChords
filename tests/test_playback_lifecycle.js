/**
 * tests/test_playback_lifecycle.js
 * 
 * Regression & Unit Tests for HotChords Playback Architecture:
 * - PlaybackClock canonical timeline & loop/restart semantics
 * - SongAudioController media element lifecycle, promises, and smooth drift reconciliation
 * - UnifiedPianoPlaybackController voice cancellation and rate scaling
 * - Mutual audio exclusivity between Piano and Original audio renderers
 * - Diagnostics & error state handling
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
require('../frontend/js/audio/songAudioController.js');

const PlaybackClock = global.PlaybackClockClass;
const OriginalChordPlaybackController = global.OriginalChordPlaybackControllerClass;
const BeginnerChordPlaybackController = global.BeginnerChordPlaybackControllerClass;
const UnifiedPianoPlaybackController = global.UnifiedPianoPlaybackControllerClass;
const SongAudioController = global.SongAudioControllerClass;

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

class MockAudioElement {
    constructor() {
        this.src = '';
        this.currentTime = 0;
        this.duration = 10.0;
        this.playbackRate = 1.0;
        this.paused = true;
        this.ended = false;
        this.readyState = 4;
        this.networkState = 1;
        this.muted = false;
        this.volume = 1.0;
        this.preservesPitch = true;
        this.playRejection = false;
        this.listeners = {};
    }

    addEventListener(event, fn) {
        if (!this.listeners[event]) this.listeners[event] = [];
        this.listeners[event].push(fn);
    }

    removeEventListener(event, fn) {
        if (!this.listeners[event]) return;
        this.listeners[event] = this.listeners[event].filter(l => l !== fn);
    }

    _emit(event, data) {
        if (this.listeners[event]) {
            this.listeners[event].forEach(fn => fn(data));
        }
    }

    load() {
        setTimeout(() => {
            this.readyState = 4;
            this._emit('loadedmetadata');
            this._emit('canplay');
        }, 10);
    }

    async play() {
        if (this.playRejection) {
            throw new Error('NotAllowedError: play() failed');
        }
        this.paused = false;
        this._emit('play');
        this._emit('playing');
        return Promise.resolve();
    }

    pause() {
        this.paused = true;
        this._emit('pause');
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
        mockNow = 3000;
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
        mockNow = 2500;
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
        mockNow = 5000;
        clock._tick();
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

    // 4. Mutual Exclusivity: Piano vs Original Track
    {
        const clock = new PlaybackClock({ duration: 10.0 });
        const mockPianoService = new MockPianoService();
        const origCtrl = new OriginalChordPlaybackController(mockPianoService);
        const begCtrl = new BeginnerChordPlaybackController(mockPianoService);
        const unifiedPiano = new UnifiedPianoPlaybackController({
            playbackService: mockPianoService,
            originalController: origCtrl,
            beginnerController: begCtrl,
            clock
        });
        unifiedPiano.loadTimeline(SAMPLE_TIMELINE);

        const songAudio = new SongAudioController({ clock });
        const mockAudio = new MockAudioElement();
        songAudio.audioEl = mockAudio;
        await songAudio.load('mock_track.mp3');

        // Default: Piano enabled, SongAudio disabled
        unifiedPiano.setEnabled(true);
        songAudio.setEnabled(false);
        assert.strictEqual(unifiedPiano.enabled, true);
        assert.strictEqual(songAudio.enabled, false);

        // Start playing
        clock.play();
        assert.strictEqual(unifiedPiano.isPlaying(), true);
        assert.strictEqual(mockAudio.paused, true, 'SongAudio must remain paused when disabled');

        // Switch to Original mode
        unifiedPiano.setEnabled(false);
        songAudio.setEnabled(true);
        assert.strictEqual(unifiedPiano.enabled, false);
        assert.strictEqual(songAudio.enabled, true);
        assert.strictEqual(unifiedPiano.isPlaying(), false, 'Piano must silence when disabled');
        assert.strictEqual(mockAudio.paused, false, 'SongAudio must start playing when enabled');

        // Switch back to Piano mode
        unifiedPiano.setEnabled(true);
        songAudio.setEnabled(false);
        assert.strictEqual(unifiedPiano.enabled, true);
        assert.strictEqual(songAudio.enabled, false);
        assert.strictEqual(unifiedPiano.isPlaying(), true, 'Piano must resume when enabled');
        assert.strictEqual(mockAudio.paused, true, 'SongAudio must pause when disabled');

        clock.stop();
        console.log('✓ Scenario 4: Mutual exclusivity between Piano and Original renderers passed');
    }

    // 5. Loop Behavior & Boundary Transitions
    {
        let mockNow = 0;
        const clock = new PlaybackClock({ timeProvider: () => mockNow, duration: 10.0 });
        clock.setLoop(2.0, 6.0, true);

        assert.strictEqual(clock.isLooping(), true);
        const region = clock.getLoopRegion();
        assert.strictEqual(region.start, 2.0);
        assert.strictEqual(region.end, 6.0);

        clock.play();
        mockNow = 1000; // 1s
        assert.strictEqual(clock.getCurrentTime(), 1.0);

        // Advance to 6.0s (loopEnd reached in _tick)
        mockNow = 6000;
        assert(clock.getCurrentTime() >= 6.0);

        clock._tick(); // rAF tick processes loop jump
        assert.strictEqual(clock.getCurrentTime(), 2.0, 'Clock must jump to loopStart upon reaching loopEnd');

        clock.clearLoop();
        assert.strictEqual(clock.isLooping(), false);
        clock.stop();
        console.log('✓ Scenario 5: Loop boundaries and wrap-around passed');
    }

    // 6. SongAudioController Diagnostics and Error Recovery
    {
        const clock = new PlaybackClock({ duration: 10.0 });
        const songAudio = new SongAudioController({ clock });
        const mockAudio = new MockAudioElement();
        songAudio.audioEl = mockAudio;

        // Test diagnostics
        const diag = songAudio.getDiagnostics();
        assert.strictEqual(diag.enabled, false);
        assert.strictEqual(typeof diag.currentTime, 'number');

        // Test error handling on load failure
        const failedLoad = await songAudio.load('');
        assert.strictEqual(failedLoad, false);
        assert.strictEqual(songAudio.getState(), 'ERROR');
        assert(songAudio.error !== null);

        // Dispose
        songAudio.dispose();
        assert.strictEqual(songAudio.getState(), 'UNLOADED');
        console.log('✓ Scenario 6: SongAudioController diagnostics and error recovery passed');
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
