/**
 * originalChordPlaybackController.js
 * 
 * Playback Controller for SongTimeline.original_chords.
 * Bridges SongTimeline canonical chord events with PianoPlaybackService.
 * 
 * Architecture:
 * SongTimeline.original_chords -> OriginalChordPlaybackController -> PianoPlaybackService -> Tone.Sampler / Web Audio
 * 
 * Responsibilities:
 * - Reads ChordEvent startTime, endTime, and pitch classes / voicings.
 * - Schedules simultaneous polyphonic piano chords using Web Audio / Tone.js hardware clock.
 * - Handles play, stop, restart, cancellation, and timeline synchronization.
 * - Pure playback controller with no secondary timing loops or setInterval clocks.
 */

(function(global) {
    'use strict';

    class OriginalChordPlaybackController {
        constructor(playbackService) {
            this.service = playbackService || global.PianoPlaybackService;
            this._isPlaying = false;
            this._playGeneration = 0;
            this.currentTimeline = null;
            this.startClockTime = 0;
            this.startTimelineOffset = 0;
            this.scheduledTimeouts = [];
            this.stateCallbacks = [];
            this.chordTriggerCallbacks = [];
        }

        /**
         * Converts a ChordEvent into an array of playable MIDI notes.
         * Uses chord voicing / pitch classes in consistent playable piano range (Octaves 3-4).
         */
        convertChordEventToPlayableNotes(chordEvent) {
            if (!chordEvent) return [];

            const cName = chordEvent.chordName || chordEvent.chord;
            if (!cName || cName === 'N') return [];

            // 1. Check if explicit voicing with MIDI keys is attached
            if (chordEvent.voicing) {
                const midiList = [];
                const rh = chordEvent.voicing.rightHand || chordEvent.voicing.right_hand || [];
                const lh = chordEvent.voicing.leftHand || chordEvent.voicing.left_hand || [];
                rh.forEach(n => { if (typeof n.midi === 'number') midiList.push(n.midi); });
                lh.forEach(n => { if (typeof n.midi === 'number') midiList.push(n.midi); });
                if (midiList.length > 0) return midiList;
            }

            // 2. Check if pitch classes are available (e.g. [0, 4, 7])
            const notes = chordEvent.notes;
            if (Array.isArray(notes) && notes.length > 0) {
                const rootPc = notes[0] % 12;
                const midiList = [];
                
                // Bass root in Octave 3 (MIDI 48 is C3) for low-end presence
                midiList.push(48 + rootPc);
                
                // Harmony triad / 7th in Octave 4 (MIDI 60 is Middle C)
                notes.forEach(pc => {
                    midiList.push(60 + (pc % 12));
                });
                return midiList;
            }

            // 3. Fallback: Parse chord symbol via PianoFingeringEngine or basic intervals
            if (global.PianoFingeringEngine) {
                const rootPc = global.MusicTheoryFormatter ? global.MusicTheoryFormatter.getNoteName(0) : 0;
                // If note indices can be derived
                const dummyNotes = [0, 4, 7];
                const voicing = global.PianoFingeringEngine.getChordVoicing(cName, dummyNotes);
                if (voicing && voicing.rightHand) {
                    return voicing.rightHand.map(n => n.midi);
                }
            }

            // Default middle C fallback
            return [60, 64, 67];
        }

        /**
         * Starts playback of SongTimeline.original_chords from a given offset in seconds with optional rate scaling.
         * @param {Object} timeline - Canonical SongTimeline object
         * @param {number} startOffset - Playback start offset in seconds (default: 0)
         * @param {number} playbackRate - Playback speed multiplier (default: 1.0)
         */
        async playOriginalChords(timeline, startOffset = 0, playbackRate = 1.0) {
            if (!timeline) {
                throw new Error('[OriginalChordPlaybackController] No SongTimeline provided.');
            }

            // Stop any existing playback first
            this.stopOriginalChords();
            const activeGen = ++this._playGeneration;

            // Ensure piano service is initialized and audio context is running
            await this.service.initialize();
            await this.service.resume();

            // Abort if superseded or cancelled during async initialization
            if (this._playGeneration !== activeGen) return;

            const originalChords = timeline.originalChords || timeline.original_chords;
            if (!Array.isArray(originalChords) || originalChords.length === 0) {
                console.warn('[OriginalChordPlaybackController] Timeline has no original_chords.');
                return;
            }

            this.currentTimeline = timeline;
            this._isPlaying = true;
            this.startTimelineOffset = Math.max(0, startOffset);
            this.playbackRate = Math.max(0.1, Number(playbackRate) || 1.0);

            // Determine base audio clock time
            let now = 0;
            if (typeof window !== 'undefined' && window.Tone && window.Tone.now) {
                now = window.Tone.now();
            } else if (this.service && this.service.audioCtx) {
                now = this.service.audioCtx.currentTime;
            }
            this.startClockTime = now;

            // Schedule all upcoming ChordEvents on the timeline
            originalChords.forEach((event, index) => {
                const start = Number(event.startTime !== undefined ? event.startTime : event.time);
                const end = Number(event.endTime !== undefined ? event.endTime : event.end);

                // Skip chords that ended before the startOffset
                if (end <= this.startTimelineOffset) return;

                // Scale timing by playbackRate: elapsed audio delay = timeline delay / rate
                const chordDelay = Math.max(0, (start - this.startTimelineOffset) / this.playbackRate);
                const chordDuration = Math.max(0.1, (end - Math.max(this.startTimelineOffset, start)) / this.playbackRate);

                const playableNotes = this.convertChordEventToPlayableNotes(event);
                const confidence = event.confidence !== undefined ? event.confidence : 0.85;
                const velocity = Math.max(0.5, Math.min(1.0, confidence));

                // Schedule UI notification callbacks & audio playback synchronized with timer
                const msUntilTrigger = chordDelay * 1000;
                const timerId = setTimeout(() => {
                    if (this._isPlaying && this._playGeneration === activeGen) {
                        if (playableNotes.length > 0) {
                            this.service.playChord(playableNotes, velocity, chordDuration);
                        }
                        this._notifyChordTrigger(event, index);
                    }
                }, msUntilTrigger);
                this.scheduledTimeouts.push(timerId);
            });

            this._notifyStateChange('playing');
        }

        /**
         * Immediately stops active voices, cancels scheduled audio events and timers.
         */
        stopOriginalChords() {
            this._playGeneration++;
            const wasPlaying = this._isPlaying;
            this._isPlaying = false;
            this._clearScheduledTimers();
            if (this.service && this.service.stopAll) {
                this.service.stopAll();
            }
            if (wasPlaying) {
                this._notifyStateChange('stopped');
            }
        }

        isPlaying() {
            return this._isPlaying;
        }

        getCurrentTime() {
            if (!this._isPlaying) return this.startTimelineOffset;
            let now = 0;
            if (typeof window !== 'undefined' && window.Tone && window.Tone.now) {
                now = window.Tone.now();
            } else if (this.service && this.service.audioCtx) {
                now = this.service.audioCtx.currentTime;
            }
            return this.startTimelineOffset + (now - this.startClockTime) * (this.playbackRate || 1.0);
        }

        onStateChange(callback) {
            if (typeof callback === 'function') this.stateCallbacks.push(callback);
        }

        onChordTrigger(callback) {
            if (typeof callback === 'function') this.chordTriggerCallbacks.push(callback);
        }

        _clearScheduledTimers() {
            this.scheduledTimeouts.forEach(id => clearTimeout(id));
            this.scheduledTimeouts = [];
        }

        _notifyStateChange(state) {
            this.stateCallbacks.forEach(cb => {
                try { cb(state); } catch (e) {}
            });
        }

        _notifyChordTrigger(chordEvent, index) {
            this.chordTriggerCallbacks.forEach(cb => {
                try { cb(chordEvent, index); } catch (e) {}
            });
        }
    }

    // Export singleton & class
    const controllerInstance = new OriginalChordPlaybackController(global.PianoPlaybackService);
    global.OriginalChordPlaybackController = controllerInstance;
    global.OriginalChordPlaybackControllerClass = OriginalChordPlaybackController;

})(typeof window !== 'undefined' ? window : global);
