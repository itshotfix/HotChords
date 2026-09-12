/**
 * workspaceChordTimeline.js
 *
 * High-Performance Deterministic 3-Chord Physical Sliding Timeline for HotChords.
 * Architectural Standards: HotChords UI/UX & Animation Engineering Skills.
 *
 * Sequence Geometry:
 *   PREVIOUS (-1D)  <───  CURRENT HERO (0)  ───>  NEXT (+1D)
 *
 * Key Architecture:
 * - Structural labels (`PREVIOUS`, `CURRENT CHORD`, `NEXT`) remain permanently fixed in space.
 * - Operates on 3 permanent DOM elements: #chord-prev, #chord-current, #chord-next.
 * - Current Chord is the central pedagogical hero element (scale 1.15, opacity 1.0, glow, active progress track).
 * - Previous & Next are visually secondary (scale 0.65, opacity 0.40-0.45, muted).
 * - Chord transitions trigger a continuous 4-lane hardware-accelerated WAAPI physical slide:
 *     1. Old Prev exits left (-1D -> -2D, scale 0.65 -> 0.38, opacity 0.40 -> 0)
 *     2. Current glides left into Prev (0 -> -1D, scale 1.15 -> 0.65, opacity 1.0 -> 0.40)
 *     3. Next glides left into Current (+1D -> 0, scale 0.65 -> 1.15, opacity 0.45 -> 1.0, hero glow)
 *     4. Incoming new Next enters from right (+2D -> +1D, scale 0.38 -> 0.65, opacity 0 -> 0.45)
 * - Seeking or rapid skipping immediately cancels active animations and snaps to clean resting state.
 * - Pause freezes visual state; Resume seamlessly continues without state jumps.
 * - Respects prefers-reduced-motion.
 */

