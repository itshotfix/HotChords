/**
 * frontend/js/audio/realtimeInputService.js
 * 
 * Local Real-Time Audio Input Manager for HotChords (Phase 11).
 * 
 * Privacy & Security Invariants:
 * 1. 100% Local Processing: Zero cloud uploads, zero external API calls.
 * 2. Transient In-Memory Only: No persistent audio files (.wav, .mp3, etc.) are written to disk.
 * 3. Immediate Hardware Release: All MediaStream tracks are explicitly stopped (`track.stop()`) on session stop.
 * 4. Single AudioContext: Reuses the shared AudioContext from PianoPlaybackService.
 * 5. Input Modes: MICROPHONE, TEST_SIGNAL, OFF.
 */

(function(global) {
    'use strict';

    const InputMode = {
        OFF: 'OFF',
        MICROPHONE: 'MICROPHONE',
        TEST_SIGNAL: 'TEST_SIGNAL'
    };

    const InputStatus = {
        UNINITIALIZED: 'UNINITIALIZED',
        PERMISSION_REQUESTED: 'PERMISSION_REQUESTED',
        LISTENING: 'LISTENING',
        PERMISSION_DENIED: 'INPUT_PERMISSION_DENIED',
        UNAVAILABLE: 'INPUT_UNAVAILABLE',
        UNSUPPORTED: 'INPUT_UNSUPPORTED',
        STOPPED: 'STOPPED'
    };

    const _raf = typeof requestAnimationFrame !== 'undefined' ? requestAnimationFrame : (cb) => setTimeout(cb, 20);
    const _caf = typeof cancelAnimationFrame !== 'undefined' ? cancelAnimationFrame : (id) => clearTimeout(id);

    class RealtimeInputService {
        constructor() {
            this.mode = InputMode.OFF;
            this.status = InputStatus.UNINITIALIZED;
            this.audioCtx = null;
            this.mediaStream = null;
            this.sourceNode = null;
            this.analyserNode = null;
            this.freqData = null;
            this.timeData = null;
            this.listeners = [];
            this.detector = null;
            this._animFrameId = null;
            this._lastRms = 0;
            this.testSignalNotes = [];
            this.testSignalConfidence = 1.0;
        }

        /**
         * Subscribe to detection / status updates.
         */
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
                    console.error('[RealtimeInputService] Listener error:', e);
                }
            }
        }

        /**
         * Start microphone listening.
         * @param {AudioContext} sharedAudioCtx - Optional shared audio context
         */
        async startMicrophone(sharedAudioCtx = null) {
            this.stop(); // Ensure clean previous state

            this.mode = InputMode.MICROPHONE;
            this.status = InputStatus.PERMISSION_REQUESTED;
            this._notify({ type: 'STATUS_CHANGE', status: this.status, mode: this.mode });

            // Check browser support
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                this.status = InputStatus.UNSUPPORTED;
                this._notify({ type: 'STATUS_CHANGE', status: this.status, mode: this.mode, error: 'getUserMedia not supported' });
                return false;
            }

            try {
                // Initialize audio context
                if (sharedAudioCtx) {
                    this.audioCtx = sharedAudioCtx;
                } else if (global.PianoPlaybackService && global.PianoPlaybackService.audioCtx) {
                    this.audioCtx = global.PianoPlaybackService.audioCtx;
                } else {
                    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
                    if (!this.audioCtx && AudioContextClass) {
                        this.audioCtx = new AudioContextClass();
                    }
                }

                if (this.audioCtx && this.audioCtx.state === 'suspended') {
                    await this.audioCtx.resume();
                }

                // Request raw audio without destructive AGC or noise suppression for cleaner piano pitch analysis
                this.mediaStream = await navigator.mediaDevices.getUserMedia({
                    audio: {
                        echoCancellation: false,
                        noiseSuppression: false,
                        autoGainControl: false,
                        channelCount: 1
                    },
                    video: false
                });

                // Create Web Audio Analyser
                this.sourceNode = this.audioCtx.createMediaStreamSource(this.mediaStream);
                this.analyserNode = this.audioCtx.createAnalyser();
                this.analyserNode.fftSize = 4096;
                this.analyserNode.smoothingTimeConstant = 0.4;

                this.sourceNode.connect(this.analyserNode);

                const binCount = this.analyserNode.frequencyBinCount;
                this.freqData = new Float32Array(binCount);
                this.timeData = new Float32Array(this.analyserNode.fftSize);

                if (!this.detector && global.RealtimePitchDetector) {
                    this.detector = new global.RealtimePitchDetector({
                        sampleRate: this.audioCtx.sampleRate,
                        fftSize: this.analyserNode.fftSize
                    });
                }

                this.status = InputStatus.LISTENING;
                this._notify({ type: 'STATUS_CHANGE', status: this.status, mode: this.mode });

                // Start analysis processing loop
                this._startProcessingLoop();
                return true;

            } catch (err) {
                if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
                    this.status = InputStatus.PERMISSION_DENIED;
                } else {
                    this.status = InputStatus.UNAVAILABLE;
                }
                this._notify({ type: 'STATUS_CHANGE', status: this.status, mode: this.mode, error: err.message });
                this.stop();
                return false;
            }
        }

        /**
         * Start deterministic synthetic test signal mode.
         */
        startTestSignal(initialNotes = [60, 64, 67], confidence = 0.95) {
            this.stop();
            this.mode = InputMode.TEST_SIGNAL;
            this.status = InputStatus.LISTENING;
            this.testSignalNotes = initialNotes;
            this.testSignalConfidence = confidence;

            this._notify({ type: 'STATUS_CHANGE', status: this.status, mode: this.mode });
            this._startProcessingLoop();
            return true;
        }

        /**
         * Update test signal notes dynamically.
         */
        setTestSignalNotes(notes, confidence = 0.95) {
            this.testSignalNotes = notes;
            this.testSignalConfidence = confidence;
        }

        /**
         * Main analysis frame loop (runs via requestAnimationFrame or timer).
         */
        _startProcessingLoop() {
            if (this._animFrameId) {
                _caf(this._animFrameId);
            }

            const loop = () => {
                if (this.mode === InputMode.OFF) return;

                if (this.mode === InputMode.MICROPHONE && this.analyserNode && this.detector) {
                    // Read frequency and time data
                    this.analyserNode.getFloatFrequencyData(this.freqData);
                    this.analyserNode.getFloatTimeDomainData(this.timeData);

                    // Compute RMS energy
                    let sumSquares = 0;
                    for (let i = 0; i < this.timeData.length; i++) {
                        sumSquares += this.timeData[i] * this.timeData[i];
                    }
                    this._lastRms = Math.sqrt(sumSquares / this.timeData.length);

                    // Convert dB frequency values [-100, -30] to linear normalized magnitude [0.0, 1.0]
                    const linearMag = new Float32Array(this.freqData.length);
                    for (let i = 0; i < this.freqData.length; i++) {
                        const db = this.freqData[i];
                        const norm = Math.max(0, Math.min(1.0, (db + 100.0) / 70.0));
                        linearMag[i] = norm;
                    }

                    const result = this.detector.detect(linearMag, this.audioCtx.sampleRate, this._lastRms);
                    this._notify({
                        type: 'NOTE_DETECTION',
                        inputStatus: this.status,
                        mode: this.mode,
                        ...result
                    });

                } else if (this.mode === InputMode.TEST_SIGNAL) {
                    const notes = (this.testSignalNotes || []).map(midi => ({
                        midi,
                        noteName: global.RealtimePitchDetector ? global.RealtimePitchDetector.midiToNoteName(midi) : `MIDI_${midi}`,
                        frequency: global.RealtimePitchDetector ? global.RealtimePitchDetector.midiToFreq(midi) : 440,
                        confidence: this.testSignalConfidence
                    }));

                    this._notify({
                        type: 'NOTE_DETECTION',
                        inputStatus: this.status,
                        mode: this.mode,
                        status: notes.length > 0 ? 'DETECTED' : 'NO_INPUT',
                        notes,
                        confidence: this.testSignalConfidence,
                        polyphonyType: notes.length > 1 ? 'POLYPHONIC' : (notes.length === 1 ? 'MONOPHONIC' : 'UNKNOWN'),
                        rms: notes.length > 0 ? 0.2 : 0.0
                    });
                }

                this._animFrameId = _raf(loop);
            };

            this._animFrameId = _raf(loop);
        }

        /**
         * Stop listening and release all audio hardware streams.
         */
        stop() {
            if (this._animFrameId) {
                _caf(this._animFrameId);
                this._animFrameId = null;
            }

            // Stop all microphone tracks immediately
            if (this.mediaStream) {
                try {
                    const tracks = this.mediaStream.getTracks();
                    for (let i = 0; i < tracks.length; i++) {
                        tracks[i].stop();
                    }
                } catch (e) {
                    console.warn('[RealtimeInputService] Error stopping media tracks:', e);
                }
                this.mediaStream = null;
            }

            if (this.sourceNode) {
                try {
                    this.sourceNode.disconnect();
                } catch (e) {}
                this.sourceNode = null;
            }

            if (this.detector) {
                this.detector.reset();
            }

            const prevMode = this.mode;
            this.mode = InputMode.OFF;
            this.status = InputStatus.STOPPED;
            
            if (prevMode !== InputMode.OFF) {
                this._notify({ type: 'STATUS_CHANGE', status: this.status, mode: this.mode });
            }
        }
    }

    // Export module
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = {
            RealtimeInputService,
            InputMode,
            InputStatus
        };
    } else {
        global.RealtimeInputService = new RealtimeInputService();
        global.InputMode = InputMode;
        global.InputStatus = InputStatus;
    }

})(typeof window !== 'undefined' ? window : this);
