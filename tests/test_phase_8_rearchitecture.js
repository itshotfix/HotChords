/**
 * test_phase_8_rearchitecture.js
 * 
 * Unit and Integration Test Suite for HotChords Phase 8:
 * UI/UX Rearchitecture & Shared Responsive Layout.
 */

const assert = require('assert');
const fs = require('fs');
const path = require('path');

// Mock browser globals
global.window = global;
global.document = {
    getElementById: (id) => ({
        innerHTML: '',
        style: {},
        classList: {
            add() {},
            remove() {},
            toggle() {},
            contains() { return false; }
        },
        setAttribute() {},
        removeAttribute() {},
        getAttribute() { return null; },
        appendChild() {},
        querySelectorAll() { return []; },
        querySelector() { return null; }
    }),
    createElement: () => ({
        innerHTML: '',
        style: {},
        classList: { add() {}, remove() {} },
        setAttribute() {},
        appendChild() {}
    })
};
global.ResizeObserver = class MockResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
};

// Load components
require(path.join(__dirname, '../frontend/js/engine/musicTheoryFormatter.js'));
require(path.join(__dirname, '../frontend/js/engine/pianoFingeringEngine.js'));
require(path.join(__dirname, '../frontend/js/engine/chordTransitionEngine.js'));
require(path.join(__dirname, '../frontend/js/engine/currentChordEngine.js'));
require(path.join(__dirname, '../frontend/js/ui/chordRibbon.js'));
require(path.join(__dirname, '../frontend/js/ui/beginnerChartRenderer.js'));
require(path.join(__dirname, '../frontend/js/ui/pianoKeyboard.js'));
require(path.join(__dirname, '../frontend/js/audio/playbackClock.js'));

require(path.join(__dirname, '../frontend/js/ui/dynamicChordReel.js'));

const sampleChords = [
    { startTime: 0.0, endTime: 4.0, chordName: 'F#', notes: [6, 10, 1] },
    { startTime: 4.0, endTime: 8.0, chordName: 'Bb', notes: [10, 2, 5] },
    { startTime: 8.0, endTime: 12.0, chordName: 'B', notes: [11, 3, 6] },
    { startTime: 12.0, endTime: 16.0, chordName: 'F#', notes: [6, 10, 1] },
    { startTime: 16.0, endTime: 20.0, chordName: 'Bbm', notes: [10, 1, 5] }
];

