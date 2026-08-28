/**
 * dynamicChordReel.js — Phase 9A.1: 3-Lane Physical Chord Timeline
 *
 * Architecture:
 * - 3 Stable Visual Lanes:
 *     LEFT (-1: Previous) | CENTER (0: Current) | RIGHT (+1: Next)
 * - Physical chord elements are positioned absolutely relative to center (left:50%, top:50%).
 * - Movement geometry is completely independent of chord text width.
 * - During natural transition (N -> N+1):
 *     Old Prev  (N-1) : X = -D -> X = -2D (fades out & exits left)
 *     Old Cur   (N)   : X = 0  -> X = -D  (slides left, shrinks to 0.68, loses glow)
 *     Old Next  (N+1) : X = +D -> X = 0   (slides center, scales to 1.0, gains glow)
 *     New Next  (N+2) : X = +2D-> X = +D  (enters from right at scale 0.68)
 * - NO chord text mutation occurs inside moving elements until animation commits.
 * - WAAPI (element.animate) handles all transitions (300ms, cubic-bezier(0.22, 1, 0.36, 1)).
 * - Seeking instantly cancels all WAAPI animations and rebuilds resting state without animation.
 * - PlaybackClock is the authoritative timing source.
 */

(function(global) {
    'use strict';

    const ANIM_DURATION = 300; // ms
    const ANIM_EASING   = 'cubic-bezier(0.22, 1, 0.36, 1)';
    const SCALE_SIDE    = 0.68;
    const OPACITY_PREV  = 0.40;
    const OPACITY_NEXT  = 0.55;
    const PROGRESS_THROTTLE_MS = 60;

    function getChordName(c) {
        if (!c) return '\u2014';
        return c.chordName || c.chord || '\u2014';
    }

    function getStartTime(c) {
        if (!c) return 0;
        return typeof c.startTime === 'number' ? c.startTime
             : typeof c.time     === 'number' ? c.time : 0;
    }

    function getEndTime(c) {
        if (!c) return 0;
        return typeof c.endTime === 'number' ? c.endTime
             : typeof c.end     === 'number' ? c.end : 0;
    }

    function prefersReducedMotion() {
        try {
            return typeof window !== 'undefined' &&
                   window.matchMedia &&
                   window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        } catch(e) { return false; }
    }

    function pitchClassToName(pc) {
        return ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'][pc % 12] || 'C';
    }

    function fmtTime(s) {
        const m = Math.floor(s / 60), sec = Math.floor(s % 60);
        return `${m}:${sec.toString().padStart(2,'0')}`;
    }

    let _instanceCount = 0;

    class DynamicChordReel {
        constructor(options = {}) {
            this.container = typeof options.container === 'string'
                ? (typeof document !== 'undefined' ? document.getElementById(options.container) : null)
                : options.container;

            this.onSeek          = options.onSeek || null;
            this.showHands       = Boolean(options.showHands);
            this.fingeringEngine = options.fingeringEngine || (typeof global !== 'undefined' ? global.PianoFingeringEngine : null) || null;

            this.chords = [];

            // Logical state
            this._logical = {
                previousIndex: -1,
                currentIndex:  -1,
                nextIndex:     -1
            };

            this._lastResolvedIndex = -999;
            this._isAnimating = false;
            this._isPaused = false;
            this._activeAnimations = [];
            this._lastProgressUpdate = 0;
            this._instanceId = ++_instanceCount;

            // Visual lane DOM elements
            this._elements = {
                prev: null,
                cur:  null,
                next: null
            };

            this._viewport = null;
            this._track = null;

            this._render();
        }

        get _state() {
            return {
                currentIndex: this._lastResolvedIndex >= 0 ? this._lastResolvedIndex : this._logical.currentIndex,
                isAnimating:  this._isAnimating,
                isPaused:     this._isPaused
            };
        }

        // ──────────────────────────────────────────────────────────────────────
        // PUBLIC API
        // ──────────────────────────────────────────────────────────────────────

        loadChords(chords) {
            this._cancelAllAnimations();
            this.chords = Array.isArray(chords) ? chords : [];
            this._logical = { previousIndex: -1, currentIndex: -1, nextIndex: -1 };
            this._lastResolvedIndex = -999;
            this._isAnimating = false;
            this._isPaused = false;
            this._instantRebuild(-1);
        }

        setChordSource(chords) { return this.loadChords(chords); }

        update(currentTime) {
            if (!this.container || !this.chords.length) return;
            if (this._isPaused) return;

            const newIdx = this._resolveIndex(currentTime);

            if (!this._isAnimating) {
                this._updateProgress(currentTime, newIdx);
            }

            if (newIdx === this._lastResolvedIndex) return;

            this._onChordChange(this._lastResolvedIndex, newIdx, false);
        }

        seekTo(currentTime) {
            if (!this.container) return;
            const newIdx = this.chords.length ? this._resolveIndex(currentTime) : -1;
            this._updateProgress(currentTime, newIdx);
            if (newIdx === this._lastResolvedIndex) return;
            this._onChordChange(this._lastResolvedIndex, newIdx, true);
        }

        pause()  { this._isPaused = true; }
        resume() { this._isPaused = false; }

        destroy() {
            this._cancelAllAnimations();
            if (this.container) this.container.innerHTML = '';
            this._elements = { prev: null, cur: null, next: null };
            this.chords = [];
        }

        // ──────────────────────────────────────────────────────────────────────
        // INDEX RESOLUTION
        // ──────────────────────────────────────────────────────────────────────

        _resolveIndex(t) {
            const chords = this.chords;
            if (!chords.length) return -1;
            for (let i = 0; i < chords.length; i++) {
                const s = getStartTime(chords[i]);
                const e = getEndTime(chords[i]);
                if (t >= s && t < e) return i;
            }
            if (t >= getStartTime(chords[chords.length - 1])) return chords.length - 1;
            return -1;
        }

        // ──────────────────────────────────────────────────────────────────────
        // STATE DISPATCH
        // ──────────────────────────────────────────────────────────────────────

        _onChordChange(oldIdx, newIdx, isSeeking) {
            this._lastResolvedIndex = newIdx;

            const isNaturalForwardStep = !isSeeking && (newIdx === oldIdx + 1);

            if (isNaturalForwardStep && !prefersReducedMotion() && this._canAnimate()) {
                this._animateTransition(oldIdx, newIdx);
            } else {
                this._cancelAllAnimations();
                this._instantRebuild(newIdx);
            }

            if (this.showHands) {
                const cur = newIdx >= 0 ? this.chords[newIdx] : null;
                this._updateHandsVoicing(cur ? getChordName(cur) : null, cur ? (cur.notes || []) : []);
            }
        }

        // ──────────────────────────────────────────────────────────────────────
        // GEOMETRY & LANE DISTANCE
        // ──────────────────────────────────────────────────────────────────────

        /**
         * Calculates stable horizontal distance (D) between center and side lanes.
         * Independent of chord text width.
         */
        _getLaneDistance() {
            if (!this._viewport) return 180;
            const w = this._viewport.offsetWidth || (typeof window !== 'undefined' ? window.innerWidth : 800);
            if (w <= 480) {
                return Math.max(85, Math.min(130, w * 0.28));
            } else if (w <= 768) {
                return Math.max(120, Math.min(170, w * 0.25));
            }
            return Math.max(160, Math.min(220, w * 0.22));
        }

        // ──────────────────────────────────────────────────────────────────────
        // INSTANT REBUILD (Seeks, Initial Loads, Mode Switches)
        // ──────────────────────────────────────────────────────────────────────

        _instantRebuild(currentIdx) {
            this._isAnimating = false;
            const chords = this.chords;

            const prevIdx = currentIdx > 0 ? currentIdx - 1 : -1;
            const nextIdx = (currentIdx >= 0 && currentIdx < chords.length - 1) ? currentIdx + 1 : -1;

            this._logical = {
                previousIndex: prevIdx,
                currentIndex:  currentIdx,
                nextIndex:     nextIdx
            };

            const prevChord = prevIdx >= 0 ? chords[prevIdx] : null;
            const curChord  = currentIdx >= 0 ? chords[currentIdx] : null;
            const nextChord = nextIdx >= 0 ? chords[nextIdx] : null;

            const D = this._getLaneDistance();

            // Render static elements at resting lane coordinates
            this._setCardData(this._elements.prev, prevChord, 'prev');
            this._applyCardRestingTransform(this._elements.prev, -D, SCALE_SIDE, OPACITY_PREV, false);

            this._setCardData(this._elements.cur, curChord, 'current');
            this._applyCardRestingTransform(this._elements.cur, 0, 1.0, 1.0, true);

            this._setCardData(this._elements.next, nextChord, 'next');
            this._applyCardRestingTransform(this._elements.next, D, SCALE_SIDE, OPACITY_NEXT, false);
        }

        // ──────────────────────────────────────────────────────────────────────
        // PHYSICAL 3-LANE WAAPI TRANSITION
        // ──────────────────────────────────────────────────────────────────────

        _animateTransition(oldIdx, newIdx) {
            if (this._isAnimating) {
                this._cancelAllAnimations();
                this._instantRebuild(newIdx);
                return;
            }

            const chords = this.chords;
            const D = this._getLaneDistance();

            const oldPrevChord = (oldIdx > 0) ? chords[oldIdx - 1] : null;
            const oldCurChord  = (oldIdx >= 0) ? chords[oldIdx] : null;
            const oldNextChord = chords[newIdx]; // was next, now becoming current
            const newNextChord = (newIdx < chords.length - 1) ? chords[newIdx + 1] : null;

            this._isAnimating = true;

            // Visual elements participating in motion
            const elemOldPrev = this._elements.prev;
            const elemOldCur  = this._elements.cur;
            const elemOldNext = this._elements.next;

            // Create incoming Next element at right off-screen (X = +2D)
            const elemNewNext = this._createCardElement(newNextChord, 'next');
            this._applyCardRestingTransform(elemNewNext, 2 * D, SCALE_SIDE, 0, false);
            if (this._track) this._track.appendChild(elemNewNext);

            const dur  = ANIM_DURATION;
            const ease = ANIM_EASING;
            const anims = [];

            // 1. Old Prev: X = -D -> X = -2D, scale 0.68 -> 0.50, opacity 0.40 -> 0
            if (elemOldPrev && typeof elemOldPrev.animate === 'function') {
                const a = elemOldPrev.animate([
                    { transform: `translate(-50%, -50%) translateX(${-D}px) scale(${SCALE_SIDE})`, opacity: OPACITY_PREV },
                    { transform: `translate(-50%, -50%) translateX(${-2 * D}px) scale(${SCALE_SIDE * 0.75})`, opacity: 0 }
                ], { duration: dur, easing: ease, fill: 'forwards' });
                anims.push({ anim: a, elem: elemOldPrev, role: 'exit', toRemove: true });
            }

            // 2. Old Cur (Chord N): X = 0 -> X = -D, scale 1.0 -> 0.68, opacity 1.0 -> 0.40
            // Text remains Chord N during movement!
            if (elemOldCur && typeof elemOldCur.animate === 'function') {
                const a = elemOldCur.animate([
                    { transform: 'translate(-50%, -50%) translateX(0px) scale(1.0)', opacity: 1.0, filter: 'drop-shadow(0 0 20px rgba(88,86,214,0.5))' },
                    { transform: `translate(-50%, -50%) translateX(${-D}px) scale(${SCALE_SIDE})`, opacity: OPACITY_PREV, filter: 'none' }
                ], { duration: dur, easing: ease, fill: 'forwards' });
                anims.push({ anim: a, elem: elemOldCur, role: 'to_prev', toRemove: false });
            }

            // 3. Old Next (Chord N+1): X = +D -> X = 0, scale 0.68 -> 1.0, opacity 0.55 -> 1.0
            // Text remains Chord N+1 during movement!
            if (elemOldNext && typeof elemOldNext.animate === 'function') {
                const a = elemOldNext.animate([
                    { transform: `translate(-50%, -50%) translateX(${D}px) scale(${SCALE_SIDE})`, opacity: OPACITY_NEXT, filter: 'none' },
                    { transform: 'translate(-50%, -50%) translateX(0px) scale(1.0)', opacity: 1.0, filter: 'drop-shadow(0 0 20px rgba(88,86,214,0.5))' }
                ], { duration: dur, easing: ease, fill: 'forwards' });
                anims.push({ anim: a, elem: elemOldNext, role: 'to_cur', toRemove: false });
            }

            // 4. New Next (Chord N+2): X = +2D -> X = +D, scale 0.68, opacity 0 -> 0.55
            if (elemNewNext && typeof elemNewNext.animate === 'function') {
                const a = elemNewNext.animate([
                    { transform: `translate(-50%, -50%) translateX(${2 * D}px) scale(${SCALE_SIDE})`, opacity: 0 },
                    { transform: `translate(-50%, -50%) translateX(${D}px) scale(${SCALE_SIDE})`, opacity: OPACITY_NEXT }
                ], { duration: dur, easing: ease, fill: 'forwards' });
                anims.push({ anim: a, elem: elemNewNext, role: 'to_next', toRemove: false });
            }

            this._activeAnimations = anims;

            // Completion Handler
            const mainAnim = anims.find(a => a.role === 'to_cur');
            if (mainAnim && mainAnim.anim) {
                const captured = anims;
                mainAnim.anim.onfinish = () => {
                    if (this._activeAnimations === captured) {
                        this._commitTransition(newIdx, elemOldCur, elemOldNext, elemNewNext, captured);
                    }
                };
                mainAnim.anim.oncancel = () => {
                    if (elemNewNext && elemNewNext.parentNode) elemNewNext.parentNode.removeChild(elemNewNext);
                };
            }
        }

        /**
         * Commits logical state and reassigns visual element pointers after WAAPI finishes.
         */
        _commitTransition(newIdx, newPrevElem, newCurElem, newNextElem, anims) {
            // Cancel WAAPI fill to return control to standard styles
            anims.forEach(a => {
                try { a.anim.cancel(); } catch(e) {}
                if (a.toRemove && a.elem && a.elem.parentNode) {
                    a.elem.parentNode.removeChild(a.elem);
                }
            });

            this._activeAnimations = [];
            this._isAnimating = false;

            // Reassign visual element pointers
            this._elements.prev = newPrevElem;
            this._elements.cur  = newCurElem;
            this._elements.next = newNextElem;

            // Re-render resting state to ensure 100% stable classes and IDs
            this._instantRebuild(newIdx);
        }

        _cancelAllAnimations() {
            const anims = this._activeAnimations;
            this._activeAnimations = [];
            anims.forEach(a => {
                try { a.anim.cancel(); } catch(e) {}
                if (a.toRemove && a.elem && a.elem.parentNode) {
                    a.elem.parentNode.removeChild(a.elem);
                }
            });
            if (this._track && typeof this._track.querySelectorAll === 'function') {
                const transients = this._track.querySelectorAll('[data-transient]');
                transients.forEach(el => { try { el.parentNode.removeChild(el); } catch(e) {} });
            }
            this._isAnimating = false;
        }

        // ──────────────────────────────────────────────────────────────────────
        // DOM HELPERS
        // ──────────────────────────────────────────────────────────────────────

        _canAnimate() {
            return typeof document !== 'undefined' &&
                   this._elements.cur &&
                   typeof this._elements.cur.animate === 'function';
        }

        _applyCardRestingTransform(el, xPx, scale, opacity, isHero) {
            if (!el || !el.style) return;
            el.style.transform = `translate(-50%, -50%) translateX(${xPx}px) scale(${scale})`;
            el.style.opacity   = String(opacity);
            if (isHero) {
                el.style.filter = 'drop-shadow(0 0 20px rgba(88,86,214,0.5))';
            } else {
                el.style.filter = 'none';
            }
        }

        _setCardData(el, chord, role) {
            if (!el) return;
            const container = this.container;
            const nameEl = (typeof el.querySelector === 'function' ? (el.querySelector('[data-chord-name]') || el.querySelector('.crt-chord-name')) : null)
                || (container && typeof container.querySelector === 'function' ? (role === 'current' ? container.querySelector('#reel-current-name') : (role === 'prev' ? container.querySelector('#reel-prev-name') : container.querySelector('#reel-next-name'))) : null);

            const voiceEl = (typeof el.querySelector === 'function' ? (el.querySelector('[data-chord-voicing]') || el.querySelector('.crt-chord-voicing')) : null)
                || (container && typeof container.querySelector === 'function' ? container.querySelector('#reel-current-voicing') : null);

            const progressEl = (typeof el.querySelector === 'function' ? (el.querySelector('[data-progress-fill]') || el.querySelector('.crt-progress-fill')) : null)
                || (container && typeof container.querySelector === 'function' ? container.querySelector('#reel-progress-fill') : null);

            if (nameEl) nameEl.textContent = getChordName(chord);

            if (el.classList && typeof el.classList.toggle === 'function') {
                el.classList.toggle('crt-card--current', role === 'current');
                el.classList.toggle('crt-card--prev',    role === 'prev');
                el.classList.toggle('crt-card--next',    role === 'next');
                el.classList.toggle('crt-item--current', role === 'current');
                el.classList.toggle('crt-item--prev',    role === 'prev');
                el.classList.toggle('crt-item--next',    role === 'next');
            }

            if (voiceEl) {
                if (role === 'current' && chord && chord.notes && chord.notes.length) {
                    const noteNames = chord.notes.map(n => typeof n === 'number' ? pitchClassToName(n) : n);
                    voiceEl.textContent = noteNames.join(' \u00b7 ');
                    voiceEl.style = voiceEl.style || {};
                    voiceEl.style.display = '';
                } else {
                    voiceEl.textContent = '';
                    voiceEl.style = voiceEl.style || {};
                    voiceEl.style.display = 'none';
                }
            }
            if (progressEl && role === 'current') {
                progressEl.style = progressEl.style || {};
                progressEl.style.width = '0%';
            }
        }

        _createCardElement(chord, role) {
            if (typeof document === 'undefined') return null;
            const el = document.createElement('div');
            el.className = `crt-card crt-card--${role} crt-item crt-item--${role} reel-slot reel-slot-${role}`;
            el.setAttribute('data-transient', '1');
            el.innerHTML = this._cardInnerHTML(role);
            this._setCardData(el, chord, role);
            return el;
        }

        _cardInnerHTML(role) {
            const label = role === 'current' ? 'Now' : role === 'prev' ? 'Previous' : 'Next';
            return [
                `<div class="crt-card-label" aria-hidden="true">${label}</div>`,
                '<div class="crt-chord-name reel-slot-chord-name" data-chord-name>\u2014</div>',
                '<div class="crt-chord-voicing reel-voicing-sub" data-chord-voicing style="display:none"></div>',
                '<div class="crt-progress-track reel-progress-pill-track" aria-hidden="true">',
                '<div class="crt-progress-fill reel-progress-pill-fill" data-progress-fill></div>',
                '</div>'
            ].join('');
        }

        // ──────────────────────────────────────────────────────────────────────
        // PROGRESS BAR
        // ──────────────────────────────────────────────────────────────────────

        _updateProgress(currentTime, currentIdx) {
            const now = typeof performance !== 'undefined' ? performance.now() : Date.now();
            if (now - this._lastProgressUpdate < PROGRESS_THROTTLE_MS) return;
            this._lastProgressUpdate = now;

            const chord  = currentIdx >= 0 ? this.chords[currentIdx] : null;
            const fillEl = this._elements.cur ? this._elements.cur.querySelector('[data-progress-fill]') : null;
            if (!fillEl || !chord) return;

            const start = getStartTime(chord);
            const end   = getEndTime(chord);
            const dur   = Math.max(0.1, end - start);
            const pct   = Math.max(0, Math.min(100, ((currentTime - start) / dur) * 100));
            fillEl.style.width = `${pct.toFixed(1)}%`;
        }

        // ──────────────────────────────────────────────────────────────────────
        // INITIAL RENDER
        // ──────────────────────────────────────────────────────────────────────

        _render() {
            if (!this.container) return;

            const lhMarkup = this.showHands ? `
                <div class="crt-hand-col crt-hand-left reel-hand-col" id="reel-hand-left" aria-label="Left Hand Bass Guidance">
                    <span class="crt-hand-title reel-hand-title">Left Hand (Bass)</span>
                    <div class="crt-hand-visual reel-hand-visual-wrap"><div class="crt-hand-svg reel-hand-svg-box" id="reel-lh-svg">${(typeof global !== 'undefined' && global.HandDiagrams && typeof global.HandDiagrams.getHandMarkup === 'function') ? global.HandDiagrams.getHandMarkup('LH') : ''}</div></div>
                    <div class="crt-finger-chips reel-finger-chips" id="reel-lh-chips"><span class="crt-chip-idle reel-chip-idle">\u2014</span></div>
                </div>` : '';

            const rhMarkup = this.showHands ? `
                <div class="crt-hand-col crt-hand-right reel-hand-col" id="reel-hand-right" aria-label="Right Hand Harmony Guidance">
                    <span class="crt-hand-title reel-hand-title">Right Hand (Harmony)</span>
                    <div class="crt-hand-visual reel-hand-visual-wrap"><div class="crt-hand-svg reel-hand-svg-box" id="reel-rh-svg">${(typeof global !== 'undefined' && global.HandDiagrams && typeof global.HandDiagrams.getHandMarkup === 'function') ? global.HandDiagrams.getHandMarkup('RH') : ''}</div></div>
                    <div class="crt-finger-chips reel-finger-chips" id="reel-rh-chips"><span class="crt-chip-idle reel-chip-idle">\u2014</span></div>
                </div>` : '';

            const trackId = `crt-track-${this._instanceId}`;

            this.container.innerHTML = `
<div class="shared-chord-timeline crt-shell ${this.showHands ? 'has-hands-layout crt-shell--with-hands' : ''}" role="region" aria-label="3-Chord Timeline">
    ${lhMarkup}
    <div class="crt-center reel-conveyor-center">
        <div class="crt-viewport" id="crt-viewport-${this._instanceId}">
            <div class="crt-track reel-chords-row" id="${trackId}">
                <div class="crt-card crt-card--prev crt-item crt-item--prev reel-slot reel-slot-prev" id="reel-slot-prev">
                    <div class="crt-card-label" aria-hidden="true">Previous</div>
                    <div class="crt-chord-name reel-slot-chord-name" id="reel-prev-name" data-chord-name>\u2014</div>
                    <div class="crt-chord-voicing" data-chord-voicing style="display:none"></div>
                    <div class="crt-progress-track" aria-hidden="true"><div class="crt-progress-fill" data-progress-fill></div></div>
                </div>
                <div class="crt-card crt-card--current crt-item crt-item--current reel-slot reel-slot-current" id="reel-slot-current" aria-live="polite" aria-atomic="true">
                    <div class="crt-card-label" aria-hidden="true">Now</div>
                    <div class="crt-chord-name reel-slot-chord-hero" id="reel-current-name" data-chord-name>\u2014</div>
                    <div class="crt-chord-voicing reel-voicing-sub" id="reel-current-voicing" data-chord-voicing style="display:none"></div>
                    <div class="crt-progress-track reel-progress-pill-track" aria-hidden="true"><div class="crt-progress-fill reel-progress-pill-fill" id="reel-progress-fill" data-progress-fill></div></div>
                </div>
                <div class="crt-card crt-card--next crt-item crt-item--next reel-slot reel-slot-next" id="reel-slot-next">
                    <div class="crt-card-label" aria-hidden="true">Next</div>
                    <div class="crt-chord-name reel-slot-chord-name" id="reel-next-name" data-chord-name>\u2014</div>
                    <div class="crt-chord-voicing" data-chord-voicing style="display:none"></div>
                    <div class="crt-progress-track" aria-hidden="true"><div class="crt-progress-fill" data-progress-fill></div></div>
                </div>
            </div>
        </div>
    </div>
    ${rhMarkup}
</div>`;

            const c = this.container;
            this._viewport = (c.querySelector && (c.querySelector(`#crt-viewport-${this._instanceId}`) || c.querySelector('.crt-viewport'))) || null;
            this._track    = (c.querySelector && (c.querySelector(`#${trackId}`) || c.querySelector('#reel-chords-row') || c.querySelector('.crt-track'))) || null;
            this._elements.prev = (c.querySelector && (c.querySelector('#reel-slot-prev') || c.querySelector('.crt-card--prev'))) || null;
            this._elements.cur  = (c.querySelector && (c.querySelector('#reel-slot-current') || c.querySelector('.crt-card--current'))) || null;
            this._elements.next = (c.querySelector && (c.querySelector('#reel-slot-next') || c.querySelector('.crt-card--next'))) || null;

            // Click-to-seek
            if (this._elements.prev) {
                this._elements.prev.onclick = () => {
                    if (this._logical.currentIndex > 0 && this.onSeek) {
                        this.onSeek(getStartTime(this.chords[this._logical.currentIndex - 1]));
                    }
                };
            }
            if (this._elements.next) {
                this._elements.next.onclick = () => {
                    const idx = this._logical.currentIndex;
                    if (idx >= 0 && idx < this.chords.length - 1 && this.onSeek) {
                        this.onSeek(getStartTime(this.chords[idx + 1]));
                    }
                };
            }

            this._instantRebuild(-1);
        }

        // ── Hands Integration ───────────────────────────────────────────────

        _updateHandsVoicing(chordName, notes) {
            if (!this.showHands || !this.container) return;
            const engine = this.fingeringEngine || (typeof global !== 'undefined' ? global.PianoFingeringEngine : null);
            const voicing = (chordName && engine && typeof engine.getChordVoicing === 'function')
                ? engine.getChordVoicing(chordName, notes) : null;

            const lhChips = this.container.querySelector('#reel-lh-chips');
            if (lhChips) {
                lhChips.innerHTML = (voicing && voicing.leftHand && voicing.leftHand.length)
                    ? voicing.leftHand.map(item => `<div class="crt-finger-chip" style="border-left:4px solid ${item.color||'#5856D6'}"><span class="crt-chip-fnum">Finger ${item.finger}</span><span class="crt-chip-note">${item.note}</span></div>`).join('')
                    : '<span class="crt-chip-idle">\u2014</span>';
            }
            const rhChips = this.container.querySelector('#reel-rh-chips');
            if (rhChips) {
                rhChips.innerHTML = (voicing && voicing.rightHand && voicing.rightHand.length)
                    ? voicing.rightHand.map(item => `<div class="crt-finger-chip" style="border-left:4px solid ${item.color||'#5856D6'}"><span class="crt-chip-fnum">Finger ${item.finger}</span><span class="crt-chip-note">${item.note}</span></div>`).join('')
                    : '<span class="crt-chip-idle">\u2014</span>';
            }
            this._animateHandFingers(voicing);
        }

        _animateHandFingers(voicing) {
            if (typeof document === 'undefined' || !this.container) return;
            const lhActive = (voicing && voicing.leftHand)  ? voicing.leftHand  : [];
            const rhActive = (voicing && voicing.rightHand) ? voicing.rightHand : [];
            ['lh','rh'].forEach(hand => {
                const active = hand === 'lh' ? lhActive : rhActive;
                for (let f = 1; f <= 5; f++) {
                    const item     = active.find(i => i.finger === f);
                    const groupEl  = this.container.querySelector(`#${hand}-finger-${f}`);
                    const fingerEl = this.container.querySelector(`#${hand}-finger-${f} path`);
                    const dotEl    = this.container.querySelector(`#${hand}-finger-dot-${f}`);
                    const numEl    = this.container.querySelector(`#${hand}-finger-num-${f}`);
                    if (groupEl)  groupEl.style.transform  = item ? 'translateY(6px)' : 'translateY(0)';
                    if (fingerEl) { fingerEl.style.fill = item ? (item.color||'#5856D6') : '#FFFFFF'; fingerEl.style.stroke = item ? (item.color||'#5856D6') : '#D2D2D7'; }
                    if (dotEl)    { dotEl.style.fill   = item ? (item.color||'#5856D6') : '#E5E5EA'; dotEl.style.stroke = item ? '#FFFFFF' : '#D2D2D7'; }
                    if (numEl)    { numEl.style.opacity = item ? '1' : '0.25'; numEl.style.fill = item ? '#FFFFFF' : '#1D1D1F'; }
                }
            });
        }

        // ── Static helpers ──────────────────────────────────────────────────

        static pitchClassToName(pc) { return pitchClassToName(pc); }
        static fmtTime(s) { return fmtTime(s); }
    }

    if (typeof module !== 'undefined' && module.exports) {
        module.exports = { DynamicChordReel };
    }
    if (typeof window !== 'undefined') {
        window.DynamicChordReel = DynamicChordReel;
    }

})(typeof globalThis !== 'undefined' ? globalThis : (typeof window !== 'undefined' ? window : this));
