/**
 * pianoKeyboard.js
 * Professional 61-key responsive piano engine.
 * 
 * Performance architecture (Realism V4):
 * We build the SVG dynamically ONCE per resize. During audio playback,
 * chord changes only update DOM element attributes (fill, y, height, opacity).
 * We strictly AVOID innerHTML re-renders to maintain 60fps and prevent
 * memory leaks or GC stuttering during fast chord progressions.
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
        
        // Fix: Set global reference before first render to ensure overlay manager works
        window.piano = this;

        this.render();
        const observer = new ResizeObserver(() => {
            const W = this.container.clientWidth;
            const H = this.container.clientHeight;
            // Only perform full SVG reconstruction if container dimensions actually changed
            if (W !== this.dimensions.W || H !== this.dimensions.H) {
                this.render();
            }
        });
        observer.observe(this.container);
    }

    render() {
        if (!this.container) return;
        
        const W = this.container.clientWidth;
        const H = this.container.clientHeight;
        if (W === 0 || H === 0) return;

        this.dimensions = { W, H };
        
        // Proportions: Black key width is 64% of white key width.

        // Height is bounded to prevent overly elongated keys on wide screens.
        this.whiteKeyWidth = W / KEYBOARD_61_CONFIG.whiteKeysCount;
        this.blackKeyWidth = this.whiteKeyWidth * 0.64;
        this.whiteKeyHeight = Math.min(H, this.whiteKeyWidth * 5.8);
        this.blackKeyHeight = this.whiteKeyHeight * 0.62;

        // Dynamic Font Sizing (scales linearly with key width, clamped to sensible min/max)
        const whiteLabelFontSize = Math.max(10, Math.min(16, this.whiteKeyWidth * 0.45));
        const blackLabelFontSize = Math.max(8, Math.min(13, this.blackKeyWidth * 0.45));
        const fingerFontSize = Math.max(10, Math.min(14, this.whiteKeyWidth * 0.35));

        const WHITE_PAT = [0, 2, 4, 5, 7, 9, 11];
        // Mathematical offsets for black keys relative to their home white key.
        // Because C-D-E has 2 black keys but F-G-A-B has 3, the spacing isn't uniform.
        const BLACK_OFFSETS = { 1: 0.67, 3: 1.74, 6: 3.67, 8: 4.71, 10: 5.76 };
        const NOTE_NAMES = ['C','','D','','E','F','','G','','A','','B'];
        const BLACK_LABELS = { 1: 'C# Db', 3: 'D# Eb', 6: 'F# Gb', 8: 'G# Ab', 10: 'A# Bb' };

        let s = `<svg id="piano-svg" width="100%" height="100%" viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMin slice" style="filter: drop-shadow(0 4px 6px rgba(0,0,0,0.1))">
            <defs>
                <linearGradient id="whiteKeyGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" style="stop-color:#FFFFFF;stop-opacity:1" />
                    <stop offset="85%" style="stop-color:#F5F5F7;stop-opacity:1" />
                    <stop offset="100%" style="stop-color:#E8E8ED;stop-opacity:1" />
                </linearGradient>
                <linearGradient id="blackKeyGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" style="stop-color:#4A4A4A;stop-opacity:1" />
                    <stop offset="15%" style="stop-color:#2C2C2E;stop-opacity:1" />
                    <stop offset="90%" style="stop-color:#1D1D1F;stop-opacity:1" />
                    <stop offset="100%" style="stop-color:#000000;stop-opacity:1" />
                </linearGradient>
            </defs>`;

        // 1. White Keys
        let wIdx = 0;
        for (let n = KEYBOARD_61_CONFIG.startNote; n <= KEYBOARD_61_CONFIG.endNote; n++) {
            const noteInOct = n % 12;
            if (WHITE_PAT.includes(noteInOct)) {
                const x = wIdx * this.whiteKeyWidth;

                // Main Key Body
                s += `<rect id="key-${n}" x="${x}" y="0" width="${this.whiteKeyWidth - 0.8}" height="${this.whiteKeyHeight}" 
                        fill="url(#whiteKeyGrad)" 
                        stroke="#D2D2D7" stroke-width="0.5" rx="4" class="white-key" style="transition: fill 0.1s ease, y 0.1s ease, height 0.1s ease;"/>`;
                
                // Bottom Bevel (Darker edge)
                s += `<path id="bevel-${n}" d="M${x+1},${this.whiteKeyHeight-4} Q${x+1},${this.whiteKeyHeight} ${x+4},${this.whiteKeyHeight} L${x+this.whiteKeyWidth-5},${this.whiteKeyHeight} Q${x+this.whiteKeyWidth-1},${this.whiteKeyHeight} ${x+this.whiteKeyWidth-1},${this.whiteKeyHeight-4} L${x+this.whiteKeyWidth-1},${this.whiteKeyHeight-8} L${x+1},${this.whiteKeyHeight-8} Z" fill="rgba(0,0,0,0.05)" pointer-events="none" style="transition: opacity 0.1s ease;"/>`;

                // Label
                const label = NOTE_NAMES[noteInOct];
                s += `<text id="key-label-${n}" x="${x + this.whiteKeyWidth / 2}" y="${this.whiteKeyHeight - 14}" 
                        class="key-label" font-size="${whiteLabelFontSize}" fill="#6E6E73" font-weight="600" opacity="0.8" style="transition: fill 0.1s ease; pointer-events: none;">${label}</text>`;
                
                // Finger Dot & Text (Hidden initially)
                const dotY = this.whiteKeyHeight * 0.76;
                s += `<circle id="finger-dot-${n}" cx="${x + this.whiteKeyWidth / 2}" cy="${dotY}" r="${this.whiteKeyWidth*0.22}" fill="rgba(255,255,255,0.3)" style="opacity: 0; transition: opacity 0.1s ease;" pointer-events="none" />`;
                s += `<text id="finger-text-${n}" x="${x + this.whiteKeyWidth / 2}" y="${dotY + 4}" 
                        class="key-label" font-size="${fingerFontSize}" font-weight="800" fill="#fff" style="opacity: 0; transition: opacity 0.1s ease;" pointer-events="none"></text>`;
                
                wIdx++;
            }
        }

        // 2. Black Keys
        wIdx = 0;
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

                            // Shadow cast on white keys
                            s += `<rect id="shadow-${absNote}" x="${blackX + 2}" y="0" width="${this.blackKeyWidth + 2}" height="${this.blackKeyHeight + 4}" fill="rgba(0,0,0,0.15)" rx="3" filter="blur(2px)"/>`;

                            // Main Black Key Body
                            s += `<rect id="key-${absNote}" x="${blackX}" y="0" width="${this.blackKeyWidth}" height="${this.blackKeyHeight}" 
                                    fill="url(#blackKeyGrad)" 
                                    rx="3" class="black-key" style="transition: fill 0.1s ease, y 0.1s ease, height 0.1s ease;"/>`;
                            
                            // Glossy Top Surface
                            s += `<rect id="gloss-${absNote}" x="${blackX + 2}" y="2" width="${this.blackKeyWidth - 4}" height="${this.blackKeyHeight * 0.1}" fill="rgba(255,255,255,0.08)" rx="1.5" pointer-events="none"/>`;

                            // Label (Both names, Dynamic Size)
                            const label = BLACK_LABELS[offset];
                            const lines = label.split(' ');
                            s += `<text id="key-label-${absNote}" x="${blackX + this.blackKeyWidth / 2}" y="${this.blackKeyHeight * 0.35}" 
                                    class="key-label" font-size="${blackLabelFontSize}" font-weight="700" fill="rgba(255,255,255,0.45)" style="transition: fill 0.1s ease; pointer-events: none;">
                                    <tspan x="${blackX + this.blackKeyWidth / 2}" dy="0">${lines[0]}</tspan>
                                    <tspan x="${blackX + this.blackKeyWidth / 2}" dy="${blackLabelFontSize + 2}">${lines[1]}</tspan>
                                  </text>`;

                            // Finger Dot & Text (Hidden initially)
                            const dotY = this.blackKeyHeight * 0.72;
                            s += `<circle id="finger-dot-${absNote}" cx="${blackX + this.blackKeyWidth / 2}" cy="${dotY}" r="${this.blackKeyWidth*0.32}" fill="rgba(255,255,255,0.2)" style="opacity: 0; transition: opacity 0.1s ease;" pointer-events="none" />`;
                            s += `<text id="finger-text-${absNote}" x="${blackX + this.blackKeyWidth / 2}" y="${dotY + 4}" 
                                    class="key-label" font-size="${blackLabelFontSize * 1.1}" font-weight="900" fill="#fff" style="opacity: 0; transition: opacity 0.1s ease;" pointer-events="none"></text>`;
                        }
                    });
                }
                wIdx++;
            }
        }

        s += '</svg>';
        this.container.innerHTML = s;
        
        // Re-apply voicing if it is currently set
        this.applyVoicingDOM();
    }

    applyVoicingDOM() {
        const WHITE_PAT = [0, 2, 4, 5, 7, 9, 11];
        
        // 1. Fast path reset: loop all keys and restore default styling.
        // This is highly optimized in the browser because we only touch DOM elements
        // that are explicitly selected by ID, and CSS transitions handle the visual smoothing.
        for (let n = KEYBOARD_61_CONFIG.startNote; n <= KEYBOARD_61_CONFIG.endNote; n++) {
            const isWhite = WHITE_PAT.includes(n % 12);
            const keyEl = document.getElementById(`key-${n}`);
            const bevelEl = document.getElementById(`bevel-${n}`);
            const labelEl = document.getElementById(`key-label-${n}`);
            const dotEl = document.getElementById(`finger-dot-${n}`);
            const textEl = document.getElementById(`finger-text-${n}`);
            
            if (keyEl) {
                keyEl.style.fill = isWhite ? 'url(#whiteKeyGrad)' : 'url(#blackKeyGrad)';
                keyEl.setAttribute('y', 0);
                keyEl.setAttribute('height', isWhite ? this.whiteKeyHeight : this.blackKeyHeight);
            }
            if (bevelEl) {
                bevelEl.style.opacity = 1;
            }
            if (labelEl) {
                labelEl.style.fill = isWhite ? '#6E6E73' : 'rgba(255,255,255,0.45)';
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
        
        // 2. Color and depress active voicing notes
        const activeNotes = [...this.voicing.leftHand, ...this.voicing.rightHand];
        
        activeNotes.forEach(v => {
            const n = v.midi;
            const isWhite = WHITE_PAT.includes(n % 12);
            const keyEl = document.getElementById(`key-${n}`);
            const bevelEl = document.getElementById(`bevel-${n}`);
            const labelEl = document.getElementById(`key-label-${n}`);
            const dotEl = document.getElementById(`finger-dot-${n}`);
            const textEl = document.getElementById(`finger-text-${n}`);
            
            if (keyEl) {
                keyEl.style.fill = v.color;
                keyEl.setAttribute('y', isWhite ? 3 : 4);
                keyEl.setAttribute('height', isWhite ? this.whiteKeyHeight - 2 : this.blackKeyHeight - 2);
            }
            if (bevelEl) {
                bevelEl.style.opacity = 0; // Hide the bottom bevel edge while pressed
            }
            if (labelEl) {
                labelEl.style.fill = '#fff';
            }
            if (dotEl) {
                dotEl.style.opacity = 1;
            }
            if (textEl) {
                textEl.style.opacity = 1;
                textEl.textContent = v.finger;
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
