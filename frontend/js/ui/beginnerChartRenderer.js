/**
 * beginnerChartRenderer.js
 * 
 * Production Beginner Chart Renderer for HotChords.
 * Renders a clean, structured musical chord progression chart from SongTimeline.beginner_chords.
 * 
 * Features:
 * - 100% text and musical chord notation only (NO hand diagrams or fingering images).
 * - Deterministic repetition detection for repeating chord loops (e.g., 4-chord pop loops).
 * - Real-time active chord highlighting synchronized with PlaybackClock.currentTime.
 * - Click-to-seek interaction via PlaybackClock.seek().
 * - Clean responsive vertical layout with measure bars.
 */

(function(global) {
    'use strict';

    class BeginnerChartRenderer {
        /**
         * Detects repeating chord sequences deterministically.
         * Looks for consecutive repeating patterns of length 2 to 8 chords.
         * @param {Array} chords - Array of ChordEvents from SongTimeline.beginner_chords
         * @returns {Array} List of block items (either single chord or repeating progression block)
         */
        static detectRepetitions(chords) {
            if (!Array.isArray(chords) || chords.length === 0) return [];
            
            const blocks = [];
            let i = 0;
            const n = chords.length;

            while (i < n) {
                let bestPatternLen = 0;
                let bestRepeats = 1;

                // Test pattern lengths from 2 to 8 chords
                for (let len = 2; len <= Math.min(8, Math.floor((n - i) / 2)); len++) {
                    const pattern = chords.slice(i, i + len).map(c => c.chordName || c.chord);
                    let repeats = 1;

                    while (i + (repeats + 1) * len <= n) {
                        const nextSlice = chords.slice(i + repeats * len, i + (repeats + 1) * len).map(c => c.chordName || c.chord);
                        if (pattern.every((val, idx) => val === nextSlice[idx])) {
                            repeats++;
                        } else {
                            break;
                        }
                    }

                    if (repeats >= 2 && (repeats * len) > (bestRepeats * bestPatternLen)) {
                        bestPatternLen = len;
                        bestRepeats = repeats;
                    }
                }

                if (bestRepeats >= 2 && bestPatternLen >= 2) {
                    const totalEvents = bestRepeats * bestPatternLen;
                    const blockEvents = chords.slice(i, i + totalEvents);
                    const patternChords = chords.slice(i, i + bestPatternLen);
                    
                    blocks.push({
                        type: 'repeated_block',
                        pattern: patternChords,
                        patternNames: patternChords.map(c => c.chordName || c.chord),
                        repeats: bestRepeats,
                        events: blockEvents,
                        startTime: blockEvents[0].startTime !== undefined ? blockEvents[0].startTime : blockEvents[0].time,
                        endTime: blockEvents[blockEvents.length - 1].endTime !== undefined ? blockEvents[blockEvents.length - 1].endTime : blockEvents[blockEvents.length - 1].end
                    });
                    i += totalEvents;
                } else {
                    blocks.push({
                        type: 'single_chord',
                        event: chords[i],
                        globalIndex: i
                    });
                    i++;
                }
            }

            return blocks;
        }

        /**
         * Renders the complete Beginner Chart into a container element.
         * @param {HTMLElement} container
         * @param {Array} beginnerChords
         * @param {Object} options
         */
        static render(container, beginnerChords, options = {}) {
            if (!container) return;
            if (!Array.isArray(beginnerChords) || beginnerChords.length === 0) {
                container.innerHTML = `
                    <div class="beg-chart-empty">
                        <p>No beginner chords available for this song.</p>
                    </div>
                `;
                return;
            }

            const onSeek = options.onSeek || ((t) => {
                if (global.PlaybackClock) global.PlaybackClock.seek(t);
            });

            const blocks = BeginnerChartRenderer.detectRepetitions(beginnerChords);
            let html = '<div class="beg-chart-container">';
            let globalEventIndex = 0;

            blocks.forEach((block, blockIdx) => {
                if (block.type === 'repeated_block') {
                    html += `
                        <div class="beg-prog-card">
                            <div class="beg-prog-header">
                                <span class="beg-prog-title">Progression Loop</span>
                                <span class="beg-repeat-badge">Repeat ×${block.repeats}</span>
                                <span class="beg-prog-time">${BeginnerChartRenderer.fmtTime(block.startTime)} - ${BeginnerChartRenderer.fmtTime(block.endTime)}</span>
                            </div>
                            <div class="beg-chord-grid">
                    `;

                    block.events.forEach((c) => {
                        const start = c.startTime !== undefined ? c.startTime : c.time;
                        const end = c.endTime !== undefined ? c.endTime : c.end;
                        const name = c.chordName || c.chord;
                        const diff = c.difficulty || 'EASY';

                        html += `
                            <div class="beg-chord-cell" role="button" tabindex="0" aria-label="Chord ${name}, starting at ${BeginnerChartRenderer.fmtTime(start)}" data-idx="${globalEventIndex}" data-start="${start}" data-end="${end}" onclick="window.__begChartSeek(${start})" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();window.__begChartSeek(${start});}">
                                <div class="beg-chord-name">${name}</div>
                                <div class="beg-chord-time">${BeginnerChartRenderer.fmtTime(start)}</div>
                                <div class="beg-chord-diff ${diff.toLowerCase()}">${diff}</div>
                            </div>
                        `;
                        globalEventIndex++;
                    });

                    html += `
                            </div>
                        </div>
                    `;
                } else {
                    const c = block.event;
                    const start = c.startTime !== undefined ? c.startTime : c.time;
                    const end = c.endTime !== undefined ? c.endTime : c.end;
                    const name = c.chordName || c.chord;
                    const diff = c.difficulty || 'EASY';

                    html += `
                        <div class="beg-single-row">
                            <div class="beg-chord-cell" role="button" tabindex="0" aria-label="Chord ${name}, from ${BeginnerChartRenderer.fmtTime(start)} to ${BeginnerChartRenderer.fmtTime(end)}" data-idx="${globalEventIndex}" data-start="${start}" data-end="${end}" onclick="window.__begChartSeek(${start})" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();window.__begChartSeek(${start});}">
                                <div class="beg-chord-name">${name}</div>
                                <div class="beg-chord-time">${BeginnerChartRenderer.fmtTime(start)} - ${BeginnerChartRenderer.fmtTime(end)}</div>
                                <div class="beg-chord-diff ${diff.toLowerCase()}">${diff}</div>
                            </div>
                        </div>
                    `;
                    globalEventIndex++;
                }
            });

            html += '</div>';
            container.innerHTML = html;

            // Global seek hook
            global.__begChartSeek = onSeek;
        }

        /**
         * Highlights the currently active chord cell according to PlaybackClock.currentTime.
         * @param {HTMLElement} container
         * @param {number} currentTime
         */
        static updateActive(container, currentTime) {
            if (!container) return;
            const cells = container.querySelectorAll('.beg-chord-cell');
            if (!cells || cells.length === 0) return;

            let activeCell = null;
            cells.forEach(cell => {
                const start = parseFloat(cell.getAttribute('data-start'));
                const end = parseFloat(cell.getAttribute('data-end'));

                if (currentTime >= start && currentTime < end) {
                    cell.classList.add('active-chord-cell');
                    activeCell = cell;
                } else {
                    cell.classList.remove('active-chord-cell');
                }
            });

            // Smoothly auto-scroll container to active cell if playing
            if (activeCell && container.offsetParent !== null) {
                activeCell.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
            }
        }

        static fmtTime(s) {
            const m = Math.floor(s / 60);
            const sec = Math.floor(s % 60);
            return `${m}:${sec.toString().padStart(2, '0')}`;
        }
    }

    // Export class & singleton for Browser and Node
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = { BeginnerChartRenderer };
    }
    if (typeof window !== 'undefined') {
        window.BeginnerChartRenderer = BeginnerChartRenderer;
    }
    if (typeof global !== 'undefined') {
        global.BeginnerChartRenderer = BeginnerChartRenderer;
    }

})(typeof globalThis !== 'undefined' ? globalThis : (typeof window !== 'undefined' ? window : this));
