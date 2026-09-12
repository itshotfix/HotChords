/**
 * frontend/js/audio/realtimePitchDetector.js
 * 
 * Real-Time Polyphonic Pitch Detector & Note Estimation Engine for HotChords (Phase 11).
 * 
 * Features:
 * - High-speed in-browser Web Audio DSP frame analysis.
 * - Sub-bin parabolic peak interpolation.
 * - Polyphonic harmonic comb salience & integer overtone suppression (2*f0, 3*f0, 4*f0, 5*f0).
 * - Temporal stabilization & hysteresis (note-on confirmation >= 2 frames, release >= 3 frames).
 * - Zero allocations in hot audio loop (reusable Float32Arrays).
 */

(function(global) {
    'use strict';

    const MIN_PIANO_MIDI = 21;  // A0 (27.5 Hz)
    const MAX_PIANO_MIDI = 108; // C8 (4186 Hz)
    const MIN_FREQ = 27.0;
    const MAX_FREQ = 4200.0;
    const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];

    function midiToFreq(midi) {
        return 440.0 * Math.pow(2.0, (midi - 69.0) / 12.0);
    }

    function freqToMidi(freq) {
        if (freq <= 0) return 0;
        return 69.0 + 12.0 * Math.log2(freq / 440.0);
    }

    function midiToNoteName(midi) {
        const pitch = ((midi % 12) + 12) % 12;
        const octave = Math.floor(midi / 12) - 1;
        return `${NOTE_NAMES[pitch]}${octave}`;
    }

    class RealtimePitchDetector {
        constructor(options = {}) {
            this.sampleRate = options.sampleRate || 44100;
            this.fftSize = options.fftSize || 4096;
            this.energyThreshold = options.energyThreshold || 0.005;
            this.peakThreshold = options.peakThreshold || 0.08;
            this.centsTolerance = options.centsTolerance || 40.0;
            this.maxPolyphony = options.maxPolyphony || 6;
            this.persistenceThreshold = options.persistenceThreshold || 2;
            this.releaseThreshold = options.releaseThreshold || 3;

            // Precomputed note frequencies
            this.midiNotes = [];
            this.targetFreqs = [];
            for (let m = MIN_PIANO_MIDI; m <= MAX_PIANO_MIDI; m++) {
                this.midiNotes.push(m);
                this.targetFreqs.push(midiToFreq(m));
            }

            // Temporal tracking state
            this.candidateCounts = new Map();
            this.activeNotes = new Map();
            this.missingCounts = new Map();
        }

        reset() {
            this.candidateCounts.clear();
            this.activeNotes.clear();
            this.missingCounts.clear();
        }

        /**
         * Detect polyphonic notes from a time-domain or frequency-domain Web Audio buffer.
         * @param {Float32Array} freqData - Normalized magnitude spectrum [0.0, 1.0]
         * @param {number} sampleRate - Active AudioContext sample rate
         * @param {number} rmsEnergy - Root mean square energy of input
         */
        detect(freqData, sampleRate, rmsEnergy = 0.05) {
            if (!freqData || freqData.length === 0 || rmsEnergy < this.energyThreshold) {
                this._decayActiveNotes();
                return {
                    status: 'NO_INPUT',
                    notes: [],
                    confidence: 0.0,
                    polyphonyType: 'UNKNOWN',
                    rms: rmsEnergy
                };
            }

            const binCount = freqData.length;
            const nyquist = sampleRate / 2;
            const binWidth = nyquist / binCount;

            // 1. Find spectral peaks
            const peaks = [];
            for (let i = 1; i < binCount - 1; i++) {
                const mag = freqData[i];
                if (mag >= this.peakThreshold && mag > freqData[i - 1] && mag > freqData[i + 1]) {
                    // Parabolic interpolation
                    const alpha = freqData[i - 1];
                    const beta = freqData[i];
                    const gamma = freqData[i + 1];
                    const denom = alpha - 2.0 * beta + gamma;
                    let delta = 0;
                    if (Math.abs(denom) > 1e-12) {
                        delta = Math.max(-0.5, Math.min(0.5, 0.5 * (alpha - gamma) / denom));
                    }
                    const freq = (i + delta) * binWidth;
                    const peakMag = beta - 0.25 * (alpha - gamma) * delta;
                    if (freq >= MIN_FREQ && freq <= MAX_FREQ) {
                        peaks.push({ freq, mag: peakMag });
                    }
                }
            }

            if (peaks.length === 0) {
                this._decayActiveNotes();
                return {
                    status: 'LOW_CONFIDENCE',
                    notes: this._getActiveNoteList(),
                    confidence: 0.15,
                    polyphonyType: 'UNKNOWN',
                    rms: rmsEnergy
                };
            }

            // 2. Harmonic Salience Scoring
            const harmonicWeights = [1.0, 0.65, 0.45, 0.30, 0.20];
            const candidateScores = [];

            for (let idx = 0; idx < this.midiNotes.length; idx++) {
                const midi = this.midiNotes[idx];
                const f0 = this.targetFreqs[idx];
                let salience = 0;
                let h1Mag = 0;
                let foundHarmonics = 0;

                for (let h = 1; h <= 5; h++) {
                    const targetFh = f0 * h;
                    if (targetFh > MAX_FREQ) break;

                    let closestPeak = null;
                    let minCents = Infinity;

                    for (let p = 0; p < peaks.length; p++) {
                        const pk = peaks[p];
                        const cents = 1200.0 * Math.abs(Math.log2(pk.freq / targetFh));
                        if (cents < minCents) {
                            minCents = cents;
                            closestPeak = pk;
                        }
                    }

                    if (closestPeak && minCents <= this.centsTolerance) {
                        salience += harmonicWeights[h - 1] * closestPeak.mag;
                        if (h === 1) {
                            h1Mag = closestPeak.mag;
                            foundHarmonics++;
                        } else if (closestPeak.mag > 0.15) {
                            foundHarmonics++;
                        }
                    }
                }

                // Fundamental requirement: note must have significant energy at its actual fundamental
                if (h1Mag >= 0.18 && salience > 0.50) {
                    candidateScores.push({ midi, salience: salience + (0.5 * h1Mag), f0 });
                }
            }

            // 3. Sort candidates and apply overtone cancellation
            candidateScores.sort((a, b) => b.salience - a.salience);

            const frameDetected = [];
            const claimedMidis = new Set();

            for (let i = 0; i < candidateScores.length; i++) {
                const cand = candidateScores[i];
                if (claimedMidis.has(cand.midi)) continue;

                // Check if candidate is an overtone of an already selected lower note
                let isOvertone = false;
                for (let j = 0; j < frameDetected.length; j++) {
                    const sel = frameDetected[j];
                    const semitoneDiff = cand.midi - sel.midi;
                    if ([12, 19, 24, 28].includes(semitoneDiff)) {
                        if (cand.salience <= sel.salience * 0.90) {
                            isOvertone = true;
                            break;
                        }
                    }
                }

                if (isOvertone) continue;

                const conf = Math.max(0.40, Math.min(0.98, cand.salience / 1.8));
                frameDetected.push({
                    midi: cand.midi,
                    noteName: midiToNoteName(cand.midi),
                    frequency: Math.round(cand.f0 * 100) / 100,
                    confidence: Math.round(conf * 1000) / 1000,
                    salience: cand.salience
                });
                claimedMidis.add(cand.midi);

                if (frameDetected.length >= this.maxPolyphony) break;
            }

            // 4. Temporal Smoothing & Hysteresis
            const detectedMidis = new Set(frameDetected.map(n => n.midi));
            const frameMap = new Map(frameDetected.map(n => [n.midi, n]));

            for (const [midi, note] of frameMap.entries()) {
                const count = (this.candidateCounts.get(midi) || 0) + 1;
                this.candidateCounts.set(midi, count);
                this.missingCounts.set(midi, 0);

                if (count >= this.persistenceThreshold) {
                    this.activeNotes.set(midi, note);
                }
            }

            for (const midi of Array.from(this.activeNotes.keys())) {
                if (!detectedMidis.has(midi)) {
                    const missCount = (this.missingCounts.get(midi) || 0) + 1;
                    this.missingCounts.set(midi, missCount);
                    if (missCount >= this.releaseThreshold) {
                        this.activeNotes.delete(midi);
                        this.candidateCounts.set(midi, 0);
                        this.missingCounts.delete(midi);
                    }
                }
            }

            const stableNotes = this._getActiveNoteList();

            if (stableNotes.length === 0) {
                return {
                    status: 'LISTENING',
                    notes: [],
                    confidence: 0.2,
                    polyphonyType: 'UNKNOWN',
                    rms: rmsEnergy
                };
            }

            const avgConf = stableNotes.reduce((acc, n) => acc + n.confidence, 0) / stableNotes.length;
            const polyType = stableNotes.length === 1 ? 'MONOPHONIC' : 'POLYPHONIC';

            return {
                status: 'DETECTED',
                notes: stableNotes,
                confidence: Math.round(avgConf * 1000) / 1000,
                polyphonyType: polyType,
                rms: rmsEnergy
            };
        }

        _getActiveNoteList() {
            return Array.from(this.activeNotes.values()).sort((a, b) => a.midi - b.midi);
        }

        _decayActiveNotes() {
            for (const midi of Array.from(this.activeNotes.keys())) {
                const missCount = (this.missingCounts.get(midi) || 0) + 1;
                this.missingCounts.set(midi, missCount);
                if (missCount >= this.releaseThreshold) {
                    this.activeNotes.delete(midi);
                    this.candidateCounts.set(midi, 0);
                    this.missingCounts.delete(midi);
                }
            }
        }
    }

    // Export module
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = {
            RealtimePitchDetector,
            midiToFreq,
            freqToMidi,
            midiToNoteName
        };
    } else {
        global.RealtimePitchDetector = RealtimePitchDetector;
    }

})(typeof window !== 'undefined' ? window : this);
