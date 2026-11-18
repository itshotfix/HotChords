/**
 * pianoStudio2D.js
 *
 * HotChords 2D Piano Roll Studio — Rounded 88-Lane Waterfall Panel & Separated
 * Realistic 88-Key Piano Bed with Finger Number Badges.
 *
 * Visual & Behavioral Specification:
 * - Upper Rounded Waterfall Stage (#121216, 1px white/8 border, 14px corner radius):
 *     * 88 vertical key columns with subtle alternating white/black key lane shading.
 *     * Horizontal beat & measure grid lines.
 *     * Note bars styled by musical source:
 *         - Melody       : Warm Cream (#F7F4EF)
 *         - Accompaniment: Medium Slate (#9696A2)
 *         - Chords       : Charcoal Slate (#666672)
 *     * Active notes emit a warm Coral Rose (#FF5A7A) or Royal Lavender (#8B6EFE) glow halo.
 *     * Chord pills (e.g. "Bm", "C#", "F#") anchored at chord changes.
 * - Separated 88-Key Realistic 2D Keyboard Below Waterfall:
 *     * 52 ivory white keys and 36 sculpted black keys.
 *     * Active Right-Hand keys illuminate in Coral Rose (#FF5A7A); Left-Hand in Royal Lavender (#7B64FF).
 *     * Circular contrast badge near the bottom of each active key displays the finger number (1..5).
 */

