/**
 * keyboardOverlayManager.js
 * Simplified manager for static hand diagrams.
 * Handles visibility and synchronization without moving containers.
 */

const KeyboardOverlayManager = {
    /**
     * Anchored hands don't move, just toggle visibility based on voicing.
     */
    updateHandPositions() {
        const voicing = window.piano?.voicing;
        const rhContainer = document.getElementById('rh-guide');
        const lhContainer = document.getElementById('lh-guide');

        if (!rhContainer || !lhContainer) return;

        if (!voicing) {
            this.hideHands();
            return;
        }

        // Right Hand Visibility
        if (voicing.rightHand && voicing.rightHand.length > 0) {
            rhContainer.classList.add('active');
            rhContainer.style.opacity = 1;
        } else {
            rhContainer.classList.remove('active');
            rhContainer.style.opacity = 0.3;
        }

        // Left Hand Visibility
        if (voicing.leftHand && voicing.leftHand.length > 0) {
            lhContainer.classList.add('active');
            lhContainer.style.opacity = 1;
        } else {
            lhContainer.classList.remove('active');
            lhContainer.style.opacity = 0.3;
        }
    },

    hideHands() {
        const rhContainer = document.getElementById('rh-guide');
        const lhContainer = document.getElementById('lh-guide');
        if (rhContainer) {
            rhContainer.classList.remove('active');
            rhContainer.style.opacity = 0.3;
        }
        if (lhContainer) {
            lhContainer.classList.remove('active');
            lhContainer.style.opacity = 0.3;
        }
    }
};

window.KeyboardOverlayManager = KeyboardOverlayManager;
