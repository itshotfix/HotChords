/**
 * workspaceHandController.js
 *
 * WorkspaceHandController for HotChords.
 * Coordinates Left Hand (Bass) and Right Hand (Harmony) SVG diagrams in real time:
 * - Direct finger highlight and key-press downward animation (WAAPI / CSS transform).
 * - Exact finger numbering and note chips.
 * - Perfectly synchronized with PianoFingeringEngine and PianoKeyboard highlights.
 */

(function(global) {
    'use strict';

    // Color palette aligned with PianoFingeringEngine & PianoKeyboard
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

    function _findInSvg(svgEl, selector) {
        if (!svgEl) return null;
        return svgEl.querySelector(selector);
    }

    function _animateFinger(prefix, fingerNum, isActive, color) {
        const rootSvg  = prefix === 'lh' ? _lhSvgEl : _rhSvgEl;
        if (!rootSvg) return;

        const groupEl  = _findInSvg(rootSvg, `#${prefix}-finger-${fingerNum}`);
        const pathEl   = groupEl ? groupEl.querySelector('path') : null;
        const dotEl    = _findInSvg(rootSvg, `#${prefix}-finger-dot-${fingerNum}`);
        const numEl    = _findInSvg(rootSvg, `#${prefix}-finger-num-${fingerNum}`);

        const activeColor = color || FINGER_COLORS[fingerNum] || '#0071E3';

        if (groupEl) {
            groupEl.style.transition = 'transform 0.2s cubic-bezier(0.22, 1, 0.36, 1)';
            groupEl.style.transform  = isActive ? 'translateY(5px)' : 'translateY(0)';
        }

        if (pathEl) {
            pathEl.style.transition = 'stroke 0.2s ease, fill 0.2s ease';
            pathEl.style.fill   = isActive ? 'rgba(0, 113, 227, 0.06)' : '#FFFFFF';
            pathEl.style.stroke = isActive ? activeColor : '#D2D2D7';
            pathEl.style.strokeWidth = isActive ? '2.5' : '1.5';
        }

        if (dotEl) {
            dotEl.style.transition = 'fill 0.2s ease, stroke 0.2s ease, filter 0.2s ease';
            dotEl.style.fill   = isActive ? activeColor : '#E5E5EA';
            dotEl.style.stroke = isActive ? '#FFFFFF' : '#D2D2D7';
            dotEl.style.strokeWidth = isActive ? '2.5' : '1.5';
            dotEl.style.filter = isActive ? `drop-shadow(0 2px 6px ${activeColor}66)` : 'none';
        }

        if (numEl) {
            numEl.style.transition = 'fill 0.2s ease, opacity 0.2s ease';
            numEl.style.opacity = isActive ? '1' : '0.35';
            numEl.style.fill    = isActive ? '#FFFFFF' : '#1D1D1F';
        }
    }

    function _updateHandFingers(prefix, activeFingers) {
        // activeFingers: Array<{ finger: 1-5, note: string, color?: string }>
        const list = Array.isArray(activeFingers) ? activeFingers : [];
        for (let f = 1; f <= 5; f++) {
            const item = list.find(i => i.finger === f);
            _animateFinger(prefix, f, !!item, item ? (item.color || FINGER_COLORS[f]) : null);
        }
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
         * init() — Mounts DOM references to the persistent hand containers.
         */
        init() {
            _lhSvgEl   = document.getElementById('ws-lh-svg');
            _rhSvgEl   = document.getElementById('ws-rh-svg');
            _lhChipsEl = document.getElementById('ws-lh-chips');
            _rhChipsEl = document.getElementById('ws-rh-chips');
        },

        /**
         * update() — Called on every chord change to update fingering and trigger finger press animation.
         */
        update(chordName, notes, voicing) {
            const lh = (voicing && voicing.leftHand)  ? voicing.leftHand  : [];
            const rh = (voicing && voicing.rightHand) ? voicing.rightHand : [];

            _updateHandFingers('lh', lh);
            _updateHandFingers('rh', rh);
            _buildChips(_lhChipsEl, lh);
            _buildChips(_rhChipsEl, rh);
        },

        /**
         * reset() — Resets fingers to neutral resting state.
         */
        reset() {
            for (let f = 1; f <= 5; f++) {
                _animateFinger('lh', f, false, null);
                _animateFinger('rh', f, false, null);
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
