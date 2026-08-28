/**
 * beginnerPianoLearningRenderer.js
 * 
 * Production Beginner Piano Learning Renderer for HotChords Phase 6D-1.
 * 
 * Architecture:
 * Pure Visualization Layer consuming:
 * - CurrentChordEngine (authoritative query for active/next chords & progress)
 * - PianoFingeringEngine (authoritative beginner hand voicings & fingerings)
 * - ChordTransitionEngine (authoritative transition difficulty & anchor finger analysis)
 * - PlaybackClock (authoritative monotonic time & playback state)
 * 
 * Invariants:
 * - 100% Driven by PlaybackClock (zero setInterval, setTimeout, or independent clocks).
 * - Zero learning logic or fingering calculations inside the renderer.
 * - Reuses PianoKeyboard (pianoKeyboard.js) for keyboard visualization.
 * - Handles all empty, initial, trailing, and unknown chord states gracefully.
 */

(function(global) {
    'use strict';

    class BeginnerPianoLearningRenderer {
        /**
         * @param {Object} options
         * @param {HTMLElement|string} [options.container] - Target container element or ID
         * @param {Object} [options.clock] - PlaybackClock instance
         * @param {Object} [options.chordEngine] - CurrentChordEngine instance
         * @param {Object} [options.fingeringEngine] - PianoFingeringEngine instance
         * @param {Object} [options.transitionEngine] - ChordTransitionEngine instance
         * @param {Object} [options.keyboard] - Existing PianoKeyboard instance (optional)
         */
        constructor(options = {}) {
            this.clock = options.clock || (global.PlaybackClock || null);
            this.chordEngine = options.chordEngine || (global.CurrentChordEngine ? new global.CurrentChordEngine(this.clock) : null);
            this.fingeringEngine = options.fingeringEngine || (global.PianoFingeringEngine || null);
            this.transitionEngine = options.transitionEngine || (global.ChordTransitionEngine || null);
            
            this.container = null;
            this.keyboard = options.keyboard || null;
            this.showEmbeddedKeyboard = options.showEmbeddedKeyboard !== undefined
                ? Boolean(options.showEmbeddedKeyboard)
                : (this.keyboard === null);

            this._unsubscribeClock = null;
            this._lastStateSnapshot = null;

            if (options.container) {
                this.mount(options.container);
            }
        }

        /**
         * Sets or updates the PlaybackClock instance and re-subscribes.
         * @param {Object} clock
         */
        setClock(clock) {
            if (this._unsubscribeClock) {
                this._unsubscribeClock();
                this._unsubscribeClock = null;
            }
            this.clock = clock;
            if (this.chordEngine && typeof this.chordEngine.setClock === 'function') {
                this.chordEngine.setClock(clock);
            }
            if (this.clock && typeof this.clock.subscribe === 'function') {
                this._unsubscribeClock = this.clock.subscribe(() => this.update());
            }
            this.update();
        }

        /**
         * Loads SongTimeline into the current chord engine.
         * @param {Object} timeline
         */
        loadTimeline(timeline) {
            if (this.chordEngine && typeof this.chordEngine.loadTimeline === 'function') {
                this.chordEngine.loadTimeline(timeline);
            }
            this.update();
        }

        /**
         * Mounts the renderer into a DOM container element.
         * @param {HTMLElement|string} containerOrId
         */
        mount(containerOrId) {
            if (typeof document === 'undefined') return;

            this.container = typeof containerOrId === 'string'
                ? document.getElementById(containerOrId)
                : containerOrId;

            if (!this.container) return;

            this._buildDOM();

            // Connect clock subscription
            if (this.clock && typeof this.clock.subscribe === 'function' && !this._unsubscribeClock) {
                this._unsubscribeClock = this.clock.subscribe(() => this.update());
            }

            this.update();
        }

        /**
         * Unmounts the renderer and clears subscriptions.
         */
        unmount() {
            if (this._unsubscribeClock) {
                this._unsubscribeClock();
                this._unsubscribeClock = null;
            }
            if (this.container) {
                this.container.innerHTML = '';
            }
        }

        /**
         * Builds the UI scaffolding inside the container.
         * @private
         */
        _buildDOM() {
            if (!this.container) return;

            const keyboardHostHTML = this.showEmbeddedKeyboard ? `
                <!-- PIANO KEYBOARD HOST -->
                <div class="bplr-keyboard-host" id="bplr-keyboard-host" aria-label="Interactive Piano Keyboard">
                    <div id="bplr-piano-embed"></div>
                </div>
            ` : '';

            this.container.innerHTML = `
                <div class="bplr-wrapper" role="region" aria-label="Beginner Piano Learning Dashboard">
                    <!-- HERO: ACTIVE & NEXT CHORD HUD -->
                    <div class="bplr-hud-grid">
                        <!-- CURRENT CHORD CARD -->
                        <div class="bplr-card bplr-current-card" aria-live="polite">
                            <div class="bplr-card-header">
                                <span class="bplr-badge bplr-badge-current">CURRENT CHORD</span>
                                <span class="bplr-time-disp" id="bplr-current-time" aria-label="Current Playback Time">0:00</span>
                            </div>
                            <div class="bplr-chord-hero" id="bplr-chord-hero" aria-label="Active Chord">—</div>
                            <div class="bplr-progress-bar-wrap" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" id="bplr-progress-wrap">
                                <div class="bplr-progress-bar-fill" id="bplr-progress-bar"></div>
                            </div>
                            <div class="bplr-notes-summary" id="bplr-current-notes-summary">No active chord</div>
                        </div>

                        <!-- NEXT CHORD & TRANSITION CARD -->
                        <div class="bplr-card bplr-next-card" id="bplr-next-card" aria-live="polite">
                            <div class="bplr-card-header">
                                <span class="bplr-badge bplr-badge-next">NEXT CHORD</span>
                                <span class="bplr-diff-badge" id="bplr-diff-badge">EASY</span>
                            </div>
                            <div class="bplr-next-chord-hero" id="bplr-next-chord-hero" aria-label="Next Chord">—</div>
                            <div class="bplr-transition-advice" id="bplr-transition-advice" aria-label="Transition Guidance">Ready</div>
                        </div>
                    </div>

                    <!-- HAND & FINGER GUIDE STRIP -->
                    <div class="bplr-hand-guides-grid">
                        <!-- LEFT HAND -->
                        <div class="bplr-card bplr-hand-card" aria-label="Left Hand Bass Guides">
                            <div class="bplr-hand-title">
                                <span class="bplr-hand-icon">✋</span> Left Hand (Bass)
                            </div>
                            <div class="bplr-hand-card-content">
                                <div class="bplr-hand-diagram" id="bplr-lh-diagram">
                                    ${global.HandDiagrams ? global.HandDiagrams.getHandMarkup('LH') : ''}
                                </div>
                                <div class="bplr-finger-chips" id="bplr-lh-chips">
                                    <span class="bplr-idle-text">—</span>
                                </div>
                            </div>
                        </div>

                        <!-- RIGHT HAND -->
                        <div class="bplr-card bplr-hand-card" aria-label="Right Hand Harmony Guides">
                            <div class="bplr-hand-title">
                                <span class="bplr-hand-icon">🤚</span> Right Hand (Harmony)
                            </div>
                            <div class="bplr-hand-card-content">
                                <div class="bplr-hand-diagram" id="bplr-rh-diagram">
                                    ${global.HandDiagrams ? global.HandDiagrams.getHandMarkup('RH') : ''}
                                </div>
                                <div class="bplr-finger-chips" id="bplr-rh-chips">
                                    <span class="bplr-idle-text">—</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    ${keyboardHostHTML}
                </div>
            `;

            // Initialize PianoKeyboard inside the embedded host if enabled
            if (this.showEmbeddedKeyboard) {
                const keyboardContainer = document.getElementById('bplr-piano-embed');
                if (keyboardContainer && !this.keyboard && global.PianoKeyboard) {
                    try {
                        this.keyboard = new global.PianoKeyboard('bplr-piano-embed');
                    } catch (e) {
                        console.warn('[BeginnerPianoLearningRenderer] Could not initialize PianoKeyboard:', e);
                    }
                }
            }
        }

        /**
         * Formats seconds to mm:ss.
         * @param {number} s
         * @returns {string}
         */
        static fmtTime(s) {
            if (typeof s !== 'number' || isNaN(s) || s < 0) return '0:00';
            const m = Math.floor(s / 60);
            const sec = Math.floor(s % 60);
            return `${m}:${sec.toString().padStart(2, '0')}`;
        }

        /**
         * Computes the current view model state snapshot from engines.
         * Pure function of engines' states without side effects.
         * @returns {Object} ViewModel snapshot
         */
        getViewModel() {
            let currentTime = 0;
            let clockState = 'STOPPED';

            if (this.clock) {
                currentTime = typeof this.clock.getCurrentTime === 'function'
                    ? this.clock.getCurrentTime()
                    : (typeof this.clock.currentTime === 'number' ? this.clock.currentTime : 0);
                clockState = this.clock.state || 'STOPPED';
            }

            let chordState = {
                currentChord: null,
                nextChord: null,
                progress: 0.0,
                isApproachingNextChord: false,
                timeRemaining: 0
            };

            if (this.chordEngine && typeof this.chordEngine.getState === 'function') {
                chordState = this.chordEngine.getState(currentTime);
            }

            const currentChordEvent = chordState.currentChord;
            const nextChordEvent = chordState.nextChord;
            const progress = chordState.progress || 0.0;
            const isApproaching = chordState.isApproachingNextChord || false;

            // 1. Resolve Current Voicing
            let currentVoicing = null;
            if (this.fingeringEngine && currentChordEvent) {
                currentVoicing = this.fingeringEngine.getChordVoicing(currentChordEvent);
            }

            // 2. Resolve Next Voicing
            let nextVoicing = null;
            if (this.fingeringEngine && nextChordEvent) {
                nextVoicing = this.fingeringEngine.getChordVoicing(nextChordEvent);
            }

            // 3. Resolve Transition Analysis
            let transition = null;
            if (this.transitionEngine && (currentChordEvent || nextChordEvent)) {
                transition = this.transitionEngine.analyzeTransition(
                    currentChordEvent,
                    nextChordEvent,
                    { availableTimeSeconds: chordState.timeRemaining }
                );
            }

            // Formulate transition guidance tip
            let transitionTip = 'Ready';
            let difficulty = transition ? transition.difficulty : 'EASY';

            if (currentChordEvent && nextChordEvent && transition) {
                if (transition.rightHand && transition.rightHand.stationaryNotes.length > 0) {
                    const held = transition.rightHand.stationaryNotes.join(', ');
                    transitionTip = `Keep finger in place on ${held}`;
                } else if (transition.sharedNotes && transition.sharedNotes.length > 0) {
                    transitionTip = `Shared anchor note: ${transition.sharedNotes.join(', ')}`;
                } else if (transition.totalMovement > 0) {
                    const dir = transition.rightHand.movement[0] ? transition.rightHand.movement[0].direction : '';
                    transitionTip = dir ? `Shift hand ${dir.toLowerCase()} by ${transition.maxMovement} semitones` : transition.difficultyReason;
                } else {
                    transitionTip = 'Continue current chord position';
                }
            } else if (!currentChordEvent && nextChordEvent) {
                transitionTip = 'Get ready for first chord';
            } else if (currentChordEvent && !nextChordEvent) {
                transitionTip = 'Final chord passage';
            } else {
                transitionTip = 'Waiting for playback';
            }

            const currentChordName = currentChordEvent
                ? (currentChordEvent.chordName || currentChordEvent.chord || '')
                : null;
            const nextChordName = nextChordEvent
                ? (nextChordEvent.chordName || nextChordEvent.chord || '')
                : null;

            return {
                currentTime,
                clockState,
                currentChord: currentChordEvent,
                nextChord: nextChordEvent,
                currentChordName,
                nextChordName,
                currentVoicing,
                nextVoicing,
                transition,
                transitionTip,
                difficulty,
                progress: Math.max(0, Math.min(1, progress)),
                isApproachingNext: isApproaching,
                timeRemaining: chordState.timeRemaining || 0
            };
        }

        /**
         * Re-evaluates engine state and renders DOM updates.
         */
        update() {
            const vm = this.getViewModel();
            this._lastStateSnapshot = vm;

            // 4. Update PianoKeyboard Highlight
            if (this.keyboard && typeof this.keyboard.applyVoicingDOM === 'function') {
                this.keyboard.voicing = vm.currentVoicing;
                this.keyboard.applyVoicingDOM();
            }

            // If running in node or non-DOM test environment, return snapshot
            if (typeof document === 'undefined' || !this.container) {
                return vm;
            }

            // 1. Current Chord Display
            const heroEl = document.getElementById('bplr-chord-hero');
            const timeEl = document.getElementById('bplr-current-time');
            const progBar = document.getElementById('bplr-progress-bar');
            const notesSummaryEl = document.getElementById('bplr-current-notes-summary');

            if (heroEl) {
                heroEl.textContent = vm.currentChordName || '—';
                heroEl.classList.toggle('bplr-has-chord', Boolean(vm.currentChordName));
            }

            if (timeEl) {
                timeEl.textContent = BeginnerPianoLearningRenderer.fmtTime(vm.currentTime);
            }

            if (progBar) {
                progBar.style.width = `${(vm.progress * 100).toFixed(1)}%`;
            }

            if (notesSummaryEl) {
                if (vm.currentVoicing) {
                    const rhNotes = vm.currentVoicing.rightHand.notes.join(' - ');
                    const lhNotes = vm.currentVoicing.leftHand.notes.join(' - ');
                    notesSummaryEl.textContent = `RH: ${rhNotes} | LH: ${lhNotes}`;
                } else if (vm.currentChordName) {
                    notesSummaryEl.textContent = 'Voicing standard triad';
                } else {
                    notesSummaryEl.textContent = 'No active chord';
                }
            }

            // 2. Next Chord Card & Transition Advice
            const nextHeroEl = document.getElementById('bplr-next-chord-hero');
            const nextCardEl = document.getElementById('bplr-next-card');
            const diffBadge = document.getElementById('bplr-diff-badge');
            const adviceEl = document.getElementById('bplr-transition-advice');

            if (nextHeroEl) {
                nextHeroEl.textContent = vm.nextChordName || '—';
            }

            if (nextCardEl) {
                nextCardEl.classList.toggle('bplr-approaching', vm.isApproachingNext);
            }

            if (diffBadge) {
                diffBadge.textContent = vm.difficulty;
                diffBadge.className = `bplr-diff-badge bplr-diff-${vm.difficulty.toLowerCase()}`;
                diffBadge.style.display = (vm.currentChordName || vm.nextChordName) ? 'inline-block' : 'none';
            }

            if (adviceEl) {
                adviceEl.textContent = vm.transitionTip;
            }

            // 3. Hand & Finger Guide Chips
            const lhContainer = document.getElementById('bplr-lh-chips');
            const rhContainer = document.getElementById('bplr-rh-chips');

            if (lhContainer) {
                if (vm.currentVoicing && vm.currentVoicing.leftHand && vm.currentVoicing.leftHand.length > 0) {
                    lhContainer.innerHTML = vm.currentVoicing.leftHand.map(item => `
                        <div class="bplr-chip" style="border-left: 4px solid ${item.color}">
                            <span class="bplr-chip-finger">Finger ${item.finger}</span>
                            <span class="bplr-chip-note">${item.note}</span>
                        </div>
                    `).join('');
                } else {
                    lhContainer.innerHTML = '<span class="bplr-idle-text">—</span>';
                }
            }

            if (rhContainer) {
                if (vm.currentVoicing && vm.currentVoicing.rightHand && vm.currentVoicing.rightHand.length > 0) {
                    rhContainer.innerHTML = vm.currentVoicing.rightHand.map(item => `
                        <div class="bplr-chip" style="border-left: 4px solid ${item.color}">
                            <span class="bplr-chip-finger">Finger ${item.finger}</span>
                            <span class="bplr-chip-note">${item.note}</span>
                        </div>
                    `).join('');
                } else {
                    rhContainer.innerHTML = '<span class="bplr-idle-text">—</span>';
                }
            }

            // 4. Update PianoKeyboard Highlight
            if (this.keyboard && typeof this.keyboard.applyVoicingDOM === 'function') {
                this.keyboard.voicing = vm.currentVoicing;
                this.keyboard.applyVoicingDOM();
            }

            // 5. Update Hand Diagrams & Animation
            if (global.HandAnimator && typeof global.HandAnimator.animateChord === 'function') {
                global.HandAnimator.animateChord(vm.currentVoicing);
            }
            this._updateHandDiagrams(vm.currentVoicing);

            return vm;
        }

        /**
         * Direct DOM update for SVG hand diagrams (ensures hands update seamlessly with or without GSAP).
         * @param {Object} voicing
         * @private
         */
        _updateHandDiagrams(voicing) {
            if (typeof document === 'undefined') return;

            // Left Hand fingers 1..5
            const lhActive = (voicing && voicing.leftHand) ? voicing.leftHand : [];
            for (let f = 1; f <= 5; f++) {
                const groupEl = document.getElementById(`lh-finger-${f}`);
                const fingerEl = document.querySelector(`#lh-finger-${f} path`);
                const dotEl = document.getElementById(`lh-finger-dot-${f}`);
                const numEl = document.getElementById(`lh-finger-num-${f}`);
                const active = lhActive.find(item => item.finger === f);

                if (groupEl) {
                    groupEl.style.transform = active ? 'translateY(6px)' : 'translateY(0)';
                }
                if (fingerEl) {
                    fingerEl.style.fill = active ? (active.color || '#0071E3') : '#FFFFFF';
                    fingerEl.style.stroke = active ? (active.color || '#0071E3') : '#D2D2D7';
                }
                if (dotEl) {
                    dotEl.style.fill = active ? (active.color || '#0071E3') : '#E5E5EA';
                    dotEl.style.stroke = active ? '#FFFFFF' : '#D2D2D7';
                }
                if (numEl) {
                    numEl.style.opacity = active ? '1' : '0.25';
                    numEl.style.fill = active ? '#FFFFFF' : '#1D1D1F';
                }
            }

            // Right Hand fingers 1..5
            const rhActive = (voicing && voicing.rightHand) ? voicing.rightHand : [];
            for (let f = 1; f <= 5; f++) {
                const groupEl = document.getElementById(`rh-finger-${f}`);
                const fingerEl = document.querySelector(`#rh-finger-${f} path`);
                const dotEl = document.getElementById(`rh-finger-dot-${f}`);
                const numEl = document.getElementById(`rh-finger-num-${f}`);
                const active = rhActive.find(item => item.finger === f);

                if (groupEl) {
                    groupEl.style.transform = active ? 'translateY(6px)' : 'translateY(0)';
                }
                if (fingerEl) {
                    fingerEl.style.fill = active ? (active.color || '#0071E3') : '#FFFFFF';
                    fingerEl.style.stroke = active ? (active.color || '#0071E3') : '#D2D2D7';
                }
                if (dotEl) {
                    dotEl.style.fill = active ? (active.color || '#0071E3') : '#E5E5EA';
                    dotEl.style.stroke = active ? '#FFFFFF' : '#D2D2D7';
                }
                if (numEl) {
                    numEl.style.opacity = active ? '1' : '0.25';
                    numEl.style.fill = active ? '#FFFFFF' : '#1D1D1F';
                }
            }
        }

        /**
         * Returns the latest snapshot.
         * @returns {Object}
         */
        getState() {
            return this._lastStateSnapshot || this.getViewModel();
        }
    }

    // Export for Browser and Node environments
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = { BeginnerPianoLearningRenderer };
    }
    if (typeof window !== 'undefined') {
        window.BeginnerPianoLearningRenderer = BeginnerPianoLearningRenderer;
    }
})(typeof globalThis !== 'undefined' ? globalThis : (typeof window !== 'undefined' ? window : this));