(function(global) {
    'use strict';

    const ANIM_DURATION_MS = 260;
    const ANIM_EASING = 'cubic-bezier(0.22, 1, 0.36, 1)';
    const NO_CHORD_TEXT = '—';

    // Module State
    let _chords = [];
    let _currentIdx = -1;
    let _isAnimating = false;
    let _reducedMotion = false;
    let _activeAnimations = [];
    let _transientNodes = [];
    let _resizeObserver = null;

    // DOM Elements
    let _prevEl = null;
    let _curEl = null;
    let _nextEl = null;
    let _trackEl = null;
    let _viewportEl = null;
    let _fillEl = null;
    let _onSeek = null;

    // Helpers
    function getStart(c) {
        if (!c) return 0;
        return typeof c.startTime === 'number' ? c.startTime : (c.time || 0);
    }

    function getEnd(c) {
        if (!c) return 0;
        return typeof c.endTime === 'number' ? c.endTime : (c.end || getStart(c) + 2.0);
    }

    function getName(c) {
        if (!c) return NO_CHORD_TEXT;
        return c.chordName || c.chord || NO_CHORD_TEXT;
    }

    function getVoicing(c) {
        if (!c || !c.notes || !c.notes.length) return '';
        const PITCH = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];
        return c.notes.map(n => typeof n === 'number' ? PITCH[n % 12] : n).join(' · ');
    }

    /**
     * Resolves chord index based on canonical PlaybackClock time.
     * Matches CurrentChordEngine boundary conditions.
     */
    function _resolveIndex(currentTime) {
        if (!_chords || !_chords.length) return -1;

        const firstStart = getStart(_chords[0]);
        if (currentTime < firstStart) return -1;

        const lastEnd = getEnd(_chords[_chords.length - 1]);
        if (currentTime >= lastEnd) return _chords.length;

        for (let i = 0; i < _chords.length; i++) {
            const start = getStart(_chords[i]);
            const nextStart = (i < _chords.length - 1) ? getStart(_chords[i + 1]) : getEnd(_chords[i]);
            if (currentTime >= start && currentTime < nextStart) {
                return i;
            }
        }
        return -1;
    }

    /**
     * Calculates the exact horizontal lane displacement distance (D).
     * Perfectly aligns with the 25% / 50% / 25% column layout of the fixed structural labels.
     */
    function _getLaneDistance() {
        const width = _viewportEl ? _viewportEl.clientWidth : 700;
        // The center of Previous is at -37.5% of width, Current at 0, Next at +37.5%
        return Math.max(140, Math.min(360, Math.round(width * 0.375)));
    }

    /**
     * Cancels all active in-flight WAAPI animations and purges transient DOM nodes.
     */
    function _cancelAnimations() {
        for (let i = 0; i < _activeAnimations.length; i++) {
            try { _activeAnimations[i].cancel(); } catch (e) {}
        }
        _activeAnimations = [];

        for (let i = 0; i < _transientNodes.length; i++) {
            try { _transientNodes[i].remove(); } catch (e) {}
        }
        _transientNodes = [];
        _isAnimating = false;
    }

    /**
     * Updates card DOM data (text content, voicing, class flags).
     */
    function _setCardData(el, chord, role) {
        if (!el) return;

        const nameEl = el.querySelector('[data-chord-name]');
        const voiceEl = el.querySelector('[data-chord-voicing]');

        if (nameEl) nameEl.textContent = getName(chord);

        if (voiceEl) {
            const vText = (role === 'current') ? getVoicing(chord) : '';
            voiceEl.textContent = vText;
            voiceEl.style.display = vText ? '' : 'none';
        }

        el.classList.toggle('chord-card--prev', role === 'prev');
        el.classList.toggle('chord-card--current', role === 'current');
        el.classList.toggle('chord-card--next', role === 'next');
    }

    /**
     * Sets GPU-accelerated resting transform and opacity for a given role.
     */
    function _applyRestingTransform(el, role, D) {
        if (!el) return;
        if (role === 'prev') {
            el.style.transform = `translate3d(calc(-50% - ${D}px), -50%, 0) scale(0.65)`;
            el.style.opacity = '0.40';
        } else if (role === 'current') {
            el.style.transform = 'translate3d(-50%, -50%, 0) scale(1.15)';
            el.style.opacity = '1.0';
        } else if (role === 'next') {
            el.style.transform = `translate3d(calc(-50% + ${D}px), -50%, 0) scale(0.65)`;
            el.style.opacity = '0.45';
        }
    }

    /**
     * Instant resting rebuild without transition animations (used on seek, init, mode-change).
     */
    function _instantRebuild(idx) {
        _cancelAnimations();

        if (!_prevEl || !_curEl || !_nextEl) return;

        const D = _getLaneDistance();
        let prevChord = null;
        let curChord = null;
        let nextChord = null;

        if (idx < 0) {
            prevChord = null;
            curChord = null;
            nextChord = _chords.length > 0 ? _chords[0] : null;
        } else if (idx >= _chords.length) {
            prevChord = _chords.length > 0 ? _chords[_chords.length - 1] : null;
            curChord = null;
            nextChord = null;
        } else {
            prevChord = idx > 0 ? _chords[idx - 1] : null;
            curChord = _chords[idx];
            nextChord = idx < _chords.length - 1 ? _chords[idx + 1] : null;
        }

        _setCardData(_prevEl, prevChord, 'prev');
        _setCardData(_curEl, curChord, 'current');
        _setCardData(_nextEl, nextChord, 'next');

        _applyRestingTransform(_prevEl, 'prev', D);
        _applyRestingTransform(_curEl, 'current', D);
        _applyRestingTransform(_nextEl, 'next', D);

        if (_fillEl) {
            if (curChord && typeof PlaybackClock !== 'undefined') {
                _updateProgress(PlaybackClock.currentTime, idx);
            } else {
                _fillEl.style.width = '0%';
            }
        }
    }

    /**
     * Coordinated 4-lane WAAPI physical slide for sequential +1 chord transition.
     */
    function _animateForward(newIdx) {
        _cancelAnimations();

        if (_reducedMotion || !_trackEl || !_prevEl || !_curEl || !_nextEl) {
            _instantRebuild(newIdx);
            return;
        }

        _isAnimating = true;
        const D = _getLaneDistance();

        // 1. Create temporary incoming card at +2D lane (entering from right)
        const incomingNextChord = newIdx < _chords.length - 1 ? _chords[newIdx + 1] : null;

        const incoming = document.createElement('div');
        incoming.className = 'chord-card chord-card--next';
        incoming.setAttribute('data-transient', 'true');
        incoming.innerHTML = `
            <div class="chord-card-name" data-chord-name>${getName(incomingNextChord)}</div>
        `;
        incoming.style.position = 'absolute';
        incoming.style.top = '50%';
        incoming.style.left = '50%';
        incoming.style.transform = `translate3d(calc(-50% + ${2 * D}px), -50%, 0) scale(0.38)`;
        incoming.style.opacity = '0';

        _trackEl.appendChild(incoming);
        _transientNodes.push(incoming);

        // Hide voicing text during physical translation to prevent font reflow pop
        const curVoiceEl = _curEl.querySelector('[data-chord-voicing]');
        if (curVoiceEl) curVoiceEl.style.display = 'none';

        const animOptions = { duration: ANIM_DURATION_MS, easing: ANIM_EASING, fill: 'none' };

        const anims = [
            // 1. Old Prev exits left (-1D -> -2D)
            _prevEl.animate([
                { transform: `translate3d(calc(-50% - ${D}px), -50%, 0) scale(0.65)`, opacity: 0.40 },
                { transform: `translate3d(calc(-50% - ${2 * D}px), -50%, 0) scale(0.38)`, opacity: 0 }
            ], animOptions),

            // 2. Current moves to prev (0 -> -1D)
            _curEl.animate([
                { transform: `translate3d(-50%, -50%, 0) scale(1.15)`, opacity: 1.0 },
                { transform: `translate3d(calc(-50% - ${D}px), -50%, 0) scale(0.65)`, opacity: 0.40 }
            ], animOptions),

            // 3. Next moves to current (+1D -> 0)
            _nextEl.animate([
                { transform: `translate3d(calc(-50% + ${D}px), -50%, 0) scale(0.65)`, opacity: 0.45 },
                { transform: `translate3d(-50%, -50%, 0) scale(1.15)`, opacity: 1.0 }
            ], animOptions),

            // 4. Incoming moves to next (+2D -> +1D)
            incoming.animate([
                { transform: `translate3d(calc(-50% + ${2 * D}px), -50%, 0) scale(0.38)`, opacity: 0 },
                { transform: `translate3d(calc(-50% + ${D}px), -50%, 0) scale(0.65)`, opacity: 0.45 }
            ], animOptions)
        ];

        _activeAnimations = anims;

        anims[0].onfinish = () => {
            _instantRebuild(newIdx);
            _isAnimating = false;
        };

        anims[0].oncancel = () => {
            _isAnimating = false;
        };
    }

    /**
     * Updates the duration progress indicator inside the Current Chord card.
     */
    function _updateProgress(currentTime, idx) {
        if (!_fillEl || idx < 0 || idx >= _chords.length || !_chords[idx]) {
            if (_fillEl) _fillEl.style.width = '0%';
            return;
        }

        const chord = _chords[idx];
        const start = getStart(chord);
        const end = getEnd(chord);
        const dur = Math.max(0.05, end - start);
        const pct = Math.max(0, Math.min(100, ((currentTime - start) / dur) * 100));
        _fillEl.style.width = `${pct.toFixed(1)}%`;
    }

    const WorkspaceChordTimeline = {
        /**
         * Mounts DOM elements and binds listeners.
         */
        init(opts = {}) {
            _prevEl     = opts.prevEl     || document.getElementById('chord-prev');
            _curEl      = opts.curEl      || document.getElementById('chord-current');
            _nextEl     = opts.nextEl     || document.getElementById('chord-next');
            _trackEl    = opts.trackEl    || document.getElementById('chord-track');
            _viewportEl = opts.viewport   || document.getElementById('chord-viewport');
            _fillEl     = opts.fillEl     || document.getElementById('chord-progress-fill');
            _onSeek     = typeof opts.onSeek === 'function' ? opts.onSeek : null;

            try {
                _reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
            } catch (e) {
                _reducedMotion = false;
            }

            if (_prevEl) {
                _prevEl.style.cursor = 'pointer';
                _prevEl.onclick = () => {
                    if (_currentIdx > 0 && _onSeek) {
                        _onSeek(getStart(_chords[_currentIdx - 1]));
                    }
                };
            }

            if (_nextEl) {
                _nextEl.style.cursor = 'pointer';
                _nextEl.onclick = () => {
                    if (_currentIdx >= 0 && _currentIdx < _chords.length - 1 && _onSeek) {
                        _onSeek(getStart(_chords[_currentIdx + 1]));
                    } else if (_currentIdx < 0 && _chords.length > 0 && _onSeek) {
                        _onSeek(getStart(_chords[0]));
                    }
                };
            }

            // Clean up existing ResizeObserver
            if (_resizeObserver) {
                _resizeObserver.disconnect();
                _resizeObserver = null;
            }

            // Responsive layout observer
            if (typeof ResizeObserver !== 'undefined' && _viewportEl) {
                _resizeObserver = new ResizeObserver(() => {
                    if (!_isAnimating) {
                        const D = _getLaneDistance();
                        _applyRestingTransform(_prevEl, 'prev', D);
                        _applyRestingTransform(_curEl, 'current', D);
                        _applyRestingTransform(_nextEl, 'next', D);
                    }
                });
                _resizeObserver.observe(_viewportEl);
            } else if (typeof window !== 'undefined' && typeof window.addEventListener === 'function') {
                window.addEventListener('resize', () => {
                    if (!_isAnimating) {
                        const D = _getLaneDistance();
                        _applyRestingTransform(_prevEl, 'prev', D);
                        _applyRestingTransform(_curEl, 'current', D);
                        _applyRestingTransform(_nextEl, 'next', D);
                    }
                });
            }

            _instantRebuild(-1);
        },

        /**
         * Loads chord dataset for active mode (simplified or original).
         */
        loadChords(chords) {
            _chords = Array.isArray(chords) ? chords : [];
            _currentIdx = -1;
            _cancelAnimations();

            const clockTime = (typeof PlaybackClock !== 'undefined') ? PlaybackClock.currentTime : 0;
            const idx = _resolveIndex(clockTime);
            _currentIdx = idx;
            _instantRebuild(idx);
        },

        /**
         * Frame-driven update anchored to PlaybackClock.
         * Triggers animation strictly on chord index boundaries.
         */
        update(currentTime) {
            if (!_chords.length) return;

            const newIdx = _resolveIndex(currentTime);

            if (newIdx !== _currentIdx) {
                const isForwardStep = (newIdx === _currentIdx + 1) && newIdx >= 0;

                if (isForwardStep) {
                    _currentIdx = newIdx;
                    _animateForward(newIdx);
                } else {
                    _currentIdx = newIdx;
                    _instantRebuild(newIdx);
                }
            } else {
                // Same chord interval: update only progress bar with zero DOM transform churn
                _updateProgress(currentTime, _currentIdx);
            }
        },

        /**
         * Resets timeline to neutral empty state.
         */
        reset() {
            _chords = [];
            _currentIdx = -1;
            _cancelAnimations();
            _instantRebuild(-1);
        },

        get currentIndex() { return _currentIdx; },
        get chords() { return _chords; }
    };

    global.WorkspaceChordTimeline = WorkspaceChordTimeline;

    if (typeof module !== 'undefined' && module.exports) {
        module.exports = { WorkspaceChordTimeline };
    }

})(typeof window !== 'undefined' ? window : (typeof global !== 'undefined' ? global : this));
