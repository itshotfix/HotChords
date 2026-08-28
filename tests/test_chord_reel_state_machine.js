/**
 * test_chord_reel_state_machine.js
 * 
 * Phase 9A State Machine & Determinism Test Suite for DynamicChordReel.
 */

const assert = require('assert');
const path = require('path');

let animationLog = [];

function createMockContainer() {
    const makeSlot = (id, initialRole) => {
        const classes = new Set([initialRole]);
        const nameEl = { textContent: '—' };
        const voiceEl = { textContent: '', style: {} };
        const progFill = { style: { width: '0%' } };

        const slot = {
            id,
            style: {},
            nameEl,
            voiceEl,
            progFill,
            classList: {
                add(...c) { c.forEach(x => classes.add(x)); },
                remove(...c) { c.forEach(x => classes.delete(x)); },
                toggle(c, force) {
                    if (force === true) classes.add(c);
                    else if (force === false) classes.delete(c);
                    else if (classes.has(c)) classes.delete(c);
                    else classes.add(c);
                },
                contains(c) { return classes.has(c); }
            },
            querySelector(sel) {
                if (sel.includes('data-chord-name') || sel.includes('chord-name')) return nameEl;
                if (sel.includes('data-chord-voicing') || sel.includes('chord-voicing')) return voiceEl;
                if (sel.includes('data-progress-fill') || sel.includes('progress-fill')) return progFill;
                return null;
            },
            animate(keyframes, options) {
                const a = {
                    keyframes,
                    options,
                    element: slot,
                    playState: 'running',
                    onfinish: null,
                    oncancel: null,
                    cancel() {
                        this.playState = 'canceled';
                        if (typeof this.oncancel === 'function') this.oncancel();
                    },
                    finish() {
                        this.playState = 'finished';
                        if (typeof this.onfinish === 'function') this.onfinish();
                    }
                };
                animationLog.push(a);
                return a;
            }
        };
        return slot;
    };

    const prevSlot = makeSlot('reel-slot-prev', 'crt-card--prev');
    const curSlot  = makeSlot('reel-slot-current', 'crt-card--current');
    const nextSlot = makeSlot('reel-slot-next', 'crt-card--next');

    const track = {
        id: 'crt-track-1',
        children: [prevSlot, curSlot, nextSlot],
        insertBefore(n, ref) { this.children.unshift(n); return n; },
        appendChild(n) { this.children.push(n); return n; },
        querySelectorAll() { return []; }
    };

    const container = {
        innerHTML: '',
        style: {},
        querySelector(sel) {
            if (sel === '#reel-slot-prev' || sel === '.crt-card--prev' || sel === '.crt-item--prev') return prevSlot;
            if (sel === '#reel-slot-current' || sel === '.crt-card--current' || sel === '.crt-item--current') return curSlot;
            if (sel === '#reel-slot-next' || sel === '.crt-card--next' || sel === '.crt-item--next') return nextSlot;
            if (sel === '#reel-prev-name') return prevSlot.nameEl;
            if (sel === '#reel-current-name') return curSlot.nameEl;
            if (sel === '#reel-next-name') return nextSlot.nameEl;
            if (sel === '#reel-current-voicing') return curSlot.voiceEl;
            if (sel === '#reel-progress-fill') return curSlot.progFill;
            if (sel.includes('crt-track') || sel === '#reel-chords-row') return track;
            return null;
        }
    };

    return { container, prevSlot, curSlot, nextSlot };
}

