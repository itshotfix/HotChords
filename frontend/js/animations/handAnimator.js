/**
 * handAnimator.js
 * GSAP-powered instructional hand animation engine.
 * Handles finger presses and pulses for static anchored hand diagrams.
 */

const HandAnimator = {
    /**
     * @param {Object} voicing { leftHand: [], rightHand: [] }
     */
    animateChord(voicing) {
        if (!window.gsap) return;

        // Reset and kill existing
        window.gsap.killTweensOf(".hand-finger path, .hand-finger rect, .hand-finger-num");
        
        const tl = window.gsap.timeline();
        
        // 1. Reset all fingers to neutral
        tl.to(".hand-finger path, .hand-finger rect", { 
            fill: "#FFFFFF", 
            y: 0, 
            duration: 0.2, 
            ease: "power2.inOut" 
        }, 0);
        
        tl.to(".hand-finger-num", { 
            opacity: 0.2, 
            fill: "#1D1D1F", 
            duration: 0.2 
        }, 0);

        if (!voicing) return;

        // 2. Animate Right Hand Active Fingers
        voicing.rightHand.forEach(v => {
            const prefix = 'rh';
            const fingerSelector = `#${prefix}-finger-${v.finger} path, #${prefix}-finger-${v.finger} rect`;
            const numSelector = `#${prefix}-finger-num-${v.finger}`;

            tl.to(fingerSelector, { 
                fill: v.color, 
                y: 8, 
                duration: 0.15, 
                ease: "back.out(1.7)" 
            }, 0.05);

            tl.to(numSelector, { 
                opacity: 1, 
                fill: "#FFFFFF", 
                duration: 0.15 
            }, 0.05);
        });

        // 3. Animate Left Hand Active Fingers
        voicing.leftHand.forEach(v => {
            const prefix = 'lh';
            const fingerSelector = `#${prefix}-finger-${v.finger} path, #${prefix}-finger-${v.finger} rect`;
            const numSelector = `#${prefix}-finger-num-${v.finger}`;

            tl.to(fingerSelector, { 
                fill: v.color, 
                y: 8, 
                duration: 0.15, 
                ease: "back.out(1.7)" 
            }, 0.05);

            tl.to(numSelector, { 
                opacity: 1, 
                fill: "#FFFFFF", 
                duration: 0.15 
            }, 0.05);
        });

        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            tl.progress(1);
        }
    },

    pulseKey(keyElement, color) {
        if (!window.gsap || !keyElement) return;
        window.gsap.fromTo(keyElement, 
            { scaleY: 1, filter: "brightness(1)" }, 
            { 
                scaleY: 0.96, 
                filter: "brightness(1.15)", 
                duration: 0.12, 
                yoyo: true, 
                repeat: 1, 
                ease: "sine.inOut" 
            }
        );
    }
};

window.HandAnimator = HandAnimator;
