/**
 * handDiagrams.js
 * Realistic SVG hand diagrams V3 (Line-art style).
 * Fixed large size, visible palm, individual finger groups.
 */

const HandDiagrams = {
    getHandMarkup(handType) {
        const isRH = handType === 'RH';
        const prefix = isRH ? 'rh' : 'lh';
        
        // Larger, more realistic line-art style
        // 1=Thumb, 2=Index, 3=Middle, 4=Ring, 5=Pinky
        return `
        <svg viewBox="0 0 200 220" width="100%" height="auto" xmlns="http://www.w3.org/2000/svg" class="hand-svg" ${!isRH ? 'style="transform: scaleX(-1);"' : ''}>
            <g class="hand-body" fill="none" stroke="#D2D2D7" stroke-width="1.5">
                <!-- Wrist and Palm Outline -->
                <path d="M60,200 C60,215 140,215 140,200 L150,150 C165,110 140,80 120,80 L80,80 C60,80 35,110 50,150 Z" fill="#FFFFFF" />
                
                <!-- Finger 1 (Thumb) -->
                <g id="${prefix}-finger-1" class="hand-finger">
                    <path d="M55,140 C30,140 20,120 25,100 L35,80 C40,70 55,75 50,95 Z" fill="#FFFFFF" />
                    <circle id="${prefix}-finger-dot-1" cx="35" cy="98" r="12" fill="white" opacity="0" />
                    <text id="${prefix}-finger-num-1" class="hand-finger-num" x="35" y="103" text-anchor="middle" font-size="14" font-weight="800" fill="#1D1D1F" ${!isRH ? 'style="transform: scaleX(-1); transform-origin: 35px 103px;"' : ''}>1</text>
                </g>

                <!-- Finger 2 (Index) -->
                <g id="${prefix}-finger-2" class="hand-finger">
                    <path d="M62,80 L62,25 C62,15 82,15 82,25 L82,80" fill="#FFFFFF" />
                    <circle id="${prefix}-finger-dot-2" cx="72" cy="38" r="12" fill="white" opacity="0" />
                    <text id="${prefix}-finger-num-2" class="hand-finger-num" x="72" y="43" text-anchor="middle" font-size="14" font-weight="800" fill="#1D1D1F" ${!isRH ? 'style="transform: scaleX(-1); transform-origin: 72px 43px;"' : ''}>2</text>
                </g>

                <!-- Finger 3 (Middle) -->
                <g id="${prefix}-finger-3" class="hand-finger">
                    <path d="M85,80 L85,15 C85,5 105,5 105,15 L105,80" fill="#FFFFFF" />
                    <circle id="${prefix}-finger-dot-3" cx="95" cy="28" r="12" fill="white" opacity="0" />
                    <text id="${prefix}-finger-num-3" class="hand-finger-num" x="95" y="33" text-anchor="middle" font-size="14" font-weight="800" fill="#1D1D1F" ${!isRH ? 'style="transform: scaleX(-1); transform-origin: 95px 33px;"' : ''}>3</text>
                </g>

                <!-- Finger 4 (Ring) -->
                <g id="${prefix}-finger-4" class="hand-finger">
                    <path d="M108,80 L108,25 C108,15 128,15 128,25 L128,80" fill="#FFFFFF" />
                    <circle id="${prefix}-finger-dot-4" cx="118" cy="38" r="12" fill="white" opacity="0" />
                    <text id="${prefix}-finger-num-4" class="hand-finger-num" x="118" y="43" text-anchor="middle" font-size="14" font-weight="800" fill="#1D1D1F" ${!isRH ? 'style="transform: scaleX(-1); transform-origin: 118px 43px;"' : ''}>4</text>
                </g>

                <!-- Finger 5 (Pinky) -->
                <g id="${prefix}-finger-5" class="hand-finger">
                    <path d="M131,90 L131,45 C131,35 147,35 147,45 L147,90" fill="#FFFFFF" />
                    <circle id="${prefix}-finger-dot-5" cx="139" cy="55" r="11" fill="white" opacity="0" />
                    <text id="${prefix}-finger-num-5" class="hand-finger-num" x="139" y="60" text-anchor="middle" font-size="13" font-weight="800" fill="#1D1D1F" ${!isRH ? 'style="transform: scaleX(-1); transform-origin: 139px 60px;"' : ''}>5</text>
                </g>
            </g>
        </svg>`;
    }
};

window.HandDiagrams = HandDiagrams;