// Global browser mocks
global.window = global;
global.document = {
    createElement: (tag) => {
        const classes = new Set();
        const nameEl = { textContent: '—' };
        const voiceEl = { textContent: '', style: {} };
        const progFill = { style: { width: '0%' } };

        const el = {
            style: {},
            nameEl,
            voiceEl,
            progFill,
            classList: {
                add(...c) { c.forEach(x => classes.add(x)); },
                remove(...c) { c.forEach(x => classes.delete(x)); },
                toggle(c, force) {
                    if (force === true) classes.add(c);
                    else if (force === false) classes.delete(c);
                    else if (classes.has(c)) classes.delete(c);
                    else classes.add(c);
                }
            },
            setAttribute(){},
            innerHTML: '',
            querySelector: (sel) => {
                if (sel.includes('data-chord-name')) return nameEl;
                if (sel.includes('data-chord-voicing')) return voiceEl;
                if (sel.includes('data-progress-fill')) return progFill;
                return null;
            },
            animate(keyframes, options) {
                const a = {
                    keyframes, options, playState: 'running',
                    cancel() { this.playState = 'canceled'; if (this.oncancel) this.oncancel(); },
                    finish() { this.playState = 'finished'; if (this.onfinish) this.onfinish(); }
                };
                animationLog.push(a);
                return a;
            }
        };
        return el;
    }
};
global.performance = { now: () => Date.now() };

const { DynamicChordReel } = require(path.join(__dirname, '../frontend/js/ui/dynamicChordReel.js'));

const sampleChords = [
    { startTime: 0.0, endTime: 2.0, chordName: 'Am', notes: [9, 0, 4] },
    { startTime: 2.0, endTime: 4.5, chordName: 'C',  notes: [0, 4, 7] },
    { startTime: 4.5, endTime: 7.0, chordName: 'F',  notes: [5, 8, 0] },
    { startTime: 7.0, endTime: 9.5, chordName: 'G',  notes: [7, 11, 2] }
];

let testsPassed = 0;
function runTest(name, fn) {
    try {
        animationLog = [];
        const env = createMockContainer();
        fn(env);
        console.log(`  ✓ ${name}`);
        testsPassed++;
    } catch (err) {
        console.error(`  ✗ ${name}`);
        console.error(err);
        process.exit(1);
    }
}

console.log('=== Starting Phase 9A Chord Timeline State Machine Tests ===');

runTest('1. Initialization creates clean 3-chord reel skeleton with empty state', (env) => {
    const reel = new DynamicChordReel({ container: env.container });
    assert.strictEqual(reel.container, env.container, 'Container correctly bound');
    assert.strictEqual(reel._state.currentIndex, -1, 'Initial index is -1');
    assert.ok(env.container.innerHTML.includes('shared-chord-timeline'), 'Shared timeline rendered in HTML');
});

runTest('2. loadChords initializes data and renders initial slots at t=0', (env) => {
    const reel = new DynamicChordReel({ container: env.container });
    reel.loadChords(sampleChords);

    assert.strictEqual(reel.chords.length, 4, 'Chords loaded');
    assert.strictEqual(reel._state.currentIndex, -1, 'Index starts before playback');
});

runTest('3. Index resolution is deterministic across exact boundaries', (env) => {
    const reel = new DynamicChordReel({ container: env.container });
    reel.loadChords(sampleChords);

    assert.strictEqual(reel._resolveIndex(0.0), 0, 't=0.0 -> Am');
    assert.strictEqual(reel._resolveIndex(1.99), 0, 't=1.99 -> Am');
    assert.strictEqual(reel._resolveIndex(2.0), 1, 't=2.0 -> C (exact boundary)');
    assert.strictEqual(reel._resolveIndex(4.49), 1, 't=4.49 -> C');
    assert.strictEqual(reel._resolveIndex(4.5), 2, 't=4.5 -> F');
    assert.strictEqual(reel._resolveIndex(7.0), 3, 't=7.0 -> G');
    assert.strictEqual(reel._resolveIndex(12.0), 3, 't=12.0 -> trailing fallback to G');
});

runTest('4. update(0.5) updates slot content to first chord (Am)', (env) => {
    const reel = new DynamicChordReel({ container: env.container });
    reel.loadChords(sampleChords);

    reel.update(0.5);
    assert.strictEqual(reel._state.currentIndex, 0, 'Active chord index is 0 (Am)');
    assert.strictEqual(reel._elements.cur.nameEl.textContent, 'Am', 'Current chord is Am');
    assert.strictEqual(reel._elements.next.nameEl.textContent, 'C', 'Next chord is C');
    assert.strictEqual(reel._elements.prev.nameEl.textContent, '—', 'Previous chord is empty');
});