function runTests() {
    console.log('--- Running HotChords Phase 8 Rearchitecture Test Suite ---');
    let passed = 0;

    function test(name, fn) {
        try {
            fn();
            console.log(`  ✓ ${name}`);
            passed++;
        } catch (err) {
            console.error(`  ✗ ${name}:`, err.message);
            throw err;
        }
    }

    // 1. ChordRibbon component availability & clean typography rendering
    test('1. ChordRibbon renders clean musical typography (no box borders)', () => {
        let mockContainer = { innerHTML: '' };
        global.ChordRibbon.render(mockContainer, sampleChords);
        assert.ok(mockContainer.innerHTML.includes('class="chord-ribbon-flow"'), 'Flow container created');
        assert.ok(mockContainer.innerHTML.includes('ribbon-chord-name'), 'Chord names present');
        assert.ok(mockContainer.innerHTML.includes('F#'), 'First chord F# rendered');
        assert.ok(mockContainer.innerHTML.includes('ribbon-measure-bar'), 'Musical measure bar inserted');
    });

    // 2. ChordRibbon active update without DOM rebuild
    test('2. ChordRibbon updateActive modifies classes only', () => {
        const mockItem1 = { dataset: { start: '0', end: '4' }, classList: { add(c){ this[c]=true; }, remove(c){ delete this[c]; } }, getBoundingClientRect: () => ({ left: 0, right: 50 }) };
        const mockItem2 = { dataset: { start: '4', end: '8' }, classList: { add(c){ this[c]=true; }, remove(c){ delete this[c]; } }, getBoundingClientRect: () => ({ left: 60, right: 110 }) };
        const mockContainer = {
            scrollWidth: 100,
            clientWidth: 200,
            getBoundingClientRect: () => ({ left: 0, right: 200 }),
            querySelectorAll: () => [mockItem1, mockItem2]
        };

        global.ChordRibbon.updateActive(mockContainer, 2.5);
        assert.strictEqual(mockItem1.classList['active-chord'], true, 'Item 1 active at 2.5s');
        assert.strictEqual(mockItem2.classList['active-chord'], undefined, 'Item 2 inactive');

        global.ChordRibbon.updateActive(mockContainer, 5.0);
        assert.strictEqual(mockItem1.classList['active-chord'], undefined, 'Item 1 deactivated');
        assert.strictEqual(mockItem2.classList['active-chord'], true, 'Item 2 active at 5.0s');
    });

    // 3. New single workspace structure verification
    test('3. Single workspace shell layout present in index.html', () => {
        const html = fs.readFileSync(path.join(__dirname, '../frontend/index.html'), 'utf8');
        // New workspace header (replaces app-header)
        assert.ok(html.includes('class="ws-header"'),        'Workspace header present');
        // New meta strip (replaces song-meta-strip)
        assert.ok(html.includes('class="ws-meta"'),          'Workspace meta present');
        // Mode selector (replaces tab-nav-strip)
        assert.ok(html.includes('class="ws-mode-selector"'), 'Mode selector present');
        // New playback row (replaces playback-bar-container)
        assert.ok(html.includes('class="ws-playback"'),      'Workspace playback row present');
        // Persistent piano dock (replaces piano-dock)
        assert.ok(html.includes('class="ws-piano"'),         'Workspace piano row present');
        // Learning area (replaces music-player-stage)
        assert.ok(html.includes('class="ws-learning-area"'), 'Workspace learning area present');
    });

    // 4. Piano visible across all modes (rendered once, never moved)
    test('4. Piano keyboard is rendered once and shared across all modes', () => {
        const html = fs.readFileSync(path.join(__dirname, '../frontend/index.html'), 'utf8');
        const pianoMatches = (html.match(/id="piano-keyboard"/g) || []).length;
        assert.strictEqual(pianoMatches, 1, 'Exactly one piano-keyboard in DOM');
        // ws-piano contains the piano (no per-mode duplication)
        assert.ok(html.includes('class="ws-piano"'), 'ws-piano wrapper present');
    });

    // 5. CSS tokens and responsive rules in piano.css
    test('5. Responsive piano-height and clamp layouts in piano.css', () => {
        const css = fs.readFileSync(path.join(__dirname, '../frontend/css/piano.css'), 'utf8');
        assert.ok(css.includes('--piano-height: clamp('), 'Responsive piano height clamp token defined');
        assert.ok(css.includes('.app-shell'), 'Application shell styling defined');
        assert.ok(css.includes('.ws-learning-area'), 'Workspace learning area styled');
        assert.ok(css.includes('.chord-card'), 'Chord card typography and layout styled');
    });


    // 6. DynamicChordReel component renders 3-chord flow (PREV < CURRENT > NEXT)
    test('6. DynamicChordReel initial DOM structure renders 3 chords with no box clutter', () => {
        let mockContainer = { innerHTML: '', querySelector: () => ({ onclick: null }) };
        const reel = new global.DynamicChordReel({ container: mockContainer });
        reel.loadChords(sampleChords);
        assert.ok(mockContainer.innerHTML.includes('class="shared-chord-timeline'), 'Shared chord timeline rendered');
        assert.ok(mockContainer.innerHTML.includes('id="reel-slot-prev"'), 'Previous chord slot present');
        assert.ok(mockContainer.innerHTML.includes('id="reel-slot-current"'), 'Current chord slot present');
        assert.ok(mockContainer.innerHTML.includes('id="reel-slot-next"'), 'Next chord slot present');
    });

    // 7. DynamicChordReel transitions smoothly right-to-left as playback moves
    test('7. DynamicChordReel transitions previous, current, and next chords on time update', () => {
        const prevNameEl = { textContent: '' };
        const curNameEl = { textContent: '' };
        const curVoicingEl = { textContent: '' };
        const nextNameEl = { textContent: '' };
        const prevSlot = { style: {}, classList: { add(){}, remove(){} } };
        const curSlot = { offsetWidth: 100, classList: { add(){}, remove(){} } };
        const nextSlot = { style: {}, classList: { add(){}, remove(){} } };
        const progFill = { style: {} };
        const conveyorRow = { offsetWidth: 100, classList: { add(){}, remove(){} } };

        const mockContainer = {
            innerHTML: '',
            querySelector(sel) {
                if (sel === '#reel-slot-prev') return prevSlot;
                if (sel === '#reel-prev-name') return prevNameEl;
                if (sel === '#reel-slot-current') return curSlot;
                if (sel === '#reel-current-name') return curNameEl;
                if (sel === '#reel-current-voicing') return curVoicingEl;
                if (sel === '#reel-slot-next') return nextSlot;
                if (sel === '#reel-next-name') return nextNameEl;
                if (sel === '#reel-progress-fill') return progFill;
                if (sel === '#reel-chords-row') return conveyorRow;
                return { textContent: '', style: {}, classList: { add(){}, remove(){} } };
            }
        };

        const reel = new global.DynamicChordReel({ container: mockContainer });
        reel.loadChords(sampleChords);

        // At t = 2.0s -> Chord 0 (F#), Next = Bb, Prev = none
        reel.update(2.0);
        assert.strictEqual(curNameEl.textContent, 'F#', 'Current chord at 2.0s is F#');
        assert.strictEqual(nextNameEl.textContent, 'Bb', 'Next chord at 2.0s is Bb');
        assert.strictEqual(prevNameEl.textContent, '—', 'No previous chord at start');

        // Advance to t = 6.0s -> Chord 1 (Bb), Prev = F#, Next = B
        reel.update(6.0);
        assert.strictEqual(prevNameEl.textContent, 'F#', 'Previous chord transitioned to F#');
        assert.strictEqual(curNameEl.textContent, 'Bb', 'Current chord transitioned to Bb');
        assert.strictEqual(nextNameEl.textContent, 'B', 'Next chord transitioned to B');
    });

    // 8. Single workspace 3-chord timeline replaces 3 separate reel containers
    test('8. All three modes share ONE WorkspaceChordTimeline in index.html', () => {
        const html = fs.readFileSync(path.join(__dirname, '../frontend/index.html'), 'utf8');
        // New: one permanent set of 3 chord cards (no per-mode reel containers)
        assert.ok(html.includes('id="chord-prev"'),    'Permanent chord-prev card present');
        assert.ok(html.includes('id="chord-current"'), 'Permanent chord-current card present');
        assert.ok(html.includes('id="chord-next"'),    'Permanent chord-next card present');
        // WorkspaceChordTimeline script tag loaded
        assert.ok(html.includes('workspaceChordTimeline.js'), 'WorkspaceChordTimeline script loaded');
        // Old per-mode reel containers should be gone
        assert.ok(!html.includes('id="simplified-chord-reel"'), 'Old simplified-chord-reel removed');
        assert.ok(!html.includes('id="practice-chord-reel"'),   'Old practice-chord-reel removed');
        assert.ok(!html.includes('id="play-track-chord-reel"'), 'Old play-track-chord-reel removed');
    });


    // 9. Practice tab integrates Left and Right Hand visual frames
    test('9. DynamicChordReel showHands option embeds left and right hand columns', () => {
        let mockContainer = { innerHTML: '', querySelector: () => ({ onclick: null }) };
        const reel = new global.DynamicChordReel({ container: mockContainer, showHands: true });
        reel.loadChords(sampleChords);
        assert.ok(mockContainer.innerHTML.includes('id="reel-hand-left"'), 'Left hand column rendered');
        assert.ok(mockContainer.innerHTML.includes('id="reel-hand-right"'), 'Right hand column rendered');
    });

    console.log(`\nAll ${passed}/9 HotChords Phase 8 tests PASSED successfully!`);
}

runTests();
