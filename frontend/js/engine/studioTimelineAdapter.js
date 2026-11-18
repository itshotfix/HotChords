/**
 * studioTimelineAdapter.js
 *
 * Canonical Musical Timeline Adapter for HotChords Piano Studio.
 * Single source of truth providing synchronized note states, chord states,
 * measure structures, real-time pitch transposition, hand filtering, and
 * offline Standard MIDI File (.mid) export for:
 *   1. 2D Piano Studio (88-key + Falling-Note Waterfall)
 *   2. 3D Piano Studio (WebGL 3D Keys + Articulated Hands + Waterfall)
 *   3. Sheet Music View (Grand Staff Treble/Bass Notation)
 *   4. Learn Mode & Practice Controller
 *   5. Note-Level Piano Audio Playback
 */

(function(global) {
    'use strict';

    const NOTE_NAMES_SHARP = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
    const FINGER_COLORS = {
        1: '#FF4D4F', // Thumb (Red)
        2: '#FAAD14', // Index (Orange)
        3: '#52C41A', // Middle (Green)
        4: '#13C2C2', // Ring (Teal)
        5: '#1677FF'  // Pinky (Blue)
    };

    function midiToNoteName(midi) {
        const m = Math.max(21, Math.min(108, Math.round(midi)));
        const octave = Math.floor(m / 12) - 1;
        const pc = ((m % 12) + 12) % 12;
        return `${NOTE_NAMES_SHARP[pc]}${octave}`;
    }

    function transposeChordName(chordName, semitones) {
        if (!chordName || chordName === 'N' || !semitones) return chordName;
        const shift = ((semitones % 12) + 12) % 12;
        if (shift === 0) return chordName;

        return String(chordName).replace(/([A-G][#b]?)/g, (match) => {
            const flatToSharp = { Db: 'C#', Eb: 'D#', Gb: 'F#', Ab: 'G#', Bb: 'A#' };
            const norm = flatToSharp[match] || match;
            const idx = NOTE_NAMES_SHARP.indexOf(norm);
            if (idx === -1) return match;
            return NOTE_NAMES_SHARP[(idx + shift) % 12];
        });
    }

    class StudioTimelineAdapter {
        constructor() {
            this.timeline = null;
            this.mode = 'simplified'; // 'simplified' (Beginner) | 'original' (Intermediate)
            this.pitchShift = 0;      // -12 .. +12 semitones
            this.handFilter = 'both'; // 'both' | 'left' | 'right'
            this._cachedIntermediateNotes = [];
            this._cachedBeginnerNotes = [];
        }

        loadTimeline(timeline, rawData = null) {
            this.timeline = timeline || null;
            const srcNotes = (timeline && timeline.notes) || (rawData && rawData.notes) || [];
            const srcBegNotes = (timeline && (timeline.beginnerNotes || timeline.beginner_notes)) ||
                (rawData && (rawData.beginner_notes || rawData.beginnerNotes)) || [];

            this._cachedIntermediateNotes = srcNotes.length > 0
                ? this._normalizeNotes(srcNotes)
                : this._synthesizeNotesFromChords((timeline && timeline.originalChords) || [], false);

            this._cachedBeginnerNotes = srcBegNotes.length > 0
                ? this._normalizeNotes(srcBegNotes)
                : this._synthesizeNotesFromChords((timeline && timeline.beginnerChords) || (timeline && timeline.originalChords) || [], true);
        }

        _normalizeNotes(rawList) {
            return (rawList || []).map((n, idx) => {
                const midi = Math.max(21, Math.min(108, Number(n.midi ?? n.pitch ?? 60)));
                const start = Number(n.start ?? n.startTime ?? 0);
                const end = Math.max(start + 0.06, Number(n.end ?? n.endTime ?? (start + 0.4)));
                const hand = String(n.hand || (midi < 60 ? 'left' : 'right')).toLowerCase();
                const finger = Math.max(1, Math.min(5, Number(n.finger || 1)));
                const color = n.color || FINGER_COLORS[finger] || '#FF4D4F';
                return {
                    id: n.id || `note-${idx}-${midi}-${Math.round(start * 1000)}`,
                    midi,
                    note: n.note || midiToNoteName(midi),
                    start,
                    end,
                    duration: Math.max(0.06, end - start),
                    velocity: Math.max(1, Math.min(127, Number(n.velocity || 80))),
                    hand,
                    finger,
                    color,
                    source: String(n.source || 'melody'),
                    chord: n.chord || null
                };
            }).sort((a, b) => a.start - b.start || a.midi - b.midi);
        }

        _synthesizeNotesFromChords(chords, isBeginner) {
            const notes = [];
            const fingeringEngine = global.PianoFingeringEngine;

            (chords || []).forEach((c, cIdx) => {
                const cName = c.chordName || c.chord || 'N';
                if (!cName || cName === 'N') return;
                const start = Number(c.startTime ?? c.time ?? 0);
                const end = Math.max(start + 0.2, Number(c.endTime ?? c.end ?? (start + 2.0)));
                const dur = end - start;

                let voicing = c.voicing;
                if (!voicing && fingeringEngine && typeof fingeringEngine.getChordVoicing === 'function') {
                    voicing = fingeringEngine.getChordVoicing(cName, c.notes || [0, 4, 7]);
                }

                const lh = (voicing && (voicing.leftHand || voicing.left_hand)) || [{ midi: 48, finger: 5, color: FINGER_COLORS[5] }];
                const rh = (voicing && (voicing.rightHand || voicing.right_hand)) || [
                    { midi: 60, finger: 1, color: FINGER_COLORS[1] },
                    { midi: 64, finger: 3, color: FINGER_COLORS[3] },
                    { midi: 67, finger: 5, color: FINGER_COLORS[5] }
                ];

                // Left hand notes
                lh.forEach((vn, i) => {
                    const finger = Number(vn.finger || (i === 0 ? 5 : 1));
                    notes.push({
                        id: `syn-lh-${cIdx}-${i}`,
                        midi: Number(vn.midi || 48),
                        note: midiToNoteName(vn.midi || 48),
                        start,
                        end,
                        duration: dur,
                        velocity: 58,
                        hand: 'left',
                        finger,
                        color: vn.color || FINGER_COLORS[finger] || '#1677FF',
                        source: 'chord',
                        chord: cName
                    });
                });

                if (isBeginner || dur < 0.8) {
                    // Block or two-beat RH pattern
                    rh.forEach((vn, i) => {
                        const finger = Number(vn.finger || (i * 2 + 1));
                        notes.push({
                            id: `syn-rh-${cIdx}-${i}`,
                            midi: Number(vn.midi || 60),
                            note: midiToNoteName(vn.midi || 60),
                            start,
                            end,
                            duration: dur,
                            velocity: i === rh.length - 1 ? 96 : 68,
                            hand: 'right',
                            finger,
                            color: vn.color || FINGER_COLORS[finger] || '#FF4D4F',
                            source: i === rh.length - 1 ? 'melody' : 'accompaniment',
                            chord: cName
                        });
                    });
                } else {
                    // Intermediate: arpeggiated / melodic subdivision across chord duration
                    const subDur = Math.max(0.25, dur / Math.max(2, rh.length));
                    rh.forEach((vn, i) => {
                        const nStart = start + i * subDur;
                        const nEnd = Math.min(end, nStart + subDur * 1.15);
                        const finger = Number(vn.finger || Math.min(5, i * 2 + 1));
                        notes.push({
                            id: `syn-rh-int-${cIdx}-${i}`,
                            midi: Number(vn.midi || 60),
                            note: midiToNoteName(vn.midi || 60),
                            start: nStart,
                            end: nEnd,
                            duration: nEnd - nStart,
                            velocity: i === rh.length - 1 ? 100 : 66,
                            hand: 'right',
                            finger,
                            color: vn.color || FINGER_COLORS[finger] || '#FF4D4F',
                            source: i === rh.length - 1 ? 'melody' : 'accompaniment',
                            chord: cName
                        });
                    });
                }
            });

            return notes.sort((a, b) => a.start - b.start || a.midi - b.midi);
        }

        setMode(mode) {
            this.mode = (mode === 'original' || mode === 'intermediate') ? 'original' : 'simplified';
        }

        setPitchShift(semitones) {
            this.pitchShift = Math.max(-12, Math.min(12, Math.round(Number(semitones) || 0)));
        }

        setHandFilter(filter) {
            const f = String(filter || 'both').toLowerCase();
            this.handFilter = (f === 'left' || f === 'right') ? f : 'both';
        }

        getNotes(overrideMode = null, overrideHand = null) {
            const targetMode = overrideMode || this.mode;
            const targetHand = overrideHand || this.handFilter;
            const baseList = (targetMode === 'original' || targetMode === 'intermediate')
                ? this._cachedIntermediateNotes
                : this._cachedBeginnerNotes;

            const shift = this.pitchShift;

            return baseList
                .filter(n => targetHand === 'both' || n.hand === targetHand)
                .map(n => {
                    if (shift === 0) return n;
                    const shiftedMidi = Math.max(21, Math.min(108, n.midi + shift));
                    return Object.assign({}, n, {
                        midi: shiftedMidi,
                        note: midiToNoteName(shiftedMidi),
                        chord: transposeChordName(n.chord, shift)
                    });
                });
        }

        getChords(overrideMode = null) {
            if (!this.timeline) return [];
            const targetMode = overrideMode || this.mode;
            const rawChords = (targetMode === 'original' || targetMode === 'intermediate')
                ? (this.timeline.originalChords || [])
                : (this.timeline.beginnerChords || this.timeline.originalChords || []);

            const shift = this.pitchShift;
            return rawChords.map(c => {
                const baseName = c.chordName || c.chord || 'N';
                const shiftedName = transposeChordName(baseName, shift);
                const shiftedNotes = Array.isArray(c.notes)
                    ? c.notes.map(pc => ((pc + shift) % 12 + 12) % 12)
                    : [0, 4, 7];
                return Object.assign({}, c, {
                    chordName: shiftedName,
                    chord: shiftedName,
                    notes: shiftedNotes
                });
            });
        }

        /**
         * Returns synchronized note states at `currentTime`:
         * - activeNotes: notes ringing right now
         * - upcomingNotes: notes starting within [currentTime, currentTime + lookAheadSec]
         * - completedNotes: notes ended within [currentTime - lookBehindSec, currentTime]
         */
        getWindowState(currentTime, lookAheadSec = 3.0, lookBehindSec = 1.2) {
            const t = Math.max(0, Number(currentTime) || 0);
            const notes = this.getNotes();
            const activeNotes = [];
            const upcomingNotes = [];
            const completedNotes = [];

            for (let i = 0; i < notes.length; i++) {
                const n = notes[i];
                if (n.start <= t && n.end > t) {
                    const progress = Math.min(1, Math.max(0, (t - n.start) / Math.max(0.05, n.end - n.start)));
                    activeNotes.push(Object.assign({}, n, { state: 'active', progress }));
                } else if (n.start > t && n.start <= t + lookAheadSec) {
                    const timeUntilStrike = n.start - t;
                    upcomingNotes.push(Object.assign({}, n, { state: 'upcoming', timeUntilStrike }));
                } else if (n.end <= t && n.end >= t - lookBehindSec) {
                    completedNotes.push(Object.assign({}, n, { state: 'completed' }));
                }
            }

            return {
                currentTime: t,
                activeNotes,
                upcomingNotes,
                completedNotes
            };
        }

        /**
         * Returns Grand Staff measures derived from the single canonical timeline.
         */
        getMeasures() {
            const notes = this.getNotes(this.mode, 'both');
            const chords = this.getChords(this.mode);
            const tempo = (this.timeline && this.timeline.metadata && this.timeline.metadata.tempo) || 120;
            const timeSig = (this.timeline && this.timeline.metadata && (this.timeline.metadata.time_sig || this.timeline.metadata.timeSig)) || '4/4';
            const beatsPerBar = String(timeSig).startsWith('3') ? 3 : 4;
            const beatSec = 60.0 / Math.max(40, Math.min(220, Number(tempo) || 120));
            const measureDur = beatSec * beatsPerBar;
            const totalDur = Math.max(
                (this.timeline && this.timeline.duration) || 0,
                notes.length > 0 ? notes[notes.length - 1].end : 0,
                measureDur
            );
            const count = Math.max(1, Math.ceil(totalDur / measureDur));
            const measures = [];

            for (let m = 0; m < count; m++) {
                const mStart = m * measureDur;
                const mEnd = (m + 1) * measureDur;
                const trebleNotes = notes.filter(n => n.hand === 'right' && n.start >= mStart - 0.02 && n.start < mEnd - 0.02);
                const bassNotes = notes.filter(n => n.hand === 'left' && n.start >= mStart - 0.02 && n.start < mEnd - 0.02);
                const mChords = chords.filter(c => {
                    const cs = Number(c.startTime ?? c.time ?? 0);
                    const ce = Number(c.endTime ?? c.end ?? 0);
                    return !(ce <= mStart + 0.02 || cs >= mEnd - 0.02);
                });

                measures.push({
                    index: m + 1,
                    startTime: mStart,
                    endTime: mEnd,
                    duration: measureDur,
                    chords: mChords,
                    trebleNotes,
                    bassNotes
                });
            }

            return {
                tempo,
                timeSig,
                beatsPerBar,
                measureDuration: measureDur,
                measures
            };
        }

        /**
         * Builds a Standard MIDI File (Format 1) Uint8Array in the browser for offline MIDI export.
         */
        exportMidiBytes() {
            const notes = this.getNotes();
            const tempo = (this.timeline && this.timeline.metadata && this.timeline.metadata.tempo) || 120;
            const bpm = Math.max(30, Math.min(240, Number(tempo) || 120));
            const ticksPerBeat = 480;
            const usPerBeat = Math.round(60000000 / bpm);

            function encodeVlq(val) {
                let v = Math.max(0, Math.round(val));
                const bytes = [v & 0x7F];
                v >>= 7;
                while (v > 0) {
                    bytes.push((v & 0x7F) | 0x80);
                    v >>= 7;
                }
                bytes.reverse();
                return bytes;
            }

            function secToTick(sec) {
                return Math.round(Math.max(0, sec) * (bpm / 60) * ticksPerBeat);
            }

            function buildTrack(events) {
                events.sort((a, b) => a.tick - b.tick || a.order - b.order);
                const body = [];
                let prev = 0;
                for (const ev of events) {
                    const delta = Math.max(0, ev.tick - prev);
                    body.push(...encodeVlq(delta), ...ev.bytes);
                    prev = ev.tick;
                }
                body.push(0x00, 0xFF, 0x2F, 0x00);
                const len = body.length;
                return [
                    0x4D, 0x54, 0x72, 0x6B,
                    (len >> 24) & 0xFF, (len >> 16) & 0xFF, (len >> 8) & 0xFF, len & 0xFF,
                    ...body
                ];
            }

            const t0 = [{
                tick: 0,
                order: 0,
                bytes: [0xFF, 0x51, 0x03, (usPerBeat >> 16) & 0xFF, (usPerBeat >> 8) & 0xFF, usPerBeat & 0xFF]
            }];

            const rhEvents = [{ tick: 0, order: 0, bytes: [0xC0, 0x00] }];
            const lhEvents = [{ tick: 0, order: 0, bytes: [0xC1, 0x00] }];

            for (const n of notes) {
                const sTick = secToTick(n.start);
                const eTick = Math.max(sTick + 20, secToTick(n.end));
                const m = Math.max(21, Math.min(108, Math.round(n.midi)));
                const v = Math.max(1, Math.min(127, Math.round(n.velocity || 80)));
                if (n.hand === 'left') {
                    lhEvents.push({ tick: sTick, order: 1, bytes: [0x91, m, v] });
                    lhEvents.push({ tick: eTick, order: 0, bytes: [0x81, m, 0] });
                } else {
                    rhEvents.push({ tick: sTick, order: 1, bytes: [0x90, m, v] });
                    rhEvents.push({ tick: eTick, order: 0, bytes: [0x80, m, 0] });
                }
            }

            const header = [
                0x4D, 0x54, 0x68, 0x64,
                0x00, 0x00, 0x00, 0x06,
                0x00, 0x01,
                0x00, 0x03,
                (ticksPerBeat >> 8) & 0xFF, ticksPerBeat & 0xFF
            ];

            return new Uint8Array([
                ...header,
                ...buildTrack(t0),
                ...buildTrack(rhEvents),
                ...buildTrack(lhEvents)
            ]);
        }
    }

    const instance = new StudioTimelineAdapter();
    global.StudioTimelineAdapter = instance;
    global.StudioTimelineAdapterClass = StudioTimelineAdapter;
    global.midiToNoteName = midiToNoteName;
    global.transposeChordName = transposeChordName;

    if (typeof module !== 'undefined' && module.exports) {
        module.exports = { StudioTimelineAdapter, instance, midiToNoteName, transposeChordName };
    }
})(typeof window !== 'undefined' ? window : global);