runTest('5. Crossing boundary naturally (oldIdx -> oldIdx + 1) triggers WAAPI transition', (env) => {
    const reel = new DynamicChordReel({ container: env.container });
    reel.loadChords(sampleChords);
    reel.update(0.5); // Index 0

    animationLog = [];
    reel.update(2.1); // Index 1 (natural step 0 -> 1)

    assert.strictEqual(reel._state.isAnimating, true, 'isAnimating state is true during transition');
    assert(animationLog.length >= 3, 'WAAPI element.animate triggered on elements');
});

runTest('6. WAAPI animation completion settles state into stable DOM without artifacts', (env) => {
    const reel = new DynamicChordReel({ container: env.container });
    reel.loadChords(sampleChords);
    reel.update(0.5); // Index 0 (Am)
    reel.update(2.1); // Natural step to Index 1 (C)

    // Complete all active mock animations
    animationLog.forEach(a => a.finish());

    assert.strictEqual(reel._state.isAnimating, false, 'isAnimating reset to false after settle');
    assert.strictEqual(reel._elements.prev.nameEl.textContent, 'Am', 'Prev chord is now Am');
    assert.strictEqual(reel._elements.cur.nameEl.textContent, 'C', 'Current chord is now C');
    assert.strictEqual(reel._elements.next.nameEl.textContent, 'F', 'Next chord is now F');
});

runTest('7. Seek operation instantly cancels active animations and rebuilds instantly without transition', (env) => {
    const reel = new DynamicChordReel({ container: env.container });
    reel.loadChords(sampleChords);
    reel.update(0.5); // Index 0
    reel.update(2.1); // Index 1 (started animating)

    // Seek directly to G (t=7.5, Index 3)
    animationLog = [];
    reel.seekTo(7.5);

    assert.strictEqual(reel._state.isAnimating, false, 'isAnimating must be false immediately upon seek');
    assert.strictEqual(reel._state.currentIndex, 3, 'Current index updated to 3 (G)');
    assert.strictEqual(reel._elements.prev.nameEl.textContent, 'F', 'Prev chord is F');
    assert.strictEqual(reel._elements.cur.nameEl.textContent, 'G', 'Current chord is G');
    assert.strictEqual(reel._elements.next.nameEl.textContent, '—', 'Next chord is empty after last chord');
});

runTest('8. Backward seek rebuilds state instantly without animation', (env) => {
    const reel = new DynamicChordReel({ container: env.container });
    reel.loadChords(sampleChords);
    reel.update(7.5); // Index 3 (G)

    animationLog = [];
    reel.seekTo(1.0); // Seek back to Am (Index 0)

    assert.strictEqual(animationLog.length, 0, 'No WAAPI animations invoked during backward seek');
    assert.strictEqual(reel._state.currentIndex, 0, 'Current index is 0 (Am)');
    assert.strictEqual(reel._elements.cur.nameEl.textContent, 'Am', 'Current chord is Am');
});

runTest('9. Pause and resume freeze and unfreeze progress/updates', (env) => {
    const reel = new DynamicChordReel({ container: env.container });
    reel.loadChords(sampleChords);
    reel.update(0.5); // Index 0

    reel.pause();
    assert.strictEqual(reel._state.isPaused, true, 'isPaused is true');
    reel.update(2.5); // Should be ignored while paused
    assert.strictEqual(reel._state.currentIndex, 0, 'Index did not advance while paused');

    reel.resume();
    assert.strictEqual(reel._state.isPaused, false, 'isPaused is false');
    reel.update(2.5);
    assert.strictEqual(reel._state.currentIndex, 1, 'Index advanced after resume');
});

runTest('10. Destroy cleans up all DOM elements and active animations cleanly', (env) => {
    const reel = new DynamicChordReel({ container: env.container });
    reel.loadChords(sampleChords);
    reel.destroy();

    assert.strictEqual(env.container.innerHTML, '', 'Container DOM emptied on destroy');
    assert.strictEqual(reel.chords.length, 0, 'Chords cleared');
});

console.log(`\nAll ${testsPassed}/10 Phase 9A State Machine tests passed successfully!`);
