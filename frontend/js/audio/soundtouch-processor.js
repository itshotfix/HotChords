/**
 * soundtouch-processor.js
 *
 * Real-time Pitch-Preserving AudioWorkletProcessor for HotChords.
 * Uses dual-pointer Hann-windowed overlap-add (OLA) delay-line pitch shifting
 * so AudioBufferSourceNode can run at playbackRate = R (staying sample-locked
 * to PlaybackClock) while restoring original pitch via pitchFactor = 1 / R.
 */

class SoundTouchPitchProcessor extends AudioWorkletProcessor {
    static get parameterDescriptors() {
        return [
            {
                name: 'pitchFactor',
                defaultValue: 1.0,
                minValue: 0.5,
                maxValue: 2.5,
                automationRate: 'k-rate',
            },
        ];
    }

    constructor() {
        super();
        this.bufferSize = 4096;
        this.windowSize = 2048;
        this.channels = [];
        this.writeIndex = 0;
        this.phase = 0.0;
    }

    _ensureChannels(numChannels) {
        while (this.channels.length < numChannels) {
            this.channels.push(new Float32Array(this.bufferSize));
        }
    }

    process(inputs, outputs, parameters) {
        const input = inputs[0];
        const output = outputs[0];
        if (!input || input.length === 0 || !output || output.length === 0) {
            return true;
        }

        const pitchFactor = parameters.pitchFactor ? parameters.pitchFactor[0] : 1.0;
        const numChannels = Math.min(input.length, output.length);
        const blockLen = output[0].length;

        // Unity bypass when pitchFactor is ~1.0 (zero latency & zero artifacts at 1.0x)
        if (Math.abs(pitchFactor - 1.0) < 0.003) {
            for (let ch = 0; ch < numChannels; ch++) {
                output[ch].set(input[ch]);
            }
            return true;
        }

        this._ensureChannels(numChannels);
        const N = this.bufferSize;
        const W = this.windowSize;
        const halfW = W * 0.5;
        // Phase advance rate proportional to (1 - pitchFactor) / W
        const phaseStep = (1.0 - pitchFactor) / W;

        for (let i = 0; i < blockLen; i++) {
            const wi = this.writeIndex;
            const p0 = this.phase;
            const p1 = (p0 + 0.5) % 1.0;

            const d0 = p0 * W;
            const d1 = p1 * W;

            // Triangular / Hann-like crossfade weights
            const w0 = 0.5 - 0.5 * Math.cos(2.0 * Math.PI * p0);
            const w1 = 1.0 - w0;

            for (let ch = 0; ch < numChannels; ch++) {
                const ring = this.channels[ch];
                ring[wi] = input[ch][i];

                const r0 = (wi - d0 + N) % N;
                const r1 = (wi - d1 + N) % N;
                const i0 = Math.floor(r0);
                const f0 = r0 - i0;
                const s0 = ring[i0] * (1.0 - f0) + ring[(i0 + 1) % N] * f0;

                const i1 = Math.floor(r1);
                const f1 = r1 - i1;
                const s1 = ring[i1] * (1.0 - f1) + ring[(i1 + 1) % N] * f1;

                output[ch][i] = s0 * w0 + s1 * w1;
            }

            this.writeIndex = (wi + 1) % N;
            this.phase = (this.phase + phaseStep + 1.0) % 1.0;
        }

        return true;
    }
}

registerProcessor('soundtouch-processor', SoundTouchPitchProcessor);
