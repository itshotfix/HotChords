/**
 * handDiagrams.js
 *
 * Anatomically Proportional Realistic SVG Hand Diagrams for HotChords.
 * Standards: HotChords UI/UX & Animation Engineering Skills (Phase 3).
 *
 * Geometric Architecture:
 * - Left Hand (LH): Mirrored with Thumb on Right, Pinky on Left.
 * - Right Hand (RH): Thumb on Left, Pinky on Right.
 * - Proportional 24-28px finger widths in 200x230 viewBox.
 * - Calibrated 19-20px finger pad dots safely enclosed within finger silhouettes with zero protrusion.
 * - Upright, non-flipped typography on all finger numbers.
 */

(function(global) {
    'use strict';

    function getRightHandMarkup() {
        return `
        <svg viewBox="0 0 200 230" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" class="hand-svg" aria-label="Right Hand Diagram">
            <!-- Wrist and Palm Body -->
            <g class="hand-body" fill="none" stroke="#D2D2D7" stroke-width="2">
                <path d="M 56 210 C 56 224 144 224 144 210 L 158 140 C 172 100 148 76 128 76 L 72 76 C 52 76 28 100 42 140 Z" fill="#FAFAFA" stroke="#D2D2D7" />
            </g>

            <!-- Finger 1 (Thumb) -->
            <g id="rh-finger-1" class="hand-finger" style="transform-origin: 48px 120px; will-change: transform;">
                <path d="M 56 138 C 28 138 16 116 22 94 L 32 70 C 38 58 58 64 52 88 Z" fill="#FFFFFF" stroke="#D2D2D7" stroke-width="1.5" />
                <circle id="rh-finger-dot-1" cx="36" cy="86" r="10" fill="#E5E5EA" stroke="#D2D2D7" stroke-width="1.5" />
                <text id="rh-finger-num-1" class="hand-finger-num" x="36" y="90" text-anchor="middle" font-size="11" font-weight="800" fill="#1D1D1F" opacity="0.35">1</text>
            </g>

            <!-- Finger 2 (Index) -->
            <g id="rh-finger-2" class="hand-finger" style="transform-origin: 69px 76px; will-change: transform;">
                <path d="M 56 76 L 56 22 C 56 10 82 10 82 22 L 82 76 Z" fill="#FFFFFF" stroke="#D2D2D7" stroke-width="1.5" />
                <circle id="rh-finger-dot-2" cx="69" cy="34" r="10" fill="#E5E5EA" stroke="#D2D2D7" stroke-width="1.5" />
                <text id="rh-finger-num-2" class="hand-finger-num" x="69" y="38" text-anchor="middle" font-size="11" font-weight="800" fill="#1D1D1F" opacity="0.35">2</text>
            </g>

            <!-- Finger 3 (Middle) -->
            <g id="rh-finger-3" class="hand-finger" style="transform-origin: 98px 76px; will-change: transform;">
                <path d="M 85 76 L 85 14 C 85 2 111 2 111 14 L 111 76 Z" fill="#FFFFFF" stroke="#D2D2D7" stroke-width="1.5" />
                <circle id="rh-finger-dot-3" cx="98" cy="26" r="10" fill="#E5E5EA" stroke="#D2D2D7" stroke-width="1.5" />
                <text id="rh-finger-num-3" class="hand-finger-num" x="98" y="30" text-anchor="middle" font-size="11" font-weight="800" fill="#1D1D1F" opacity="0.35">3</text>
            </g>

            <!-- Finger 4 (Ring) -->
            <g id="rh-finger-4" class="hand-finger" style="transform-origin: 127px 76px; will-change: transform;">
                <path d="M 114 76 L 114 22 C 114 10 140 10 140 22 L 140 76 Z" fill="#FFFFFF" stroke="#D2D2D7" stroke-width="1.5" />
                <circle id="rh-finger-dot-4" cx="127" cy="34" r="10" fill="#E5E5EA" stroke="#D2D2D7" stroke-width="1.5" />
                <text id="rh-finger-num-4" class="hand-finger-num" x="127" y="38" text-anchor="middle" font-size="11" font-weight="800" fill="#1D1D1F" opacity="0.35">4</text>
            </g>

            <!-- Finger 5 (Pinky) -->
            <g id="rh-finger-5" class="hand-finger" style="transform-origin: 155px 86px; will-change: transform;">
                <path d="M 143 86 L 143 42 C 143 30 167 30 167 42 L 167 86 Z" fill="#FFFFFF" stroke="#D2D2D7" stroke-width="1.5" />
                <circle id="rh-finger-dot-5" cx="155" cy="52" r="9.5" fill="#E5E5EA" stroke="#D2D2D7" stroke-width="1.5" />
                <text id="rh-finger-num-5" class="hand-finger-num" x="155" y="56" text-anchor="middle" font-size="10.5" font-weight="800" fill="#1D1D1F" opacity="0.35">5</text>
            </g>
        </svg>`;
    }

    function getLeftHandMarkup() {
        return `
        <svg viewBox="0 0 200 230" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" class="hand-svg" aria-label="Left Hand Diagram">
            <!-- Wrist and Palm Body -->
            <g class="hand-body" fill="none" stroke="#D2D2D7" stroke-width="2">
                <path d="M 144 210 C 144 224 56 224 56 210 L 42 140 C 28 100 52 76 72 76 L 128 76 C 148 76 172 100 158 140 Z" fill="#FAFAFA" stroke="#D2D2D7" />
            </g>

            <!-- Finger 5 (Pinky on Left) -->
            <g id="lh-finger-5" class="hand-finger" style="transform-origin: 45px 86px; will-change: transform;">
                <path d="M 57 86 L 57 42 C 57 30 33 30 33 42 L 33 86 Z" fill="#FFFFFF" stroke="#D2D2D7" stroke-width="1.5" />
                <circle id="lh-finger-dot-5" cx="45" cy="52" r="9.5" fill="#E5E5EA" stroke="#D2D2D7" stroke-width="1.5" />
                <text id="lh-finger-num-5" class="hand-finger-num" x="45" y="56" text-anchor="middle" font-size="10.5" font-weight="800" fill="#1D1D1F" opacity="0.35">5</text>
            </g>

            <!-- Finger 4 (Ring) -->
            <g id="lh-finger-4" class="hand-finger" style="transform-origin: 73px 76px; will-change: transform;">
                <path d="M 86 76 L 86 22 C 86 10 60 10 60 22 L 60 76 Z" fill="#FFFFFF" stroke="#D2D2D7" stroke-width="1.5" />
                <circle id="lh-finger-dot-4" cx="73" cy="34" r="10" fill="#E5E5EA" stroke="#D2D2D7" stroke-width="1.5" />
                <text id="lh-finger-num-4" class="hand-finger-num" x="73" y="38" text-anchor="middle" font-size="11" font-weight="800" fill="#1D1D1F" opacity="0.35">4</text>
            </g>

            <!-- Finger 3 (Middle) -->
            <g id="lh-finger-3" class="hand-finger" style="transform-origin: 102px 76px; will-change: transform;">
                <path d="M 115 76 L 115 14 C 115 2 89 2 89 14 L 89 76 Z" fill="#FFFFFF" stroke="#D2D2D7" stroke-width="1.5" />
                <circle id="lh-finger-dot-3" cx="102" cy="26" r="10" fill="#E5E5EA" stroke="#D2D2D7" stroke-width="1.5" />
                <text id="lh-finger-num-3" class="hand-finger-num" x="102" y="30" text-anchor="middle" font-size="11" font-weight="800" fill="#1D1D1F" opacity="0.35">3</text>
            </g>

            <!-- Finger 2 (Index) -->
            <g id="lh-finger-2" class="hand-finger" style="transform-origin: 131px 76px; will-change: transform;">
                <path d="M 144 76 L 144 22 C 144 10 118 10 118 22 L 118 76 Z" fill="#FFFFFF" stroke="#D2D2D7" stroke-width="1.5" />
                <circle id="lh-finger-dot-2" cx="131" cy="34" r="10" fill="#E5E5EA" stroke="#D2D2D7" stroke-width="1.5" />
                <text id="lh-finger-num-2" class="hand-finger-num" x="131" y="38" text-anchor="middle" font-size="11" font-weight="800" fill="#1D1D1F" opacity="0.35">2</text>
            </g>

            <!-- Finger 1 (Thumb on Right) -->
            <g id="lh-finger-1" class="hand-finger" style="transform-origin: 152px 120px; will-change: transform;">
                <path d="M 144 138 C 172 138 184 116 178 94 L 168 70 C 162 58 142 64 148 88 Z" fill="#FFFFFF" stroke="#D2D2D7" stroke-width="1.5" />
                <circle id="lh-finger-dot-1" cx="164" cy="86" r="10" fill="#E5E5EA" stroke="#D2D2D7" stroke-width="1.5" />
                <text id="lh-finger-num-1" class="hand-finger-num" x="164" y="90" text-anchor="middle" font-size="11" font-weight="800" fill="#1D1D1F" opacity="0.35">1</text>
            </g>
        </svg>`;
    }

    const HandDiagrams = {
        getHandMarkup(handType) {
            return handType === 'LH' ? getLeftHandMarkup() : getRightHandMarkup();
        }
    };

    global.HandDiagrams = HandDiagrams;

    if (typeof module !== 'undefined' && module.exports) {
        module.exports = { HandDiagrams };
    }

})(typeof window !== 'undefined' ? window : (typeof global !== 'undefined' ? global : this));
