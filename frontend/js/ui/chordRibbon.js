/**
 * chordRibbon.js
 * 
 * Reusable Chord Ribbon Component for HotChords Phase 8.
 * Renders chord progressions using clean musical typography without box borders.
 * Synchronized with PlaybackClock without rebuilding the DOM on every tick.
 */

(function(global) {
    'use strict';

    class ChordRibbon {
        /**
         * Formats seconds into m:ss.
         * @param {number} s
         * @returns {string}
         */
        static formatTime(s) {
            if (typeof s !== 'number' || isNaN(s) || s < 0) return '0:00';
            const m = Math.floor(s / 60);
            const sec = Math.floor(s % 60);
            return `${m}:${sec.toString().padStart(2, '0')}`;
        }

        /**
         * Renders the chord ribbon into a container.
         * @param {HTMLElement} container - Target container element
         * @param {Array} chords - Array of ChordEvents (from SongTimeline.beginnerChords or originalChords)
         * @param {Object} options - { onSeek: (time) => void, compact: boolean }
         */
        static render(container, chords, options = {}) {
            if (!container) return;
            if (!Array.isArray(chords) || chords.length === 0) {
                container.innerHTML = `
                    <div class="chord-ribbon-empty">
                        <span class="ribbon-empty-text">No chord progression available</span>
                    </div>
                `;
                return;
            }

            const onSeek = typeof options.onSeek === 'function' ? options.onSeek : (t) => {
                if (global.PlaybackClock) global.PlaybackClock.seek(t);
            };

            global.__chordRibbonSeek = (time) => {
                onSeek(time);
            };

            let html = '<div class="chord-ribbon-flow" role="region" aria-label="Chord Progression Ribbon">';

            chords.forEach((c, idx) => {
                const start = c.startTime !== undefined ? c.startTime : (c.time || 0);
                const end = c.endTime !== undefined ? c.endTime : (c.end || start + 2);
                const name = c.chordName || c.chord || '—';
                const diff = c.difficulty || 'EASY';

                html += `
                    <span class="ribbon-chord-item beg-chord-cell" 
                          role="button" 
                          tabindex="0" 
                          data-idx="${idx}" 
                          data-start="${start}" 
                          data-end="${end}" 
                          aria-label="Chord ${name} at ${ChordRibbon.formatTime(start)}" 
                          onclick="window.__chordRibbonSeek(${start})"
                          onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();window.__chordRibbonSeek(${start});}">
                        <span class="ribbon-chord-name beg-chord-name">${name}</span>
                        <span class="ribbon-chord-meta">
                            <span class="ribbon-chord-time beg-chord-time">${ChordRibbon.formatTime(start)}</span>
                        </span>
                    </span>
                `;

                // Add musical measure bar every 4 chords or when spaced
                if ((idx + 1) % 4 === 0 && idx < chords.length - 1) {
                    html += `<span class="ribbon-measure-bar" aria-hidden="true">|</span>`;
                }
            });

            html += '</div>';
            container.innerHTML = html;
        }

        /**
         * Updates the active chord highlight in the ribbon based on currentTime.
         * Only modifies classes without rebuilding DOM.
         * @param {HTMLElement} container
         * @param {number} currentTime
         */
        static updateActive(container, currentTime) {
            if (!container) return;
            const items = container.querySelectorAll('.ribbon-chord-item');
            if (!items || items.length === 0) return;

            let activeItem = null;

            items.forEach(item => {
                const start = parseFloat(item.dataset.start);
                const end = parseFloat(item.dataset.end);
                const isActive = (currentTime >= start && currentTime < end);

                if (isActive) {
                    item.classList.add('active-chord', 'active-chord-cell');
                    activeItem = item;
                } else {
                    item.classList.remove('active-chord', 'active-chord-cell');
                }
            });

            // Smoothly keep the active chord in view within ribbon container
            if (activeItem && container.scrollWidth > container.clientWidth) {
                const containerRect = container.getBoundingClientRect();
                const itemRect = activeItem.getBoundingClientRect();
                if (itemRect.left < containerRect.left || itemRect.right > containerRect.right) {
                    activeItem.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
                }
            }
        }
    }

    global.ChordRibbon = ChordRibbon;
})(typeof window !== 'undefined' ? window : global);
