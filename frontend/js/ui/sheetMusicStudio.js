/**
 * sheetMusicStudio.js
 *
 * HotChords Multi-System Grand Staff Sheet Music Studio.
 *
 * Visual & Behavioral Specification:
 * - Warm Parchment Sheet Page (#FAF8F5) with rounded corners over obsidian (#101012).
 * - Editorial Header: Song Title in Serif, "Key · ♩ = BPM" subtitle, and
 *   "Piano arrangement by HotChords" italic credit.
 * - Multi-System Engraving (4 measures per system row, multiple systems stacked vertically):
 *     * Classic Grand Staff brace, Treble G-clef (𝄞), Bass F-clef (𝄢), Key Signature & Time Signature.
 *     * Engraved quarter, half, whole, and beamed 8th/16th notes, rests, ties, and ledger lines.
 *     * Sweeping Coral-Magenta vertical playhead line (#FF477E -> #B14BFF) synchronized to PlaybackClock.
 *     * Automatic vertical system scrolling + click-on-measure to seek.
 */

(function(global) {
    'use strict';

    const PC_TO_DIATONIC = [0, 0, 1, 1, 2, 3, 3, 4, 4, 5, 5, 6];
    const SHARP_PCS = new Set([1, 3, 6, 8, 10]);

    function midiToDiatonicStep(midi) {
        const m = Math.max(21, Math.min(108, Math.round(midi)));
        const octave = Math.floor(m / 12) - 1;
        const pc = ((m % 12) + 12) % 12;
        return octave * 7 + PC_TO_DIATONIC[pc];
    }

    class SheetMusicStudio {
        constructor(containerEl, options = {}) {
            this.container = typeof containerEl === 'string'
                ? (typeof document !== 'undefined' ? document.getElementById(containerEl) : null)
                : containerEl;
            this.adapter = options.adapter || global.StudioTimelineAdapter;
            this.onSeek = options.onSeek || (t => {
                if (global.PlaybackClock) global.PlaybackClock.seek(t);
            });
            this.measuresPerSystem = 4;
            this.canvas = null;
            this.ctx = null;
            this.width = 0;
            this.height = 0;
            this.currentTime = 0;
            this._systemHitBoxes = [];

            if (this.container) {
                this._initDOM();
            }
        }

        _initDOM() {
            if (!this.container || typeof document === 'undefined') return;
            this.container.innerHTML = '';
            this.canvas = document.createElement('canvas');
            this.canvas.className = 'sheet-music-studio-canvas';
            if (this.canvas.style) {
                this.canvas.style.width = '100%';
                this.canvas.style.height = '100%';
                this.canvas.style.display = 'block';
                this.canvas.style.cursor = 'pointer';
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
            this.render(this.currentTime);
        }

        _handleCanvasClick(e) {
            if (!this.canvas || !this._systemHitBoxes || this._systemHitBoxes.length === 0) return;
            const rect = this.canvas.getBoundingClientRect ? this.canvas.getBoundingClientRect() : { left: 0, top: 0 };
            const x = (e.clientX || 0) - rect.left;
            const y = (e.clientY || 0) - rect.top;

            for (const box of this._systemHitBoxes) {
                if (x >= box.x0 && x <= box.x1 && y >= box.y0 && y <= box.y1) {
                    const ratio = Math.max(0, Math.min(1, (x - box.x0) / Math.max(1, box.x1 - box.x0)));
                    const targetTime = box.startTime + ratio * (box.endTime - box.startTime);
                    if (this.onSeek) this.onSeek(targetTime);
                    return;
                }
            }
        }

        _midiToStaffY(midi, isTreble, bottomLineY, lineSpacing) {
            const step = midiToDiatonicStep(midi);
            const refStep = isTreble ? midiToDiatonicStep(64) : midiToDiatonicStep(43);
            const halfSpace = lineSpacing / 2;
            return bottomLineY - (step - refStep) * halfSpace;
        }

        render(currentTime = 0) {
            this.currentTime = Math.max(0, Number(currentTime) || 0);
            const mBundle = this.adapter ? this.adapter.getMeasures() : {
                tempo: 120,
                timeSig: '4/4',
                beatsPerBar: 4,
                measureDuration: 2.0,
                measures: []
            };
            this.lastMeasureData = mBundle;

            const measures = mBundle.measures || [];
            const activeMeasure = measures.find(
                m => this.currentTime >= m.startTime && this.currentTime < m.endTime
            ) || measures[0] || { index: 1, startTime: 0, endTime: 2.0, chords: [], trebleNotes: [], bassNotes: [] };

            this.lastRenderedState = {
                currentTime: this.currentTime,
                activeMeasureIndex: activeMeasure.index,
                totalMeasures: measures.length,
                timeSignature: mBundle.timeSig
            };

            const ctx = this.ctx;
            if (!ctx) return this.lastRenderedState;

            const W = this.width || 1040;
            const H = this.height || 520;
            const pageMarginX = Math.max(18, Math.round(W * 0.032));
            const pageW = W - pageMarginX * 2;

            // 1. Dark Studio Background + Warm Parchment Sheet Page (#FAF8F5)
            ctx.fillStyle = '#101012';
            ctx.fillRect(0, 0, W, H);

            ctx.fillStyle = '#FAF8F5';
            ctx.beginPath();
            if (typeof ctx.roundRect === 'function') {
                ctx.roundRect(pageMarginX, 4, pageW, H - 8, 14);
            } else {
                ctx.rect(pageMarginX, 4, pageW, H - 8);
            }
            ctx.fill();

            // 2. Group measures into systems of 4 measures each
            const mPerSys = this.measuresPerSystem;
            const totalSystems = Math.max(1, Math.ceil(measures.length / mPerSys));
            const activeSystemIdx = Math.floor((activeMeasure.index - 1) / mPerSys);

            // Auto-scroll page window so active system is centered/visible among 3 visible systems
            const firstVisibleSys = Math.max(0, Math.min( Math.max(0, totalSystems - 3), activeSystemIdx - (activeSystemIdx > 0 ? 1 : 0) ));
            const visibleSysCount = Math.min(3, totalSystems - firstVisibleSys);

            let cursorY = 20;
            // Show title banner when on top system
            if (firstVisibleSys === 0 && H >= 360) {
                const tl = this.adapter && this.adapter.timeline;
                const rawTitle = (tl && tl.metadata && (tl.metadata.file || tl.metadata.title)) || 'Piano Arrangement';
                const cleanTitle = String(rawTitle).replace(/\.[^.]+$/, '');
                const keyFull = (tl && tl.metadata && tl.metadata.key_full) || 'C major';
                const bpm = Math.round(mBundle.tempo || 120);

                ctx.fillStyle = '#141413';
                ctx.font = '400 24px "Instrument Serif", Georgia, serif';
                ctx.textAlign = 'center';
                ctx.fillText(cleanTitle.slice(0, 48), W / 2, cursorY + 20);

                ctx.fillStyle = '#6A6A72';
                ctx.font = '500 12px -apple-system, BlinkMacSystemFont, sans-serif';
                ctx.fillText(`${keyFull} · ♩ = ${bpm}`, W / 2, cursorY + 40);

                ctx.font = 'italic 11.5px Georgia, serif';
                ctx.textAlign = 'right';
                ctx.fillText('Piano arrangement by HotChords', pageMarginX + pageW - 36, cursorY + 54);
                cursorY += 68;
            } else {
                cursorY += 18;
            }

            const availH = H - cursorY - 16;
            const sysBlockH = Math.max(115, Math.floor(availH / Math.max(1, visibleSysCount)));
            const lineSpacing = Math.max(6.5, Math.min(9.0, Math.floor(sysBlockH * 0.068)));
            const staffH = lineSpacing * 4;
            const staffGap = Math.max(24, Math.floor(sysBlockH * 0.22));

            const innerLeftX = pageMarginX + 42;
            const innerRightX = pageMarginX + pageW - 32;
            const clefHeaderW = 58;
            const measuresAreaW = Math.max(200, innerRightX - (innerLeftX + clefHeaderW));

            this._systemHitBoxes = [];

            for (let sOffset = 0; sOffset < visibleSysCount; sOffset++) {
                const sysIdx = firstVisibleSys + sOffset;
                const sysMeasures = measures.slice(sysIdx * mPerSys, (sysIdx + 1) * mPerSys);
                if (sysMeasures.length === 0) continue;

                const trebleTopY = cursorY + sOffset * sysBlockH + 14;
                const trebleBottomY = trebleTopY + staffH;
                const bassTopY = trebleBottomY + staffGap;
                const bassBottomY = bassTopY + staffH;

                // Measure number at top-left of system
                ctx.fillStyle = '#3A3A40';
                ctx.font = 'italic 11px Georgia, serif';
                ctx.textAlign = 'left';
                ctx.fillText(String(sysMeasures[0].index), innerLeftX, trebleTopY - 6);

                // Draw 5 Treble & 5 Bass staff lines across system
                ctx.strokeStyle = 'rgba(20, 20, 19, 0.52)';
                ctx.lineWidth = 0.85;
                for (let l = 0; l < 5; l++) {
                    const ty = trebleTopY + l * lineSpacing;
                    ctx.beginPath();
                    ctx.moveTo(innerLeftX, ty);
                    ctx.lineTo(innerRightX, ty);
                    ctx.stroke();

                    const by = bassTopY + l * lineSpacing;
                    ctx.beginPath();
                    ctx.moveTo(innerLeftX, by);
                    ctx.lineTo(innerRightX, by);
                    ctx.stroke();
                }

                // System left vertical connector & curly brace
                ctx.strokeStyle = '#141413';
                ctx.lineWidth = 1.6;
                ctx.beginPath();
                ctx.moveTo(innerLeftX, trebleTopY);
                ctx.lineTo(innerLeftX, bassBottomY);
                ctx.stroke();

                const midBraceY = (trebleTopY + bassBottomY) * 0.5;
                ctx.lineWidth = 1.8;
                ctx.beginPath();
                ctx.moveTo(innerLeftX - 2, trebleTopY);
                ctx.quadraticCurveTo(innerLeftX - 10, trebleTopY + (midBraceY - trebleTopY) * 0.5, innerLeftX - 8, midBraceY);
                ctx.quadraticCurveTo(innerLeftX - 10, bassBottomY - (bassBottomY - midBraceY) * 0.5, innerLeftX - 2, bassBottomY);
                ctx.stroke();

                // Clefs & Time Signature
                ctx.fillStyle = '#141413';
                ctx.font = `${Math.round(staffH * 1.15)}px Georgia, serif`;
                ctx.textAlign = 'center';
                ctx.fillText('𝄞', innerLeftX + 18, trebleBottomY - lineSpacing * 0.6);
                ctx.font = `${Math.round(staffH * 0.95)}px Georgia, serif`;
                ctx.fillText('𝄢', innerLeftX + 18, bassBottomY - lineSpacing * 0.9);

                // Key signature accidentals (#)
                ctx.font = `700 ${Math.round(lineSpacing * 1.4)}px Georgia, serif`;
                ctx.fillText('♯', innerLeftX + 34, trebleTopY + lineSpacing * 0.8);
                ctx.fillText('♯', innerLeftX + 41, trebleTopY + lineSpacing * 2.3);
                ctx.fillText('♯', innerLeftX + 34, bassTopY + lineSpacing * 1.3);
                ctx.fillText('♯', innerLeftX + 41, bassTopY + lineSpacing * 2.8);

                if (sysIdx === 0) {
                    const tsParts = String(mBundle.timeSig || '4/4').split('/');
                    ctx.font = `800 ${Math.round(lineSpacing * 1.9)}px Georgia, serif`;
                    ctx.fillText(tsParts[0] || '4', innerLeftX + 51, trebleTopY + lineSpacing * 1.85);
                    ctx.fillText(tsParts[1] || '4', innerLeftX + 51, trebleTopY + lineSpacing * 3.75);
                    ctx.fillText(tsParts[0] || '4', innerLeftX + 51, bassTopY + lineSpacing * 1.85);
                    ctx.fillText(tsParts[1] || '4', innerLeftX + 51, bassTopY + lineSpacing * 3.75);
                }

                // Render individual measures in this system
                const mWidth = measuresAreaW / sysMeasures.length;
                sysMeasures.forEach((m, mSlot) => {
                    const mx0 = innerLeftX + clefHeaderW + mSlot * mWidth;
                    const mx1 = mx0 + mWidth;

                    this._systemHitBoxes.push({
                        x0: mx0,
                        x1: mx1,
                        y0: trebleTopY - 12,
                        y1: bassBottomY + 12,
                        startTime: m.startTime,
                        endTime: m.endTime
                    });

                    // End barline of measure
                    ctx.strokeStyle = '#141413';
                    ctx.lineWidth = 1.1;
                    ctx.beginPath();
                    ctx.moveTo(mx1, trebleTopY);
                    ctx.lineTo(mx1, bassBottomY);
                    ctx.stroke();

                    // Chord symbols above measure
                    (m.chords || []).slice(0, 2).forEach((c, cIdx) => {
                        const cName = c.chordName || c.chord || '';
                        if (cName && cName !== 'N') {
                            ctx.fillStyle = '#2B2B30';
                            ctx.font = '700 11px -apple-system, BlinkMacSystemFont, sans-serif';
                            ctx.textAlign = 'left';
                            ctx.fillText(cName, mx0 + 8 + cIdx * (mWidth * 0.48), trebleTopY - 7);
                        }
                    });

                    // Render Treble & Bass notes (or whole-measure rest if empty)
                    this._renderMeasureVoice(ctx, m.trebleNotes, m, true, mx0, mx1, trebleTopY, trebleBottomY, lineSpacing);
                    this._renderMeasureVoice(ctx, m.bassNotes, m, false, mx0, mx1, bassTopY, bassBottomY, lineSpacing);

                    // Sweeping Coral-Violet Vertical Playhead Line if playback is inside this measure
                    if (this.currentTime >= m.startTime && this.currentTime < m.endTime) {
                        const progress = (this.currentTime - m.startTime) / Math.max(0.1, m.endTime - m.startTime);
                        const px = mx0 + 10 + progress * (mWidth - 18);

                        ctx.save();
                        ctx.strokeStyle = '#FF477E';
                        ctx.lineWidth = 2.0;
                        ctx.beginPath();
                        ctx.moveTo(px, trebleTopY - 8);
                        ctx.lineTo(px, bassBottomY + 8);
                        ctx.stroke();
                        ctx.restore();
                    }
                });
            }

            return this.lastRenderedState;
        }

        _renderMeasureVoice(ctx, notes, measure, isTreble, mx0, mx1, staffTopY, staffBottomY, lineSpacing) {
            const innerW = Math.max(40, (mx1 - mx0) - 24);
            const startX = mx0 + 14;

            if (!notes || notes.length === 0) {
                // Draw whole/half bar rest rectangle in middle of measure
                ctx.fillStyle = '#141413';
                ctx.fillRect((mx0 + mx1) * 0.5 - 5, staffTopY + lineSpacing * 1.1, 10, lineSpacing * 0.55);
                return;
            }

            // Group simultaneous chord notes within this measure
            const clusters = [];
            notes.forEach(n => {
                if (!clusters.length || Math.abs(n.start - clusters[clusters.length - 1][0].start) > 0.05) {
                    clusters.push([n]);
                } else {
                    clusters[clusters.length - 1].push(n);
                }
            });

            const mDur = Math.max(0.2, measure.endTime - measure.startTime);
            const stemTips = [];

            clusters.forEach((cl, cIdx) => {
                const n0 = cl[0];
                const relRatio = Math.max(0, Math.min(0.92, (n0.start - measure.startTime) / mDur));
                const nx = startX + relRatio * innerW;
                const isActive = (this.currentTime >= n0.start && this.currentTime < n0.end);
                const isHalfOrWhole = (n0.duration >= mDur * 0.42);
                const isEighthOrShorter = (n0.duration <= mDur * 0.18);

                let minY = 9999;
                let maxY = -9999;

                cl.forEach(n => {
                    const ny = this._midiToStaffY(n.midi, isTreble, staffBottomY, lineSpacing);
                    if (ny < minY) minY = ny;
                    if (ny > maxY) maxY = ny;

                    // Ledger lines
                    if (ny >= staffBottomY + lineSpacing * 0.85) {
                        ctx.strokeStyle = '#141413';
                        ctx.lineWidth = 1.0;
                        ctx.beginPath();
                        ctx.moveTo(nx - 7, staffBottomY + lineSpacing);
                        ctx.lineTo(nx + 7, staffBottomY + lineSpacing);
                        ctx.stroke();
                    } else if (ny <= staffTopY - lineSpacing * 0.85) {
                        ctx.strokeStyle = '#141413';
                        ctx.lineWidth = 1.0;
                        ctx.beginPath();
                        ctx.moveTo(nx - 7, staffTopY - lineSpacing);
                        ctx.lineTo(nx + 7, staffTopY - lineSpacing);
                        ctx.stroke();
                    }

                    // Notehead (hollow for half/whole, filled for quarter/8th)
                    ctx.save();
                    ctx.fillStyle = isActive ? '#FF477E' : '#141413';
                    ctx.strokeStyle = isActive ? '#FF477E' : '#141413';
                    ctx.lineWidth = 1.3;
                    ctx.beginPath();
                    if (typeof ctx.ellipse === 'function') {
                        ctx.ellipse(nx, ny, 4.4, 3.1, -0.28, 0, Math.PI * 2);
                    } else {
                        ctx.arc(nx, ny, 3.6, 0, Math.PI * 2);
                    }
                    if (isHalfOrWhole) {
                        ctx.stroke();
                    } else {
                        ctx.fill();
                    }
                    ctx.restore();
                });

                // Draw vertical stem
                const stemUp = isTreble ? (minY > staffTopY + lineSpacing * 1.5) : (maxY > staffTopY + lineSpacing * 2.2);
                const stemX = stemUp ? (nx + 3.8) : (nx - 3.8);
                const stemStartY = stemUp ? maxY : minY;
                const stemEndY = stemUp ? (minY - lineSpacing * 2.7) : (maxY + lineSpacing * 2.7);

                ctx.strokeStyle = isActive ? '#FF477E' : '#141413';
                ctx.lineWidth = 1.15;
                ctx.beginPath();
                ctx.moveTo(stemX, stemStartY);
                ctx.lineTo(stemX, stemEndY);
                ctx.stroke();

                stemTips.push({
                    x: stemX,
                    y: stemEndY,
                    stemUp,
                    isEighth: isEighthOrShorter,
                    noteX: nx,
                    noteY: minY
                });

                // Tie / slur arc on sustained notes
                if (isHalfOrWhole && cIdx + 1 < clusters.length) {
                    const nextX = startX + Math.min(0.92, (clusters[cIdx + 1][0].start - measure.startTime) / mDur) * innerW;
                    if (nextX - nx > 12) {
                        ctx.strokeStyle = '#141413';
                        ctx.lineWidth = 1.1;
                        ctx.beginPath();
                        ctx.moveTo(nx + 5, maxY + 4);
                        ctx.quadraticCurveTo((nx + nextX) * 0.5, maxY + 11, nextX - 5, maxY + 4);
                        ctx.stroke();
                    }
                }
            });

            // Draw beams connecting adjacent eighth-note pairs
            for (let i = 0; i < stemTips.length - 1; i += 2) {
                const a = stemTips[i];
                const b = stemTips[i + 1];
                if (a.isEighth && b.isEighth && a.stemUp === b.stemUp && Math.abs(b.x - a.x) < innerW * 0.42) {
                    ctx.strokeStyle = '#141413';
                    ctx.lineWidth = 2.8;
                    ctx.beginPath();
                    ctx.moveTo(a.x, a.y);
                    ctx.lineTo(b.x, b.y);
                    ctx.stroke();
                }
            }
        }
    }

    global.SheetMusicStudio = SheetMusicStudio;
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = { SheetMusicStudio, midiToDiatonicStep };
    }
})(typeof window !== 'undefined' ? window : global);
