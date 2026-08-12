# Piano Fingering & Voicing Engine

HotChords doesn't just tell the user what chord is playing; it shows them exactly how to play it on the piano.

The logic for this is contained entirely in the frontend, specifically in `js/engine/pianoFingeringEngine.js` and `js/ui/pianoKeyboard.js`.

## The "One Voicing Per Hand" Philosophy

Many chord detection tools simply highlight every instance of a note (e.g., every 'C', 'E', and 'G' across all 88 keys). This is completely unplayable for a beginner.

HotChords implements a strict **One Voicing Per Hand** philosophy. The engine automatically assigns specific notes to specific octaves to create a playable, pedagogical arrangement:

### Left Hand (Bass/Power Anchor)
- **Octave Anchored:** Octave 2 (MIDI 36+)
- **Voicing:** Power chord (Root + Perfect 5th)
- **Purpose:** Provides a solid bass foundation without muddying the midrange, mimicking how rock/pop pianists often play left-hand parts.

### Right Hand (Harmony)
- **Octave Anchored:** Octave 4 (MIDI 60+ / Middle C)
- **Voicing:** Full closed-position chord (e.g., Root, 3rd, 5th, 7th)
- **Purpose:** Provides clear harmonic identity in the most readable range of the piano.

## Fingering Assignment

Finger assignments follow classical pedagogical numbering:
- **1** = Thumb
- **2** = Index
- **3** = Middle
- **4** = Ring
- **5** = Pinky

Fingers are strictly mapped based on the chord type. For example, a basic triad (Major/Minor):
- **Right Hand:** 1 (Root), 3 (Third), 5 (Fifth)
- **Left Hand:** 5 (Root), 3 (Fifth) - Note the thumb (1) is omitted in the simple power chord voicing to keep the hand relaxed.

### The 5-Color System

To visually link the hand diagrams to the piano keys, we use a consistent 5-color system throughout the UI:
- **Red:** Thumb (1)
- **Yellow:** Index (2)
- **Green:** Middle (3)
- **Teal:** Ring (4)
- **Blue:** Pinky (5)

## SVG Rendering & Performance

The 61-key piano (`pianoKeyboard.js`) is generated dynamically via SVG.

To maintain 60fps animations during fast chord changes, we strictly avoid `innerHTML` re-renders. 
Instead, the SVG is built once. When a chord changes, the engine looks up the specific `<rect>` elements by MIDI ID and updates their `fill` and `y` attributes to visually "press" the keys. The GSAP animation engine (`handAnimator.js`) simultaneously animates the SVG hand diagrams to press the corresponding fingers.
