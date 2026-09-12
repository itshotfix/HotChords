/**
 * frontend/js/audio/inputCalibrationService.js
 * 
 * In-Browser Microphone Input Calibration & Noise Gate Engine for HotChords (Phase 12).
 * 
 * Features:
 * - 100% in-memory transient processing; zero audio files stored or uploaded.
 * - Robust noise floor estimation via median RMS and spectral flatness over 2 seconds.
 * - Dynamic noise gate calculation (avoids fragile fixed global thresholds).
 * - Signal quality classification: CALIBRATING, READY, GOOD_SIGNAL, WEAK_SIGNAL, NOISE, CLIPPING, LOW_CONFIDENCE.
 */

(function(global) {
    'use strict';

    const SignalQualityState = {
        CALIBRATING: 'CALIBRATING',
        READY: 'READY',
        GOOD_SIGNAL: 'GOOD_SIGNAL',
        WEAK_SIGNAL: 'WEAK_SIGNAL',
        NOISE: 'NOISE',
        CLIPPING: 'CLIPPING',
        LOW_CONFIDENCE: 'LOW_CONFIDENCE'
    };

    const _raf = typeof requestAnimationFrame !== 'undefined' ? requestAnimationFrame : (cb) => setTimeout(cb, 20);
    const _caf = typeof cancelAnimationFrame !== 'undefined' ? cancelAnimationFrame : (id) => clearTimeout(id);

    class InputCalibrationService {
        constructor() {
            this.isCalibrating = false;
            this.calibrationDurationMs = 2000;
            this.startTime = 0;
            this.rmsValues = [];
            this.peakValues = [];
            this.flatnessValues = [];
            this.clippedCount = 0;
            this.totalSamples = 0;

            this.profile = {
                sampleRate: 44100,
                noiseFloorRms: 0.005,
                noiseGateRms: 0.012,
                peakLevel: 0.0,
                dynamicRangeDb: 40.0,
                spectralFlatness: 0.05,
                clippingRatio: 0.0,
                signalQuality: SignalQualityState.READY,
                calibrationTimestamp: Date.now()
            };

            this.listeners = [];
            this._animFrameId = null;
        }

        subscribe(callback) {
            if (typeof callback === 'function') {
                this.listeners.push(callback);
            }
            return () => {
                this.listeners = this.listeners.filter(cb => cb !== callback);
            };
        }

        _notify(event) {
            for (let i = 0; i < this.listeners.length; i++) {
                try {
                    this.listeners[i](event);
                } catch (e) {
                    console.error('[InputCalibrationService] Listener error:', e);
                }
            }
        }

        startCalibration(inputService, durationMs = 2000) {
            this.reset();
            this.isCalibrating = true;
            this.calibrationDurationMs = Math.max(500, Math.min(10000, durationMs));
            this.startTime = Date.now();

            this._notify({ type: 'CALIBRATION_START', durationMs: this.calibrationDurationMs });

            const checkProgress = () => {
                if (!this.isCalibrating) return;

                const elapsed = Date.now() - this.startTime;
                const progress = Math.min(1.0, elapsed / this.calibrationDurationMs);

                // Read active frame from inputService if available
                if (inputService && inputService.analyserNode && inputService.timeData) {
                    inputService.analyserNode.getFloatTimeDomainData(inputService.timeData);
                    this.processFrame(inputService.timeData, inputService.freqData);
                }

                this._notify({
                    type: 'CALIBRATION_PROGRESS',
                    progress: Math.round(progress * 100) / 100,
                    rms: this.rmsValues.length > 0 ? this.rmsValues[this.rmsValues.length - 1] : 0.0
                });

                if (progress >= 1.0) {
                    this.finishCalibration(inputService);
                } else {
                    this._animFrameId = _raf(checkProgress);
                }
            };

            this._animFrameId = _raf(checkProgress);
        }

        processFrame(timeData, freqData) {
            if (!timeData || timeData.length === 0) return;

            let sumSquares = 0;
            let peak = 0;
            let clipped = 0;

            for (let i = 0; i < timeData.length; i++) {
                const val = Math.abs(timeData[i]);
                sumSquares += val * val;
                if (val > peak) peak = val;
                if (val >= 0.98) clipped++;
            }

            const rms = Math.sqrt(sumSquares / timeData.length);
            this.rmsValues.push(rms);
            this.peakValues.push(peak);
            this.clippedCount += clipped;
            this.totalSamples += timeData.length;

            // Approximate spectral flatness
            let flatness = 0.05;
            if (freqData && freqData.length > 0) {
                let logSum = 0;
                let powerSum = 0;
                for (let i = 0; i < freqData.length; i++) {
                    const p = Math.max(1e-12, Math.pow(10, freqData[i] / 10));
                    logSum += Math.log(p);
                    powerSum += p;
                }
                const geom = Math.exp(logSum / freqData.length);
                const arith = powerSum / freqData.length;
                if (arith > 1e-12) flatness = Math.min(1.0, geom / arith);
            }
            this.flatnessValues.push(flatness);
        }

        finishCalibration(inputService = null) {
            this.isCalibrating = false;
            if (this._animFrameId) {
                _caf(this._animFrameId);
                this._animFrameId = null;
            }

            if (this.rmsValues.length === 0) {
                this.profile.signalQuality = SignalQualityState.READY;
                this._notify({ type: 'CALIBRATION_COMPLETE', profile: this.profile });
                return this.profile;
            }

            // Compute statistics
            const sortedRms = [...this.rmsValues].sort((a, b) => a - b);
            const medianRms = sortedRms[Math.floor(sortedRms.length / 2)];
            const p90Rms = sortedRms[Math.floor(sortedRms.length * 0.90)];
            const peakLevel = Math.max(...this.peakValues);
            
            const sortedFlatness = [...this.flatnessValues].sort((a, b) => a - b);
            const medianFlatness = sortedFlatness[Math.floor(sortedFlatness.length / 2)];
            const clipRatio = this.clippedCount / Math.max(1, this.totalSamples);

            // Dynamic noise gate
            const noiseGateRms = Math.max(0.004, Math.min(0.08, Math.max(medianRms * 2.2, p90Rms * 1.3)));

            // Dynamic range in dB
            const dynamicRangeDb = (medianRms > 1e-6 && peakLevel > medianRms)
                ? 20 * Math.log10(Math.max(1.0, peakLevel) / medianRms)
                : 40.0;

            let quality = SignalQualityState.READY;
            if (clipRatio > 0.05) quality = SignalQualityState.CLIPPING;
            else if (medianFlatness > 0.25 || medianRms > 0.05) quality = SignalQualityState.NOISE;

            this.profile = {
                sampleRate: inputService && inputService.audioCtx ? inputService.audioCtx.sampleRate : 44100,
                noiseFloorRms: Math.round(medianRms * 100000) / 100000,
                noiseGateRms: Math.round(noiseGateRms * 100000) / 100000,
                peakLevel: Math.round(peakLevel * 10000) / 10000,
                dynamicRangeDb: Math.round(dynamicRangeDb * 10) / 10,
                spectralFlatness: Math.round(medianFlatness * 10000) / 10000,
                clippingRatio: Math.round(clipRatio * 100000) / 100000,
                signalQuality: quality,
                calibrationTimestamp: Date.now()
            };

            // Propagate dynamic thresholds to PitchDetector if attached
            if (inputService && inputService.detector) {
                inputService.detector.energyThreshold = this.profile.noiseGateRms;
            }

            this._notify({ type: 'CALIBRATION_COMPLETE', profile: this.profile });

            // Clear transient arrays
            this.rmsValues = [];
            this.peakValues = [];
            this.flatnessValues = [];
            this.clippedCount = 0;

            return this.profile;
        }

        reset() {
            this.isCalibrating = false;
            if (this._animFrameId) {
                _caf(this._animFrameId);
                this._animFrameId = null;
            }
            this.rmsValues = [];
            this.peakValues = [];
            this.flatnessValues = [];
            this.clippedCount = 0;
            this.totalSamples = 0;
        }
    }

    // Export module
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = {
            InputCalibrationService,
            SignalQualityState
        };
    } else {
        global.InputCalibrationService = new InputCalibrationService();
        global.SignalQualityState = SignalQualityState;
    }

})(typeof window !== 'undefined' ? window : this);
