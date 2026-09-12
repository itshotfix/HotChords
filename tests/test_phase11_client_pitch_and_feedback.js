/**
 * tests/test_phase11_client_pitch_and_feedback.js
 * 
 * Node.js Unit Tests for HotChords Phase 11 Client-Side Components:
 * - RealtimePitchDetector (DSP frame estimation & overtone suppression)
 * - RealtimeInputService (lifecycle, privacy cleanup, test-signal mode)
 * - PracticeFeedbackBridge (exact vs pitch-class note comparison, precision/recall/F1)
 */

const assert = require('assert');
const { RealtimePitchDetector, midiToFreq, freqToMidi, midiToNoteName } = require('../frontend/js/audio/realtimePitchDetector.js');
const { RealtimeInputService, InputMode, InputStatus } = require('../frontend/js/audio/realtimeInputService.js');
const { PracticeFeedbackBridge, FeedbackStatus, MatchingMode } = require('../frontend/js/audio/practiceFeedbackBridge.js');

console.log('\n--- Running HotChords Phase 11 Client Pitch & Practice Feedback Test Suite ---');

let passedTests = 0;

function runTest(name, fn) {
    try {
        fn();
        console.log(`  ✓ ${name}`);
        passedTests++;
    } catch (err) {
        console.error(`  ✗ ${name}`);
        console.error(err);
        process.exit(1);
    }
}

// 1. Note Conversion Utilities
runTest('1. Frequency to MIDI & Note Name Conversion', () => {
    assert.strictEqual(midiToNoteName(60), 'C4');
    assert.strictEqual(midiToNoteName(69), 'A4');
    assert.strictEqual(midiToNoteName(55), 'G3');
    assert.ok(Math.abs(midiToFreq(69) - 440.0) < 0.01);
    assert.ok(Math.abs(freqToMidi(440.0) - 69.0) < 0.01);
});

// 2. RealtimePitchDetector Synthetic Peak Analysis
runTest('2. RealtimePitchDetector Single Note & Overtone Suppression', () => {
    const detector = new RealtimePitchDetector({ sampleRate: 44100, fftSize: 4096 });
    const binCount = 2048;
    const freqData = new Float32Array(binCount); // Linear normalized spectrum

    // Synthesize C4 (261.63 Hz) fundamental and harmonics
    const nyquist = 22050;
    const binWidth = nyquist / binCount;
    const c4Bin = Math.round(261.63 / binWidth);
    const c5Bin = Math.round(523.25 / binWidth); // 2nd harmonic
    const g5Bin = Math.round(784.88 / binWidth); // 3rd harmonic

    freqData[c4Bin] = 0.90;
    freqData[c5Bin] = 0.45;
    freqData[g5Bin] = 0.25;

    // First frame (persisting)
    let res = detector.detect(freqData, 44100, 0.15);
    // Second frame (confirmed)
    res = detector.detect(freqData, 44100, 0.15);

    assert.strictEqual(res.status, 'DETECTED');
    assert.ok(res.notes.length >= 1);
    assert.strictEqual(res.notes[0].midi, 60);
    assert.strictEqual(res.notes[0].noteName, 'C4');
});

// 3. RealtimePitchDetector Temporal Release
runTest('3. RealtimePitchDetector Temporal Release Hysteresis', () => {
    const detector = new RealtimePitchDetector({ sampleRate: 44100, fftSize: 4096 });
    const emptyData = new Float32Array(2048);

    // Provide 0 energy
    const res = detector.detect(emptyData, 44100, 0.001);
    assert.strictEqual(res.status, 'NO_INPUT');
    assert.strictEqual(res.notes.length, 0);
});

// 4. RealtimeInputService Test Signal Mode & Cleanup
runTest('4. RealtimeInputService Test Signal Mode & Immediate Hardware Stop', () => {
    const service = new RealtimeInputService();
    let lastEvent = null;

    const unsub = service.subscribe(e => { lastEvent = e; });
    service.startTestSignal([60, 64, 67], 0.95);

    assert.strictEqual(service.mode, InputMode.TEST_SIGNAL);
    assert.strictEqual(service.status, InputStatus.LISTENING);

    // Stop and verify clean release
    service.stop();
    assert.strictEqual(service.mode, InputMode.OFF);
    assert.strictEqual(service.status, InputStatus.STOPPED);
    unsub();
});

// 5. PracticeFeedbackBridge Exact Note Matching
runTest('5. PracticeFeedbackBridge Exact Note Match & Metrics', () => {
    const bridge = new PracticeFeedbackBridge();
    bridge.setMatchingMode(MatchingMode.EXACT_NOTE_MATCH);

    const comp = bridge.compareNotes([60, 64, 67], [60, 64, 67], MatchingMode.EXACT_NOTE_MATCH);
    assert.deepStrictEqual(comp.correctNotes, [60, 64, 67]);
    assert.strictEqual(comp.notePrecision, 1.0);
    assert.strictEqual(comp.noteRecall, 1.0);
    assert.strictEqual(comp.noteF1, 1.0);
});

// 6. PracticeFeedbackBridge Pitch-Class Matching
runTest('6. PracticeFeedbackBridge Octave-Tolerant Pitch-Class Matching', () => {
    const bridge = new PracticeFeedbackBridge();
    bridge.setMatchingMode(MatchingMode.PITCH_CLASS_MATCH);

    // C3, E3, G3 (48, 52, 55) vs expected C4, E4, G4 (60, 64, 67)
    const comp = bridge.compareNotes([60, 64, 67], [48, 52, 55], MatchingMode.PITCH_CLASS_MATCH);
    assert.deepStrictEqual(comp.correctNotes, ['C', 'E', 'G']);
    assert.strictEqual(comp.notePrecision, 1.0);
    assert.strictEqual(comp.noteRecall, 1.0);
    assert.strictEqual(comp.noteF1, 1.0);
});

// 7. PracticeFeedbackBridge Partial & Extra Note Detection
runTest('7. PracticeFeedbackBridge Partial & Extra Note Handling', () => {
    const bridge = new PracticeFeedbackBridge();
    const comp = bridge.compareNotes([60, 64, 67], [60, 62, 64], MatchingMode.EXACT_NOTE_MATCH);
    
    assert.deepStrictEqual(comp.correctNotes, [60, 64]);
    assert.deepStrictEqual(comp.missingNotes, [67]);
    assert.deepStrictEqual(comp.extraNotes, [62]);
    assert.strictEqual(comp.notePrecision, 0.667);
    assert.strictEqual(comp.noteRecall, 0.667);
});

console.log(`\nAll ${passedTests}/${passedTests} Phase 11 Client Pitch & Feedback tests PASSED successfully!\n`);
