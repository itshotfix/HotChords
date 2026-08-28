/**
 * workspaceChordTimeline.js
 *
 * Single Workspace Chord Timeline for HotChords (Phase 2).
 * High-performance 3-chord physical sliding carousel (Previous < Current Hero > Next).
 *
 * Architecture:
 * - Operates on 3 permanent DOM elements: #chord-prev, #chord-current, #chord-next.
 * - State machine updates ONLY when currentIndex actually changes.
 * - During a chord interval, only the progress indicator width updates (0 DOM/transform churn).
 * - Sequential +1 chord transition triggers a coordinated 4-lane WAAPI physical slide:
 *     1. Previous moves & fades out left (-1D -> -2D)
 *     2. Current moves left into Previous (0 -> -1D, scale 1.08 -> 0.55, opacity 1.0 -> 0.45)
 *     3. Next moves left into Current (+1D -> 0, scale 0.55 -> 1.08, opacity 0.45 -> 1.0, hero glow)
 *     4. Incoming new chord enters from right (+2D -> +1D, scale 0.35 -> 0.55, opacity 0 -> 0.45)
 * - Rapid seeking or multi-chord skips immediately cancel in-flight animations and snap to resting state.
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

    function _resolveIndex(currentTime) {
        if (!_chords.length) return -1;
        let found = -1;
        for (let i = 0; i < _chords.length; i++) {
            if (currentTime >= getStart(_chords[i])) {
                found = i;
            } else {
                break;
            }
        }
        return found;
    }

    function _getLaneDistance() {
        const width = _viewportEl ? _viewportEl.clientWidth : 700;
        return Math.max(160, Math.min(360, Math.round(width * 0.30)));
    }


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

    function _applyRestingTransform(el, role, D) {
        if (!el) return;
        if (role === 'prev') {
            el.style.transform = `translate3d(calc(-50% - ${D}px), -50%, 0) scale(0.68)`;
            el.style.opacity = '0.45';
        } else if (role === 'current') {
            el.style.transform = 'translate3d(-50%, -50%, 0) scale(1.18)';
            el.style.opacity = '1.0';
        } else if (role === 'next') {
            el.style.transform = `translate3d(calc(-50% + ${D}px), -50%, 0) scale(0.68)`;
            el.style.opacity = '0.45';
        }
    }

    function _instantRebuild(idx) {
        _cancelAnimations();

        if (!_prevEl || !_curEl || !_nextEl) return;

        const D = _getLaneDistance();
        const prevChord = idx > 0 ? _chords[idx - 1] : null;
        const curChord  = idx >= 0 ? _chords[idx] : null;
        const nextChord = (idx >= 0 && idx < _chords.length - 1) ? _chords[idx + 1] : (_chords.length && idx < 0 ? _chords[0] : null);

        _setCardData(_prevEl, prevChord, 'prev');
        _setCardData(_curEl,  curChord,  'current');
        _setCardData(_nextEl, nextChord, 'next');

        _applyRestingTransform(_prevEl, 'prev', D);
        _applyRestingTransform(_curEl, 'current', D);
        _applyRestingTransform(_nextEl, 'next', D);

        if (_fillEl) _fillEl.style.width = '0%';
    }

    function _animateForward(newIdx) {
        _cancelAnimations();

        if (_reducedMotion || !_trackEl || !_prevEl || !_curEl || !_nextEl) {
            _instantRebuild(newIdx);
            return;
        }

        _isAnimating = true;
        const D = _getLaneDistance();

        // Incoming chord entering from right at lane +2D
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
        incoming.style.transform = `translate3d(calc(-50% + ${2 * D}px), -50%, 0) scale(0.40)`;
        incoming.style.opacity = '0';

        _trackEl.appendChild(incoming);
        _transientNodes.push(incoming);

        // Hide voicing on current during movement to prevent text layout pop
        const curVoiceEl = _curEl.querySelector('[data-chord-voicing]');
        if (curVoiceEl) curVoiceEl.style.display = 'none';

        const animOptions = { duration: ANIM_DURATION_MS, easing: ANIM_EASING, fill: 'none' };

        const anims = [
            // 1. Prev exits left (-1D -> -2D)
            _prevEl.animate([
                { transform: `translate3d(calc(-50% - ${D}px), -50%, 0) scale(0.68)`, opacity: 0.45 },
                { transform: `translate3d(calc(-50% - ${2 * D}px), -50%, 0) scale(0.40)`, opacity: 0 }
            ], animOptions),

            // 2. Current moves to prev (0 -> -1D)
            _curEl.animate([
                { transform: `translate3d(-50%, -50%, 0) scale(1.18)`, opacity: 1.0 },
                { transform: `translate3d(calc(-50% - ${D}px), -50%, 0) scale(0.68)`, opacity: 0.45 }
            ], animOptions),

            // 3. Next moves to current (+1D -> 0)
            _nextEl.animate([
                { transform: `translate3d(calc(-50% + ${D}px), -50%, 0) scale(0.68)`, opacity: 0.45 },
                { transform: `translate3d(-50%, -50%, 0) scale(1.18)`, opacity: 1.0 }
            ], animOptions),

            // 4. Incoming moves to next (+2D -> +1D)
            incoming.animate([
                { transform: `translate3d(calc(-50% + ${2 * D}px), -50%, 0) scale(0.40)`, opacity: 0 },
                { transform: `translate3d(calc(-50% + ${D}px), -50%, 0) scale(0.68)`, opacity: 0.45 }
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

    function _updateProgress(currentTime, idx) {
        if (!_fillEl || idx < 0 || !_chords[idx]) {
            if (_fillEl) _fillEl.style.width = '0%';
            return;
        }

        const chord = _chords[idx];
        const start = getStart(chord);
        const end   = getEnd(chord);
        const dur   = Math.max(0.05, end - start);
        const pct   = Math.max(0, Math.min(100, ((currentTime - start) / dur) * 100));
        _fillEl.style.width = `${pct.toFixed(1)}%`;
    }

    const WorkspaceChordTimeline = {
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
                    }
                };
            }

            // Window resize handler to reposition cards
            if (typeof window !== 'undefined' && typeof window.addEventListener === 'function') {
                window.addEventListener('resize', () => {
                    if (!_isAnimating && _currentIdx >= 0) {
                        const D = _getLaneDistance();
                        _applyRestingTransform(_prevEl, 'prev', D);
                        _applyRestingTransform(_curEl, 'current', D);
                        _applyRestingTransform(_nextEl, 'next', D);
                    }
                });
            }

            _instantRebuild(-1);
        },

        loadChords(chords) {
            _chords = Array.isArray(chords) ? chords : [];
            _currentIdx = -1;
            _cancelAnimations();

            const clockTime = (typeof PlaybackClock !== 'undefined') ? PlaybackClock.currentTime : 0;
            const idx = _resolveIndex(clockTime);
            _currentIdx = idx;
            _instantRebuild(idx);
        },

        update(currentTime) {
            if (!_chords.length) return;

            const newIdx = _resolveIndex(currentTime);

            if (newIdx !== _currentIdx) {
                const isForwardStep = (newIdx === _currentIdx + 1) && newIdx >= 0;

                if (isForwardStep) {
                    _animateForward(newIdx);
                    _currentIdx = newIdx;
                } else {
                    _currentIdx = newIdx;
                    _instantRebuild(newIdx);
                }
            } else {
                // Same chord: ONLY update progress bar, zero DOM transform churn
                _updateProgress(currentTime, _currentIdx);
            }
        },

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
