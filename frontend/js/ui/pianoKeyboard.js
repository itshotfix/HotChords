/**
 * pianoKeyboard.js
 * Professional 61-key responsive piano engine for HotChords.
 *
 * Architectural Standards:
 * - 61-key docked keyboard (MIDI C2 #36 to C7 #96, 36 white keys).
 * - Deterministic geometric model: every key has its own local coordinate system.
 * - Strict SVG layer stacking:
 *     <g id="piano-white-keys-layer"> (Layer 1 — White keys, bevels, labels, badges)
 *     <g id="piano-black-keys-layer"> (Layer 2 — Black keys, shadows, gloss, labels, badges)
 *   Ensures black keys unconditionally render above white keys under all state changes.
 * - Non-mutating active state: highlighting only changes fill, text colors, and badge visibility.
 *   Key geometry (x, y, width, height) remains strictly invariant.
 * - Deterministic Note Label System:
 *     - White key: Single centered <text> element anchored at (centerX, whiteLabelY).
 *     - Black key: Two independent centered <text> elements for sharp & flat enharmonics at (blackCenterX, line1Y) and (blackCenterX, line2Y).
 *     - Zero <tspan> baseline drift. High-contrast white when active.
 * - Playback-state-driven finger badge visibility via PlaybackClock.
 */

const KEYBOARD_61_CONFIG = {
    startNote: 36, // C2
    endNote: 96,   // C7
    totalKeys: 61,
    whiteKeysCount: 36
};

class PianoKeyboard {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.voicing = null;
        this.dimensions = { W: 0, H: 0 };

        window.piano = this;

