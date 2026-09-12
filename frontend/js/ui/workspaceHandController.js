/**
 * workspaceHandController.js
 *
 * Workspace Hand & Finger Guidance Controller for HotChords.
 * Architectural Standards: HotChords UI/UX & Animation Engineering Skills (Phase 3).
 *
 * Capabilities:
 * - Coordinates Left Hand (Bass foundation) and Right Hand (Harmony triad) in real time.
 * - Natural physical downward finger press (6px keybed depression) and release.
 * - Repeated Finger Strike Feedback: consecutive chords using the same finger trigger a distinct
 *   micro-release and re-strike physical pulse.
 * - Synchronized with PlaybackClock, PianoFingeringEngine, and PianoKeyboard.
 * - Zero setInterval/setTimeout independent timers.
 * - Immediate seek cancellation & clean resting state.
 * - Respects prefers-reduced-motion.
 */

(function(global) {
    'use strict';

    // Standardized 5-color pedagogical palette
    const FINGER_COLORS = Object.freeze({
        1: '#FF4D4F', // Thumb (Red)
        2: '#FAAD14', // Index (Orange/Yellow)
        3: '#52C41A', // Middle (Green)
        4: '#13C2C2', // Ring (Cyan)
        5: '#1677FF'  // Pinky (Blue)
    });

    // DOM references
    let _lhSvgEl   = null;
    let _rhSvgEl   = null;
    let _lhChipsEl = null;
    let _rhChipsEl = null;

    // State Tracking
    let _lastChordKey = null;
    let _previousActive = {
        lh: new Map(), // fingerNum -> { note, color }
        rh: new Map()
    };
    let _activeAnims = new Map(); // elementId -> Animation
    let _reducedMotion = false;

    function _findInSvg(svgEl, selector) {
        if (!svgEl) return null;
        return svgEl.querySelector(selector);
    }

    /**
     * Cancels any active WAAPI animation on an element.
     */
    function _cancelElementAnim(animKey) {
        if (_activeAnims.has(animKey)) {
            try {
                _activeAnims.get(animKey).cancel();
            } catch (e) {}
            _activeAnims.delete(animKey);
        }
    }

    /**
     * Executes finger press / release / re-strike animation.
     */
    function _animateFinger(prefix, fingerNum, isActive, color, isRepeated) {
        const rootSvg  = prefix === 'lh' ? _lhSvgEl : _rhSvgEl;
        if (!rootSvg) return;

        const groupEl  = _findInSvg(rootSvg, `#${prefix}-finger-${fingerNum}`);
        const pathEl   = groupEl ? groupEl.querySelector('path') : null;
        const dotEl    = _findInSvg(rootSvg, `#${prefix}-finger-dot-${fingerNum}`);
        const numEl    = _findInSvg(rootSvg, `#${prefix}-finger-num-${fingerNum}`);

        if (!groupEl) return;

        const animKey = `${prefix}-f-${fingerNum}`;
        const activeColor = color || FINGER_COLORS[fingerNum] || '#0071E3';

        if (isActive) {
            // Apply active visual styling
            if (pathEl) {
                pathEl.style.transition = 'stroke 0.15s ease, fill 0.15s ease';
                pathEl.style.fill   = 'rgba(0, 113, 227, 0.07)';
                pathEl.style.stroke = activeColor;
                pathEl.style.strokeWidth = '2.5';
            }

            if (dotEl) {
                dotEl.style.transition = 'fill 0.15s ease, stroke 0.15s ease, filter 0.15s ease';
                dotEl.style.fill   = activeColor;
                dotEl.style.stroke = '#FFFFFF';
                dotEl.style.strokeWidth = '2';
                dotEl.style.filter = `drop-shadow(0 2px 6px ${activeColor}88)`;
            }

            if (numEl) {
                numEl.style.transition = 'fill 0.15s ease, opacity 0.15s ease';
                numEl.style.opacity = '1';
                numEl.style.fill    = '#FFFFFF';
            }

            if (_reducedMotion) {
                groupEl.style.transform = 'translate3d(0, 6px, 0)';
                return;
            }

            if (isRepeated) {
                // REPEATED FINGER STRIKE: Micro-release and rapid re-strike
                _cancelElementAnim(animKey);
                const anim = groupEl.animate([
                    { transform: 'translate3d(0, 6px, 0)' },
                    { transform: 'translate3d(0, 1px, 0)' },
                    { transform: 'translate3d(0, 7px, 0)' },
                    { transform: 'translate3d(0, 6px, 0)' }
                ], {
                    duration: 140,
                    easing: 'cubic-bezier(0.22, 1, 0.36, 1)'
                });

                _activeAnims.set(animKey, anim);
                anim.onfinish = () => {
                    groupEl.style.transform = 'translate3d(0, 6px, 0)';
                    _activeAnims.delete(animKey);
                };
            } else {
                // FRESH INITIAL PRESS: Smooth descent into keybed
                _cancelElementAnim(animKey);
                const anim = groupEl.animate([
                    { transform: groupEl.style.transform || 'translate3d(0, 0, 0)' },
                    { transform: 'translate3d(0, 6px, 0)' }
                ], {
                    duration: 130,
                    easing: 'cubic-bezier(0.22, 1, 0.36, 1)',
                    fill: 'forwards'
                });

                _activeAnims.set(animKey, anim);
                anim.onfinish = () => {
                    groupEl.style.transform = 'translate3d(0, 6px, 0)';
                    _activeAnims.delete(animKey);
                };
            }

        } else {
            // RELEASE: Smooth return to resting state
            _cancelElementAnim(animKey);

            if (pathEl) {
                pathEl.style.transition = 'stroke 0.18s ease, fill 0.18s ease';
                pathEl.style.fill   = '#FFFFFF';
                pathEl.style.stroke = '#D2D2D7';
                pathEl.style.strokeWidth = '1.5';
            }

            if (dotEl) {
                dotEl.style.transition = 'fill 0.18s ease, stroke 0.18s ease, filter 0.18s ease';
                dotEl.style.fill   = '#E5E5EA';
                dotEl.style.stroke = '#D2D2D7';
                dotEl.style.strokeWidth = '1.5';
                dotEl.style.filter = 'none';
            }

            if (numEl) {
                numEl.style.transition = 'fill 0.18s ease, opacity 0.18s ease';
                numEl.style.opacity = '0.35';
                numEl.style.fill    = '#1D1D1F';
            }

            if (_reducedMotion) {
                groupEl.style.transform = 'translate3d(0, 0, 0)';
                return;
            }

            const anim = groupEl.animate([
                { transform: groupEl.style.transform || 'translate3d(0, 6px, 0)' },
                { transform: 'translate3d(0, 0, 0)' }
            ], {
                duration: 160,
                easing: 'ease-out',
                fill: 'forwards'
            });

            _activeAnims.set(animKey, anim);
            anim.onfinish = () => {
                groupEl.style.transform = 'translate3d(0, 0, 0)';
                _activeAnims.delete(animKey);
            };
        }
    }

    /**
     * Updates hand fingers with repeat detection.
     */
    function _updateHand(prefix, activeFingers, isNewChord) {
        const currentMap = new Map();
        const list = Array.isArray(activeFingers) ? activeFingers : [];

        list.forEach(item => {
            if (item && item.finger >= 1 && item.finger <= 5) {
                currentMap.set(item.finger, {
                    note: item.note || '',
                    color: item.color || FINGER_COLORS[item.finger]
                });
            }
        });

        const prevMap = _previousActive[prefix];

        for (let f = 1; f <= 5; f++) {
            const isCurrentlyActive = currentMap.has(f);
            const wasPreviouslyActive = prevMap.has(f);
            const isRepeated = isNewChord && isCurrentlyActive && wasPreviouslyActive;
            const item = currentMap.get(f);

            _animateFinger(
                prefix,
                f,
                isCurrentlyActive,
                item ? item.color : null,
                isRepeated
            );
        }

        _previousActive[prefix] = currentMap;
    }

    function _buildChips(chipsEl, fingerList) {
        if (!chipsEl) return;
        if (!fingerList || !fingerList.length) {
            chipsEl.innerHTML = '<span class="ws-chip-idle">—</span>';
            return;
        }
        chipsEl.innerHTML = fingerList.map(item => {
            const chipColor = item.color || FINGER_COLORS[item.finger] || '#0071E3';
            return `<div class="ws-finger-chip" style="border-left: 4px solid ${chipColor}">
                <span class="ws-chip-fnum">Finger ${item.finger}</span>
                <span class="ws-chip-note">${item.note || ''}</span>
            </div>`;
        }).join('');
    }

    const WorkspaceHandController = {
        /**
         * init() — Mounts DOM references and attaches media queries.
         */
        init() {
            _lhSvgEl   = document.getElementById('ws-lh-svg');
            _rhSvgEl   = document.getElementById('ws-rh-svg');
            _lhChipsEl = document.getElementById('ws-lh-chips');
            _rhChipsEl = document.getElementById('ws-rh-chips');

            try {
                _reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
            } catch (e) {
                _reducedMotion = false;
            }

            this.reset();
        },

        /**
         * update() — Called to synchronize hand state with current chord voicing.
         */
        update(chordName, notes, voicing) {
            const lh = (voicing && voicing.leftHand)  ? voicing.leftHand  : [];
            const rh = (voicing && voicing.rightHand) ? voicing.rightHand : [];

            // Compute unique chord signature to detect actual chord boundary switches
            const chordKey = `${chordName || 'none'}|${lh.map(x => x.midi).join(',')}|${rh.map(x => x.midi).join(',')}`;
            const isNewChord = (chordKey !== _lastChordKey);

            if (!isNewChord) {
                // Same chord: fingers remain comfortably pressed, zero DOM churn
                return;
            }

            _lastChordKey = chordKey;

            _updateHand('lh', lh, true);
            _updateHand('rh', rh, true);
            _buildChips(_lhChipsEl, lh);
            _buildChips(_rhChipsEl, rh);
        },

        /**
         * reset() — Instantly resets fingers to neutral resting state.
         */
        reset() {
            _lastChordKey = null;

            // Cancel any in-flight WAAPI animations
            _activeAnims.forEach(anim => {
                try { anim.cancel(); } catch (e) {}
            });
            _activeAnims.clear();

            _previousActive.lh.clear();
            _previousActive.rh.clear();

            for (let f = 1; f <= 5; f++) {
                _animateFinger('lh', f, false, null, false);
                _animateFinger('rh', f, false, null, false);
            }

            if (_lhChipsEl) _lhChipsEl.innerHTML = '<span class="ws-chip-idle">—</span>';
            if (_rhChipsEl) _rhChipsEl.innerHTML = '<span class="ws-chip-idle">—</span>';
        }
    };

    global.WorkspaceHandController = WorkspaceHandController;

    if (typeof module !== 'undefined' && module.exports) {
        module.exports = { WorkspaceHandController };
    }

})(typeof window !== 'undefined' ? window : (typeof global !== 'undefined' ? global : this));