(function(global) {
    'use strict';

    const WHITE_PCS = new Set([0, 2, 4, 5, 7, 9, 11]);
    const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];

    const HAND_ACTIVE_THEME = {
        left: {
            keyFill: '#7B64FF',
            glow: 'rgba(139, 110, 254, 0.70)'
        },
        right: {
            keyFill: '#FF5A7A',
            glow: 'rgba(255, 90, 122, 0.70)'
        }
    };

    const SOURCE_FILLS = {
        melody: '#F7F4EF',
        accompaniment: '#9696A2',
        chord: '#666672'
    };

    class PianoStudio2D {
        constructor(containerEl, options = {}) {
            this.container = typeof containerEl === 'string'
                ? (typeof document !== 'undefined' ? document.getElementById(containerEl) : null)
                : containerEl;
            this.adapter = options.adapter || global.StudioTimelineAdapter;
            this.lookAheadSec = options.lookAheadSec || 3.2;
            this.keyMap = {};
            this.canvas = null;
            this.ctx = null;
            this.width = 0;
            this.height = 0;
            this.currentTime = 0;
            this.showFingerBadges = true;
            this.showColourKey = options.showColourKey !== undefined ? Boolean(options.showColourKey) : true;

            if (this.container) {
                this._initDOM();
            }
        }

        setShowColourKey(visible) {
            this.showColourKey = Boolean(visible);
            this.render(this.currentTime);
        }

        _initDOM() {
            if (!this.container || typeof document === 'undefined') return;
            this.container.innerHTML = '';
            this.canvas = document.createElement('canvas');
            this.canvas.className = 'piano-studio-2d-canvas';
            if (this.canvas.style) {
                this.canvas.style.width = '100%';
                this.canvas.style.height = '100%';
                this.canvas.style.display = 'block';
            }
            this.container.appendChild(this.canvas);

            if (typeof this.canvas.addEventListener === 'function') {
                this.canvas.addEventListener('click', (e) => this._handleCanvasClick(e));
            }

            this.resize();
            if (typeof ResizeObserver !== 'undefined') {
                this._ro = new ResizeObserver(() => this.resize());
                this._ro.observe(this.container);
            }
        }

        compute88KeyLayout(totalWidth, marginX = 0) {
            const innerW = Math.max(320, (Number(totalWidth) || 880) - marginX * 2);
            const whiteWidth = innerW / 52;
            const blackWidth = whiteWidth * 0.62;
            const map = {};

            let whiteIndex = 0;
            for (let midi = 21; midi <= 108; midi++) {
                const pc = midi % 12;
                const octave = Math.floor(midi / 12) - 1;
                if (WHITE_PCS.has(pc)) {
                    const x = marginX + whiteIndex * whiteWidth;
                    map[midi] = {
                        midi,
                        isBlack: false,
                        x,
                        width: whiteWidth,
                        centerX: x + whiteWidth / 2,
                        label: pc === 0 ? `C${octave}` : NOTE_NAMES[pc]
                    };
                    whiteIndex++;
                }
            }

            for (let midi = 21; midi <= 108; midi++) {
                const pc = midi % 12;
                if (!WHITE_PCS.has(pc)) {
                    const prevWhite = map[midi - 1];
                    const baseRight = prevWhite ? (prevWhite.x + prevWhite.width) : marginX;
                    const x = baseRight - blackWidth / 2;
                    map[midi] = {
                        midi,
                        isBlack: true,
                        x,
                        width: blackWidth,
                        centerX: x + blackWidth / 2,
                        label: NOTE_NAMES[pc]
                    };
                }
            }

            this.keyMap = map;
            return map;
        }

        resize() {
            if (!this.container || !this.canvas) return;
            const W = this.container.clientWidth || 1040;
            const H = this.container.clientHeight || 520;
            this.width = W;
            this.height = H;

            const dpr = (typeof window !== 'undefined' && window.devicePixelRatio) || 1;
            this.canvas.width = Math.round(W * dpr);
            this.canvas.height = Math.round(H * dpr);

            if (typeof this.canvas.getContext === 'function') {
                this.ctx = this.canvas.getContext('2d');
                if (this.ctx && typeof this.ctx.setTransform === 'function') {
                    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
                }
            }

            const padX = Math.round(Math.min(18, W * 0.015));
            this.compute88KeyLayout(W, padX);
            this.render(this.currentTime);
        }

        _handleCanvasClick(e) {
            if (!this.canvas || !this.height) return;
            const rect = this.canvas.getBoundingClientRect ? this.canvas.getBoundingClientRect() : { left: 0, top: 0 };
            const x = (e.clientX || 0) - rect.left;
            const y = (e.clientY || 0) - rect.top;

            const rollBottomY = Math.round(this.height * 0.74);
            const kbTopY = rollBottomY + 14;
            const kbH = this.height - kbTopY - 8;

            if (y >= kbTopY) {
                let clickedMidi = null;
                for (let m = 21; m <= 108; m++) {
                    const k = this.keyMap[m];
                    if (k && k.isBlack && x >= k.x && x <= k.x + k.width && y <= kbTopY + kbH * 0.62) {
                        clickedMidi = m;
                        break;
                    }
                }
                if (!clickedMidi) {
                    for (let m = 21; m <= 108; m++) {
                        const k = this.keyMap[m];
                        if (k && !k.isBlack && x >= k.x && x <= k.x + k.width) {
                            clickedMidi = m;
                            break;
                        }
                    }
                }
                if (clickedMidi) {
                    if (global.PianoPlaybackService) {
                        global.PianoPlaybackService.playNote(clickedMidi, 0.85, 0.45);
                    }
                    if (global.LearnModeController && global.LearnModeController.enabled) {
                        global.LearnModeController.submitUserNotes([clickedMidi]);
                    }
                }
            } else if (global.PlaybackClock) {
                const distRatio = (rollBottomY - y) / Math.max(1, rollBottomY);
                const targetTime = Math.max(0, this.currentTime + distRatio * this.lookAheadSec);
                global.PlaybackClock.seek(targetTime);
            }
        }

        render(currentTime = 0) {
            this.currentTime = Number(currentTime) || 0;
            const W = this.width || 1040;
            const H = this.height || 520;
            const padX = Math.round(Math.min(18, W * 0.015));

            if (!this.keyMap || Object.keys(this.keyMap).length === 0) {
                this.compute88KeyLayout(W, padX);
            }

            const winState = this.adapter
                ? this.adapter.getWindowState(this.currentTime, this.lookAheadSec, 0.4)
                : { activeNotes: [], upcomingNotes: [], completedNotes: [] };

            this.lastRenderedState = winState;

            const ctx = this.ctx;
            if (!ctx) return winState;

            const rollTopY = 6;
            const rollBottomY = Math.round(H * 0.74);
            const rollH = rollBottomY - rollTopY;
            const kbTopY = rollBottomY + 14;
            const kbH = Math.max(72, H - kbTopY - 8);
            const pixelsPerSec = rollH / this.lookAheadSec;

            // 1. Studio Root Background (#101012)
            ctx.fillStyle = '#101012';
            ctx.fillRect(0, 0, W, H);

            // 2. Rounded Waterfall Roll Panel
            ctx.save();
            ctx.fillStyle = '#141418';
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
            ctx.lineWidth = 1;
            ctx.beginPath();
            if (typeof ctx.roundRect === 'function') {
                ctx.roundRect(padX, rollTopY, W - padX * 2, rollH, 12);
            } else {
                ctx.rect(padX, rollTopY, W - padX * 2, rollH);
            }
            ctx.fill();
            ctx.stroke();

            // Vertical 88-key lane stripes
            for (let midi = 21; midi <= 108; midi++) {
                const k = this.keyMap[midi];
                if (!k) continue;
                if (k.isBlack) {
                    ctx.fillStyle = 'rgba(0, 0, 0, 0.22)';
                    ctx.fillRect(k.x, rollTopY + 1, k.width, rollH - 2);
                }
                if (midi % 12 === 0 || midi % 12 === 5) {
                    ctx.strokeStyle = midi % 12 === 0 ? 'rgba(255, 255, 255, 0.07)' : 'rgba(255, 255, 255, 0.03)';
                    ctx.lineWidth = 1;
                    ctx.beginPath();
                    ctx.moveTo(k.x, rollTopY + 1);
                    ctx.lineTo(k.x, rollBottomY - 1);
                    ctx.stroke();
                }
            }

            // Horizontal beat / grid lines
            const gridStepPx = Math.max(48, rollH / 4);
            for (let gy = rollBottomY - gridStepPx; gy > rollTopY + 10; gy -= gridStepPx) {
                ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(padX + 1, gy);
                ctx.lineTo(W - padX - 1, gy);
                ctx.stroke();
            }

            // 3. Falling Note Bars (Upcoming & Active)
            const notesToDraw = [...winState.upcomingNotes, ...winState.activeNotes];
            notesToDraw.forEach(n => {
                const k = this.keyMap[n.midi];
                if (!k) return;

                const noteBottomY = Math.min(rollBottomY - 2, rollBottomY - Math.max(0, n.start - this.currentTime) * pixelsPerSec);
                const noteTopY = Math.max(rollTopY + 2, rollBottomY - (n.end - this.currentTime) * pixelsPerSec);
                const barH = Math.max(7, noteBottomY - noteTopY);
                const inset = k.isBlack ? 0.8 : 1.4;
                const barX = k.x + inset;
                const barW = Math.max(4, k.width - inset * 2);

                const fill = this.showColourKey
                    ? (SOURCE_FILLS[n.source] || SOURCE_FILLS.melody)
                    : '#D8D6D0';
                const hTheme = this.showColourKey
                    ? (HAND_ACTIVE_THEME[n.hand] || HAND_ACTIVE_THEME.right)
                    : { keyFill: '#F7F4EF', glow: 'rgba(247, 244, 239, 0.5)' };

                ctx.save();
                ctx.fillStyle = fill;
                ctx.globalAlpha = n.state === 'active' ? 1.0 : 0.90;

                ctx.beginPath();
                if (typeof ctx.roundRect === 'function') {
                    ctx.roundRect(barX, noteTopY, barW, barH, 3.5);
                } else {
                    ctx.rect(barX, noteTopY, barW, barH);
                }
                ctx.fill();

                if (n.state === 'active') {
                    ctx.strokeStyle = hTheme.keyFill;
                    ctx.lineWidth = 2.0;
                    ctx.stroke();
                }
                ctx.restore();
            });

            // 4. Floating Chord Labels in Waterfall (collision-safe, non-obstructing)
            if (this.adapter) {
                const chords = this.adapter.getChords();
                let lastLabelY = Infinity;
                chords.forEach(c => {
                    const cStart = Number(c.startTime ?? c.time ?? 0);
                    const cEnd = Number(c.endTime ?? c.end ?? (cStart + 1.5));
                    if (cStart >= this.currentTime - 0.15 && cStart <= this.currentTime + this.lookAheadSec * 0.94) {
                        const cName = c.chordName || c.chord || '';
                        if (!cName || cName === 'N') return;

                        const y = Math.min(rollBottomY - 8, rollBottomY - Math.max(0, cStart - this.currentTime) * pixelsPerSec);
                        if (Math.abs(lastLabelY - y) < 22) return;
                        lastLabelY = y;

                        const bassK = this.keyMap[40] || this.keyMap[45] || { x: padX + 120 };
                        const isActive = this.currentTime >= cStart && this.currentTime < cEnd;
                        const isNearStrike = Math.abs(cStart - this.currentTime) < 0.25 || isActive;

                        ctx.save();
                        ctx.font = '700 11px -apple-system, BlinkMacSystemFont, sans-serif';
                        const textW = typeof ctx.measureText === 'function' ? ctx.measureText(cName).width : cName.length * 7;
                        const pillW = Math.max(30, textW + 14);
                        const pillH = 18;
                        const pillX = Math.max(padX + pillW / 2 + 6, bassK.x - pillW / 2 - 8);
                        const pillY = y - pillH;

                        ctx.fillStyle = isNearStrike ? '#F7F4EF' : 'rgba(18, 18, 22, 0.88)';
                        ctx.strokeStyle = isNearStrike ? '#F7F4EF' : 'rgba(255, 255, 255, 0.18)';
                        ctx.lineWidth = 1;
                        ctx.beginPath();
                        if (typeof ctx.roundRect === 'function') {
                            ctx.roundRect(pillX - pillW / 2, pillY, pillW, pillH, 5);
                        } else {
                            ctx.rect(pillX - pillW / 2, pillY, pillW, pillH);
                        }
                        ctx.fill();
                        if (!isNearStrike) ctx.stroke();

                        ctx.fillStyle = isNearStrike ? '#101012' : 'rgba(247, 244, 239, 0.92)';
                        ctx.textAlign = 'center';
                        ctx.fillText(cName, pillX, pillY + 12.5);
                        ctx.restore();
                    }
                });
            }

            ctx.restore();

            // 5. Separated 88-Key Realistic 2D Piano Keyboard Frame
            const activeByMidi = {};
            winState.activeNotes.forEach(n => { activeByMidi[n.midi] = n; });

            // Outer dark surround for keyboard
            ctx.fillStyle = '#0A0A0D';
            ctx.beginPath();
            if (typeof ctx.roundRect === 'function') {
                ctx.roundRect(padX - 2, kbTopY - 2, W - (padX - 2) * 2, kbH + 4, 10);
            } else {
                ctx.rect(padX - 2, kbTopY - 2, W - (padX - 2) * 2, kbH + 4);
            }
            ctx.fill();

            // White keys
            for (let midi = 21; midi <= 108; midi++) {
                const k = this.keyMap[midi];
                if (!k || k.isBlack) continue;
                const act = activeByMidi[midi];
                const hTheme = act
                    ? (this.showColourKey ? (HAND_ACTIVE_THEME[act.hand] || HAND_ACTIVE_THEME.right) : { keyFill: '#C8C4BC' })
                    : null;

                ctx.fillStyle = act ? hTheme.keyFill : '#EFECE6';
                ctx.beginPath();
                if (typeof ctx.roundRect === 'function') {
                    ctx.roundRect(k.x + 0.5, kbTopY, k.width - 1, kbH, [0, 0, 4, 4]);
                } else {
                    ctx.rect(k.x + 0.5, kbTopY, k.width - 1, kbH);
                }
                ctx.fill();

                ctx.strokeStyle = '#1C1C22';
                ctx.lineWidth = 0.7;
                ctx.stroke();

                // Circular Finger Badge on Active White Key
                if (act && act.finger) {
                    const badgeY = kbTopY + kbH - 13;
                    ctx.fillStyle = 'rgba(20, 20, 19, 0.82)';
                    ctx.beginPath();
                    ctx.arc(k.centerX, badgeY, 7, 0, Math.PI * 2);
                    ctx.fill();

                    ctx.fillStyle = '#FAF9F5';
                    ctx.font = '700 9px -apple-system, BlinkMacSystemFont, sans-serif';
                    ctx.textAlign = 'center';
                    ctx.fillText(String(act.finger), k.centerX, badgeY + 3);
                }
            }

            // Black keys
            const blackH = Math.round(kbH * 0.62);
            for (let midi = 21; midi <= 108; midi++) {
                const k = this.keyMap[midi];
                if (!k || !k.isBlack) continue;
                const act = activeByMidi[midi];
                const hTheme = act
                    ? (this.showColourKey ? (HAND_ACTIVE_THEME[act.hand] || HAND_ACTIVE_THEME.right) : { keyFill: '#52525E' })
                    : null;

                ctx.fillStyle = act ? hTheme.keyFill : '#18181D';
                ctx.beginPath();
                if (typeof ctx.roundRect === 'function') {
                    ctx.roundRect(k.x, kbTopY, k.width, blackH, [0, 0, 3, 3]);
                } else {
                    ctx.rect(k.x, kbTopY, k.width, blackH);
                }
                ctx.fill();

                ctx.strokeStyle = '#050507';
                ctx.lineWidth = 0.8;
                ctx.stroke();

                // Circular Finger Badge on Active Black Key
                if (act && act.finger) {
                    const badgeY = kbTopY + blackH - 10;
                    ctx.fillStyle = 'rgba(250, 249, 245, 0.92)';
                    ctx.beginPath();
                    ctx.arc(k.centerX, badgeY, 6, 0, Math.PI * 2);
                    ctx.fill();

                    ctx.fillStyle = '#141413';
                    ctx.font = '700 8.5px -apple-system, BlinkMacSystemFont, sans-serif';
                    ctx.textAlign = 'center';
                    ctx.fillText(String(act.finger), k.centerX, badgeY + 3);
                }
            }

            return winState;
        }
    }

    global.PianoStudio2D = PianoStudio2D;
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = { PianoStudio2D };
    }
})(typeof window !== 'undefined' ? window : global);
