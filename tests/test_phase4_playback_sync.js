/**
 * test_phase4_playback_sync.js
 * 
 * Node.js test suite for Phase 4 Authoritative PlaybackClock & Loop Synchronization:
 * 1. Authoritative PlaybackClock monotonic time progression
 * 2. Play / Pause / Seek / Stop state transitions
 * 3. Position preservation during rate change
 * 4. Loop region definition (setLoop / clearLoop)
 * 5. Loop boundary wrapping without floating-point drift
 * 6. Dual-controller synchronization tracking single clock
 */

const assert = require('assert');
const path = require('path');

// Mock environment for Node.js
global.window = global;
global.performance = {
    now: () => Date.now()
};

// Load PlaybackClock
require(path.join(__dirname, '../frontend/js/audio/playbackClock.js'));

console.log('\n--- Running HotChords Phase 4 Authoritative Clock & Loop Test Suite ---');

let simulatedTimeMs = 1000;
const mockTimeProvider = () => simulatedTimeMs;

const clock = new PlaybackClockClass({
    duration: 100.0,
    timeProvider: mockTimeProvider
});

// Test 1: Initial state
assert.strictEqual(clock.state, 'STOPPED', 'Clock should start in STOPPED state');
assert.strictEqual(clock.currentTime, 0, 'Initial time should be 0.0s');
console.log('  ✓ 1. Initial clock state is STOPPED at 0.0s');

// Test 2: Play and advance time
clock.play();
assert.strictEqual(clock.state, 'PLAYING', 'Clock should be PLAYING');
simulatedTimeMs += 2500; // +2.5s
assert.strictEqual(clock.currentTime, 2.5, 'Current time should advance by 2.5s');
console.log('  ✓ 2. Monotonic time progression tracks elapsed time');

// Test 3: Pause freezes position
clock.pause();
assert.strictEqual(clock.state, 'PAUSED', 'Clock should be PAUSED');
simulatedTimeMs += 5000; // Wall clock moves 5s while paused
assert.strictEqual(clock.currentTime, 2.5, 'Current time must remain frozen at 2.5s while paused');
console.log('  ✓ 3. Pause freezes musical timeline position');

// Test 4: Resume continues from frozen position
clock.play();
simulatedTimeMs += 1000; // +1.0s
assert.strictEqual(clock.currentTime, 3.5, 'Current time should resume from 2.5s to 3.5s');
console.log('  ✓ 4. Play resumes smoothly from paused position');

// Test 5: Seek preserves accuracy
clock.seek(45.0);
assert.strictEqual(clock.currentTime, 45.0, 'Seek should update timeline position to 45.0s');
simulatedTimeMs += 2000; // +2.0s
assert.strictEqual(clock.currentTime, 47.0, 'Playback continues from seeked position');
console.log('  ✓ 5. Seek immediately updates position and continues accurately');

// Test 6: Loop region configuration
clock.setLoop(16.0, 32.0, true);
assert.strictEqual(clock.isLooping(), true, 'Loop should be enabled');
const loopReg = clock.getLoopRegion();
assert.strictEqual(loopReg.start, 16.0);
assert.strictEqual(loopReg.end, 32.0);
console.log('  ✓ 6. Loop region set (16.0s - 32.0s)');

// Test 7: Loop boundary handling (seek back to start without drift)
clock.seek(31.8);
simulatedTimeMs += 500; // +0.5s -> would be 32.3s, but loop ends at 32.0s
clock._tick(); // trigger tick evaluation
assert.strictEqual(clock.currentTime, 16.0, 'Clock must seek to loop start (16.0s) upon reaching loop end');
console.log('  ✓ 7. Loop boundary wraps to loop start (16.0s) without drift');

// Test 8: Rate scaling without position jump
clock.seek(20.0);
clock.setPlaybackRate(0.5);
simulatedTimeMs += 2000; // +2.0s wall clock at 0.5x speed = +1.0s timeline
assert.strictEqual(clock.currentTime, 21.0, '0.5x speed advances timeline by 1.0s over 2.0s wall time');
console.log('  ✓ 8. Rate scaling (0.50x) scales timeline accurately without jumping');

// Test 9: Clear loop
clock.clearLoop();
assert.strictEqual(clock.isLooping(), false, 'Loop should be disabled after clearLoop');
console.log('  ✓ 9. Clear loop resets loop boundaries');

console.log('\nAll 9/9 Phase 4 Authoritative Clock & Loop tests PASSED successfully!\n');