        this.render();
        const observer = new ResizeObserver(() => {
            if (!this.container) return;
            const W = this.container.clientWidth;
            const H = this.container.clientHeight;
            if (W !== this.dimensions.W || H !== this.dimensions.H) {
                this.render();
            }
        });
        if (this.container) observer.observe(this.container);
    }

    render() {
        if (!this.container) return;

        const W = this.container.clientWidth;
        const H = this.container.clientHeight;
        if (W === 0 || H === 0) return;

        this.dimensions = { W, H };

        // Exact geometric proportions
        this.whiteKeyWidth = W / KEYBOARD_61_CONFIG.whiteKeysCount;
        this.blackKeyWidth = this.whiteKeyWidth * 0.64;
        this.whiteKeyHeight = H;
        this.blackKeyHeight = Math.round(this.whiteKeyHeight * 0.60);

        // Dynamic font sizing calibrated to key widths
        const whiteLabelFontSize = Math.max(7, Math.min(13, this.whiteKeyWidth * 0.36));
        const blackLabelFontSize = Math.max(6, Math.min(10, this.blackKeyWidth * 0.38));
        const whiteFingerFontSize = Math.max(8, Math.min(13, this.whiteKeyWidth * 0.34));
        const blackFingerFontSize = Math.max(7, Math.min(11, this.blackKeyWidth * 0.35));

        const WHITE_PAT = [0, 2, 4, 5, 7, 9, 11];
        const BLACK_OFFSETS = { 1: 0.67, 3: 1.74, 6: 3.67, 8: 4.71, 10: 5.76 };
        const NOTE_NAMES = ['C','','D','','E','F','','G','','A','','B'];
        const BLACK_LABELS = { 1: 'C# Db', 3: 'D# Eb', 6: 'F# Gb', 8: 'G# Ab', 10: 'A# Bb' };

        let s = `<svg id="piano-svg" width="100%" height="100%" viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" style="display:block; width:100%; height:100%;">
            <defs>
                <linearGradient id="whiteKeyGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" style="stop-color:#FFFFFF;stop-opacity:1" />
                    <stop offset="85%" style="stop-color:#F5F5F7;stop-opacity:1" />
                    <stop offset="100%" style="stop-color:#E8E8ED;stop-opacity:1" />
                </linearGradient>
                <linearGradient id="blackKeyGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" style="stop-color:#48484A;stop-opacity:1" />
                    <stop offset="18%" style="stop-color:#2C2C2E;stop-opacity:1" />
                    <stop offset="88%" style="stop-color:#1C1C1E;stop-opacity:1" />
                    <stop offset="100%" style="stop-color:#000000;stop-opacity:1" />
                </linearGradient>
            </defs>`;

        // ══════════════════════════════════════════════════════════════
        // LAYER 1: WHITE KEYS LAYER (Rendered underneath black keys)
        // ══════════════════════════════════════════════════════════════
        s += `<g id="piano-white-keys-layer" class="piano-white-keys-layer">`;
        let wIdx = 0;
        const whiteLabelY = Math.round(this.whiteKeyHeight - Math.max(12, this.whiteKeyHeight * 0.08));
        const whiteDotY = Math.round(this.whiteKeyHeight * 0.74);
        const whiteDotR = Math.max(7, Math.min(11, this.whiteKeyWidth * 0.22));

        for (let n = KEYBOARD_61_CONFIG.startNote; n <= KEYBOARD_61_CONFIG.endNote; n++) {
            const noteInOct = n % 12;
            if (WHITE_PAT.includes(noteInOct)) {
                const x = wIdx * this.whiteKeyWidth;
                const centerX = Math.round((x + this.whiteKeyWidth / 2) * 10) / 10;

                // Main White Key Body (Invariant geometry)
                s += `<rect id="key-${n}" x="${x}" y="0" width="${this.whiteKeyWidth - 0.8}" height="${this.whiteKeyHeight}"
                        fill="url(#whiteKeyGrad)"
                        stroke="#D2D2D7" stroke-width="0.5" rx="3.5" class="white-key" style="transition: fill 0.1s ease;"/>`;

                // Bottom Bevel Edge
                s += `<path id="bevel-${n}" d="M${x+1},${this.whiteKeyHeight-4} Q${x+1},${this.whiteKeyHeight} ${x+4},${this.whiteKeyHeight} L${x+this.whiteKeyWidth-5},${this.whiteKeyHeight} Q${x+this.whiteKeyWidth-1},${this.whiteKeyHeight} ${x+this.whiteKeyWidth-1},${this.whiteKeyHeight-4} L${x+this.whiteKeyWidth-1},${this.whiteKeyHeight-8} L${x+1},${this.whiteKeyHeight-8} Z" fill="rgba(0,0,0,0.05)" pointer-events="none" style="transition: opacity 0.1s ease;"/>`;

                // Note Label (Stable bottom region, horizontally centered)
                const label = NOTE_NAMES[noteInOct];
                s += `<text id="key-label-${n}" x="${centerX}" y="${whiteLabelY}"
                        class="key-label key-label--white" font-size="${whiteLabelFontSize}" fill="#6E6E73" font-weight="700" text-anchor="middle" dominant-baseline="central" alignment-baseline="central" style="transition: fill 0.1s ease; pointer-events: none; user-select: none;">${label}</text>`;

                // Finger Badge Circle & Text (Geometrically centered)
                s += `<circle id="finger-dot-${n}" cx="${centerX}" cy="${whiteDotY}" r="${whiteDotR}" fill="rgba(0,0,0,0.30)" stroke="#FFFFFF" stroke-width="1.2" style="opacity: 0; transition: opacity 0.1s ease;" pointer-events="none" />`;
                s += `<text id="finger-text-${n}" x="${centerX}" y="${whiteDotY}"
                        class="key-label key-finger-text" font-size="${whiteFingerFontSize}" font-weight="800" fill="#FFFFFF" text-anchor="middle" dominant-baseline="central" alignment-baseline="central" dy="0.06em" style="opacity: 0; transition: opacity 0.1s ease;" pointer-events="none; user-select: none;"></text>`;

                wIdx++;
            }
        }
        s += `</g>`;

        // ══════════════════════════════════════════════════════════════
        // LAYER 2: BLACK KEYS LAYER (Rendered strictly above white keys)
        // ══════════════════════════════════════════════════════════════
        s += `<g id="piano-black-keys-layer" class="piano-black-keys-layer">`;
        wIdx = 0;
        const labelLine1Y = Math.round(this.blackKeyHeight * 0.18);
        const labelLine2Y = Math.round(this.blackKeyHeight * 0.36);
        const blackDotY = Math.round(this.blackKeyHeight * 0.74);
        const blackDotR = Math.max(6.5, Math.min(9.5, this.blackKeyWidth * 0.28));

        for (let n = KEYBOARD_61_CONFIG.startNote; n <= KEYBOARD_61_CONFIG.endNote; n++) {
            const noteInOct = n % 12;
            if (WHITE_PAT.includes(noteInOct)) {
                const octaveStartIdx = wIdx - (WHITE_PAT.indexOf(noteInOct));
                if (noteInOct === 0) {
                    [1, 3, 6, 8, 10].forEach(offset => {
                        const absNote = (n - noteInOct) + offset;
                        if (absNote >= KEYBOARD_61_CONFIG.startNote && absNote <= KEYBOARD_61_CONFIG.endNote) {
                            const pos = BLACK_OFFSETS[offset];
                            const blackX = (octaveStartIdx + pos) * this.whiteKeyWidth - this.blackKeyWidth / 2;
                            const blackCenterX = Math.round((blackX + this.blackKeyWidth / 2) * 10) / 10;

                            // Shadow cast on white keys
                            s += `<rect id="shadow-${absNote}" x="${blackX + 1.5}" y="0" width="${this.blackKeyWidth + 1.5}" height="${this.blackKeyHeight + 3}" fill="rgba(0,0,0,0.18)" rx="2.5" filter="blur(1.5px)"/>`;

                            // Main Black Key Body (Invariant geometry)
                            s += `<rect id="key-${absNote}" x="${blackX}" y="0" width="${this.blackKeyWidth}" height="${this.blackKeyHeight}"
                                    fill="url(#blackKeyGrad)"
                                    rx="2.5" class="black-key" style="transition: fill 0.1s ease;"/>`;

                            // Glossy Top Surface
                            s += `<rect id="gloss-${absNote}" x="${blackX + 1.5}" y="1.5" width="${this.blackKeyWidth - 3}" height="${this.blackKeyHeight * 0.10}" fill="rgba(255,255,255,0.08)" rx="1.5" pointer-events="none"/>`;

                            // Black Key Note Label (2 independent, centered text elements for enharmonics)
                            const label = BLACK_LABELS[offset];
                            const lines = label.split(' ');
                            s += `<text id="key-label-${absNote}-1" x="${blackCenterX}" y="${labelLine1Y}"
                                    class="key-label key-label--black" font-size="${blackLabelFontSize}" font-weight="700" fill="rgba(255,255,255,0.70)" text-anchor="middle" dominant-baseline="central" alignment-baseline="central" style="transition: fill 0.1s ease; pointer-events: none; user-select: none;">${lines[0]}</text>`;
                            s += `<text id="key-label-${absNote}-2" x="${blackCenterX}" y="${labelLine2Y}"
                                    class="key-label key-label--black" font-size="${blackLabelFontSize}" font-weight="700" fill="rgba(255,255,255,0.70)" text-anchor="middle" dominant-baseline="central" alignment-baseline="central" style="transition: fill 0.1s ease; pointer-events: none; user-select: none;">${lines[1]}</text>`;

                            // Black Key Finger Badge Circle & Text (Geometrically centered)
                            s += `<circle id="finger-dot-${absNote}" cx="${blackCenterX}" cy="${blackDotY}" r="${blackDotR}" fill="rgba(0,0,0,0.35)" stroke="#FFFFFF" stroke-width="1.2" style="opacity: 0; transition: opacity 0.1s ease;" pointer-events="none" />`;
                            s += `<text id="finger-text-${absNote}" x="${blackCenterX}" y="${blackDotY}"
                                    class="key-label key-finger-text" font-size="${blackFingerFontSize}" font-weight="800" fill="#FFFFFF" text-anchor="middle" dominant-baseline="central" alignment-baseline="central" dy="0.06em" style="opacity: 0; transition: opacity 0.1s ease;" pointer-events="none; user-select: none;"></text>`;
                        }
                    });
                }
                wIdx++;
            }
        }
        s += `</g>`;

        s += '</svg>';
        this.container.innerHTML = s;

        // Re-apply voicing if currently active
        this.applyVoicingDOM();
    }

    /**
     * Applies active voicing styling to the DOM keys without altering key dimensions or positions.
     * @param {boolean|null} showFingers - Explicit override for finger indicator visibility. Defaults to checking PlaybackClock state.
     */
    applyVoicingDOM(showFingers = null) {
        const WHITE_PAT = [0, 2, 4, 5, 7, 9, 11];
        const isPlayingOrPaused = (typeof PlaybackClock !== 'undefined')
            ? (PlaybackClock.state === 'PLAYING' || PlaybackClock.state === 'PAUSED')
            : false;
        const shouldShowFingers = (showFingers !== null) ? Boolean(showFingers) : isPlayingOrPaused;

        // 1. Fast path reset: restore resting default styling across all 61 keys (preserving exact geometry)
        for (let n = KEYBOARD_61_CONFIG.startNote; n <= KEYBOARD_61_CONFIG.endNote; n++) {
            const isWhite = WHITE_PAT.includes(n % 12);
            const keyEl = document.getElementById(`key-${n}`);
            const bevelEl = document.getElementById(`bevel-${n}`);
            const labelEl = document.getElementById(`key-label-${n}`);
            const label1El = document.getElementById(`key-label-${n}-1`);
            const label2El = document.getElementById(`key-label-${n}-2`);
            const dotEl = document.getElementById(`finger-dot-${n}`);
            const textEl = document.getElementById(`finger-text-${n}`);

            if (keyEl) {
                keyEl.style.fill = isWhite ? 'url(#whiteKeyGrad)' : 'url(#blackKeyGrad)';
            }
            if (bevelEl) {
                bevelEl.style.opacity = 1;
            }
            if (labelEl) {
                labelEl.style.fill = '#6E6E73';
                labelEl.style.fontWeight = '700';
            }
            if (label1El) {
                label1El.style.fill = 'rgba(255,255,255,0.70)';
                label1El.style.fontWeight = '700';
            }
            if (label2El) {
                label2El.style.fill = 'rgba(255,255,255,0.70)';
                label2El.style.fontWeight = '700';
            }
            if (dotEl) {
                dotEl.style.opacity = 0;
            }
            if (textEl) {
                textEl.style.opacity = 0;
                textEl.textContent = '';
            }
        }

        if (!this.voicing) {
            if (window.KeyboardOverlayManager) window.KeyboardOverlayManager.updateHandPositions();
            return;
        }

        // 2. Color active voicing notes (geometry remains strictly invariant)
        const activeNotes = [...this.voicing.leftHand, ...this.voicing.rightHand];

        activeNotes.forEach(v => {
            const n = v.midi;
            const isWhite = WHITE_PAT.includes(n % 12);
            const keyEl = document.getElementById(`key-${n}`);
            const bevelEl = document.getElementById(`bevel-${n}`);
            const labelEl = document.getElementById(`key-label-${n}`);
            const label1El = document.getElementById(`key-label-${n}-1`);
            const label2El = document.getElementById(`key-label-${n}-2`);
            const dotEl = document.getElementById(`finger-dot-${n}`);
            const textEl = document.getElementById(`finger-text-${n}`);

            if (keyEl) {
                keyEl.style.fill = v.color;
            }
            if (bevelEl) {
                bevelEl.style.opacity = 0;
            }
            if (labelEl) {
                labelEl.style.fill = '#FFFFFF';
                labelEl.style.fontWeight = '800';
            }
            if (label1El) {
                label1El.style.fill = '#FFFFFF';
                label1El.style.fontWeight = '800';
            }
            if (label2El) {
                label2El.style.fill = '#FFFFFF';
                label2El.style.fontWeight = '800';
            }
            if (dotEl) {
                dotEl.style.opacity = shouldShowFingers ? 1 : 0;
            }
            if (textEl) {
                textEl.style.opacity = shouldShowFingers ? 1 : 0;
                textEl.textContent = shouldShowFingers ? v.finger : '';
            }
        });
    }

    setChord(chordName, notes) {
        if (!notes || notes.length === 0) {
            this.voicing = null;
            this.applyVoicingDOM();
            return;
        }

        this.voicing = window.PianoFingeringEngine.getChordVoicing(chordName, notes);
        this.applyVoicingDOM();
    }

    getKeyPosition(midiNote) {
        const rect = document.getElementById(`key-${midiNote}`);
        if (!rect) return null;

        const svg = rect.ownerSVGElement;
        if (!svg) return null;

        const bbox = rect.getBBox();
        const pt = svg.createSVGPoint();
        pt.x = bbox.x + bbox.width / 2;
        pt.y = bbox.y;

        const matrix = svg.getScreenCTM();
        if (!matrix) return null;

        const globalPt = pt.matrixTransform(matrix);
        return globalPt.x;
    }
}

window.PianoKeyboard = PianoKeyboard;
