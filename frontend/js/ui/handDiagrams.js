/**
 * handDiagrams.js
 * Realistic SVG hand diagrams (Line-art + Animated Finger Pads).
 * Large size, visible palm, individual finger groups with glowing active dots.
 */

const HandDiagrams = {
    getHandMarkup(handType) {
        const isRH = handType === 'RH';
        const prefix = isRH ? 'rh' : 'lh';
        
        // 1=Thumb, 2=Index, 3=Middle, 4=Ring, 5=Pinky
        return `
        <svg viewBox="0 0 200 220" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" class="hand-svg" ${!isRH ? 'style="transform: scaleX(-1);"' : ''}>
            <!-- Wrist and Palm Outline -->
            <g class="hand-body" fill="none" stroke="#D2D2D7" stroke-width="2">
                <path d="M60,200 C60,215 140,215 140,200 L150,140 C165,100 140,75 120,75 L80,75 C60,75 35,100 50,140 Z" fill="#FAFAFA" stroke="#D2D2D7" />
                
                <!-- Finger 1 (Thumb) -->
                <g id="${prefix}-finger-1" class="hand-finger" style="transition: transform 0.15s ease, fill 0.15s ease;">
                    <path d="M55,135 C30,135 20,115 25,95 L35,75 C40,65 55,70 50,90 Z" fill="#FFFFFF" stroke="#D2D2D7" />
                    <circle id="${prefix}-finger-dot-1" cx="35" cy="90" r="14" fill="#E5E5EA" stroke="#D2D2D7" stroke-width="1.5" />
                    <text id="${prefix}-finger-num-1" class="hand-finger-num" x="35" y="95" text-anchor="middle" font-size="14" font-weight="800" fill="#1D1D1F" ${!isRH ? 'style="transform: scaleX(-1); transform-origin: 35px 95px;"' : ''}>1</text>
                </g>

                <!-- Finger 2 (Index) -->
                <g id="${prefix}-finger-2" class="hand-finger" style="transition: transform 0.15s ease, fill 0.15s ease;">
                    <path d="M60,75 L60,22 C60,12 82,12 82,22 L82,75" fill="#FFFFFF" stroke="#D2D2D7" />
                    <circle id="${prefix}-finger-dot-2" cx="71" cy="34" r="14" fill="#E5E5EA" stroke="#D2D2D7" stroke-width="1.5" />
                    <text id="${prefix}-finger-num-2" class="hand-finger-num" x="71" y="39" text-anchor="middle" font-size="14" font-weight="800" fill="#1D1D1F" ${!isRH ? 'style="transform: scaleX(-1); transform-origin: 71px 39px;"' : ''}>2</text>
                </g>

                <!-- Finger 3 (Middle) -->
                <g id="${prefix}-finger-3" class="hand-finger" style="transition: transform 0.15s ease, fill 0.15s ease;">
                    <path d="M84,75 L84,14 C84,4 106,4 106,14 L106,75" fill="#FFFFFF" stroke="#D2D2D7" />
                    <circle id="${prefix}-finger-dot-3" cx="95" cy="26" r="14" fill="#E5E5EA" stroke="#D2D2D7" stroke-width="1.5" />
                    <text id="${prefix}-finger-num-3" class="hand-finger-num" x="95" y="31" text-anchor="middle" font-size="14" font-weight="800" fill="#1D1D1F" ${!isRH ? 'style="transform: scaleX(-1); transform-origin: 95px 31px;"' : ''}>3</text>
                </g>

                <!-- Finger 4 (Ring) -->
                <g id="${prefix}-finger-4" class="hand-finger" style="transition: transform 0.15s ease, fill 0.15s ease;">
                    <path d="M108,75 L108,22 C108,12 130,12 130,22 L130,75" fill="#FFFFFF" stroke="#D2D2D7" />
                    <circle id="${prefix}-finger-dot-4" cx="119" cy="34" r="14" fill="#E5E5EA" stroke="#D2D2D7" stroke-width="1.5" />
                    <text id="${prefix}-finger-num-4" class="hand-finger-num" x="119" y="39" text-anchor="middle" font-size="14" font-weight="800" fill="#1D1D1F" ${!isRH ? 'style="transform: scaleX(-1); transform-origin: 119px 39px;"' : ''}>4</text>
                </g>

                <!-- Finger 5 (Pinky) -->
                <g id="${prefix}-finger-5" class="hand-finger" style="transition: transform 0.15s ease, fill 0.15s ease;">
                    <path d="M132,85 L132,40 C132,30 150,30 150,40 L150,85" fill="#FFFFFF" stroke="#D2D2D7" />
                    <circle id="${prefix}-finger-dot-5" cx="141" cy="50" r="13" fill="#E5E5EA" stroke="#D2D2D7" stroke-width="1.5" />
                    <text id="${prefix}-finger-num-5" class="hand-finger-num" x="141" y="55" text-anchor="middle" font-size="13" font-weight="800" fill="#1D1D1F" ${!isRH ? 'style="transform: scaleX(-1); transform-origin: 141px 55px;"' : ''}>5</text>
                </g>
            </g>
        </svg>`;
    }
};

window.HandDiagrams = HandDiagrams;

