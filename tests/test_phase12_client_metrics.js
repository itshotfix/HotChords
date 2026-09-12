/**
 * tests/test_phase12_client_metrics.js
 * 
 * Node.js Unit Tests for HotChords Phase 12 Client-Side Components:
 * - InputCalibrationService (noise floor, dynamic noise gate, signal quality)
 * - PracticeMetricsTracker (event buffer, per-chord mastery, targeted recommendations, adaptive tempo)
 */

const assert = require('assert');
const { InputCalibrationService, SignalQualityState } = require('../frontend/js/audio/inputCalibrationService.js');
const { PracticeMetricsTracker, PlayerFeedbackEventType } = require('../frontend/js/audio/practiceMetricsTracker.js');

console.log('\n--- Running HotChords Phase 12 Client Metrics & Calibration Test Suite ---');

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

// 1. InputCalibrationService Lifecycle & Noise Gate
runTest('1. InputCalibrationService Noise Floor & Dynamic Gate Derivation', () => {
    const calib = new InputCalibrationService();
    calib.startCalibration(null, 500);

    // Feed low-amplitude ambient noise frames (RMS ~ 0.003)
    for (let f = 0; f < 20; f++) {
        const timeData = new Float32Array(2048);
        for (let i = 0; i < 2048; i++) {
            timeData[i] = (Math.random() - 0.5) * 0.006;
        }
        calib.processFrame(timeData, null);
    }

    const profile = calib.finishCalibration(null);

    assert.ok(profile.noiseFloorRms > 0.0);
    assert.ok(profile.noiseGateRms > profile.noiseFloorRms);
    assert.strictEqual(profile.signalQuality, SignalQualityState.READY);
});

// 2. PracticeMetricsTracker Event Accumulation & Bounded Buffer
runTest('2. PracticeMetricsTracker Bounded Ring Buffer (Max 50)', () => {
    const tracker = new PracticeMetricsTracker(50);
    tracker.startSession(0.0);

    // Record 110 events
    for (let i = 0; i < 110; i++) {
        tracker.recordEvent({
            eventType: PlayerFeedbackEventType.CHORD_MATCHED,
            timestamp: i * 0.5,
            chordName: 'C',
            expectedMidi: [60, 64, 67],
            observedMidi: [60, 64, 67],
            timingOffsetMs: 25.0,
            notePrecision: 1.0,
            noteRecall: 1.0,
            noteF1: 1.0
        });
    }

    assert.strictEqual(tracker.recentEvents.length, 50);
    assert.strictEqual(tracker.chordsAttempted, 110);
    assert.strictEqual(tracker.chordsMatched, 110);

    const summary = tracker.getSessionSummary();
    assert.strictEqual(summary.chordsAttempted, 110);
    assert.strictEqual(summary.chordsMatched, 110);
    assert.strictEqual(summary.notePrecision, 1.0);
    assert.strictEqual(summary.averageTimingOffsetMs, 25.0);
});

// 3. PracticeMetricsTracker Per-Chord Mastery & Targeted Recommendations
runTest('3. Per-Chord Mastery & Targeted Practice Recommendations', () => {
    const tracker = new PracticeMetricsTracker(50);

    // Record 3 misses for C#m
    for (let i = 0; i < 3; i++) {
        tracker.recordEvent({
            eventType: PlayerFeedbackEventType.CHORD_MISSED,
            timestamp: i * 2.0,
            chordName: 'C#m',
            timingOffsetMs: 180.0
        });
    }

    // Record 3 matches for C
    for (let i = 0; i < 3; i++) {
        tracker.recordEvent({
            eventType: PlayerFeedbackEventType.CHORD_MATCHED,
            timestamp: 10 + i * 2.0,
            chordName: 'C',
            timingOffsetMs: 160.0,
            notePrecision: 0.65,
            noteRecall: 1.0
        });
    }

    const mastery = tracker.getChordMasteryMap();
    assert.ok(mastery['C#m']);
    assert.strictEqual(mastery['C#m'].misses, 3);
    assert.strictEqual(mastery['C#m'].avgNoteRecall, 0.0);

    assert.ok(mastery['C']);
    assert.strictEqual(mastery['C'].matches, 3);
    assert.strictEqual(mastery['C'].avgNoteRecall, 1.0);

    const recs = tracker.getTargetedRecommendations();
    const recTypes = recs.map(r => r.type);

    assert.ok(recTypes.includes('CHORD_FOCUS'));
    assert.ok(recTypes.includes('TIMING'));
    assert.ok(recTypes.includes('ACCURACY'));
});

// 4. PracticeMetricsTracker Adaptive Tempo Recommendation
runTest('4. Conservative Adaptive Tempo Advice', () => {
    const tracker = new PracticeMetricsTracker(50);

    // Simulate 2 flawless loops
    for (let l = 0; l < 2; l++) {
        for (let i = 0; i < 4; i++) {
            tracker.recordEvent({
                eventType: PlayerFeedbackEventType.CHORD_MATCHED,
                chordName: 'C'
            });
        }
        tracker.recordLoopCompleted();
    }

    const advice = tracker.getAdaptiveTempoRecommendation(60.0, 120.0);
    assert.strictEqual(advice.recommendation, 'INCREASE_TEMPO');
    assert.strictEqual(advice.recommendedBpm, 63.0);
});

// 5. PracticeMetricsTracker Export Report & Reset
runTest('5. Exportable Session Report & Reset', () => {
    const tracker = new PracticeMetricsTracker(50);
    tracker.recordEvent({
        eventType: PlayerFeedbackEventType.CHORD_MATCHED,
        chordName: 'G'
    });

    const report = tracker.exportSessionReport();
    assert.ok(report.summary);
    assert.ok(report.chordMastery);
    assert.ok(report.recommendations);

    tracker.resetSession();
    assert.strictEqual(tracker.recentEvents.length, 0);
    assert.strictEqual(tracker.chordsAttempted, 0);
});

console.log(`\nAll ${passedTests}/${passedTests} Phase 12 Client Metrics & Calibration tests PASSED successfully!\n`);
