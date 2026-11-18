/**
 * pianoStudio3D.js
 *
 * HotChords 3D Piano Studio — High-DPI 3D Perspective 88-Key Piano, Extruded Note Slabs,
 * Fallboard Radial Glow Orbs, Floating Billboard Chords, Curated Camera Presets,
 * and Sculpted 3D Articulated Left & Right Hands.
 *
 * Visual & Behavioral Specification:
 * - Obsidian Stage (#101012) with 88-key acoustic piano cabinet & recessed fallboard.
 * - Curated Non-Orbitable Camera Angles (smooth 400ms cubic interpolation):
 *     1. 'performer' : 38.5° downward tilt (Over-the-shoulder Performer POV)
 *     2. 'overhead'  : 76.1° downward tilt (Straight down the 88 lanes)
 *     3. 'closeup'   : 19.9° downward tilt (Low, near the hands & keys)
 * - Note Colour System:
 *     * Melody notes        : Warm Cream (#F7F4EF) with #CBC5B9 3D bevel
 *     * Instrumental notes  : Medium Slate (#9A9AA6) with #63636E 3D bevel
 *     * Chord / Bass notes  : Charcoal Slate (#686873) with #45454F 3D bevel
 *     * Active Right Hand   : Coral Rose (#FF5A7A) key illumination + fallboard radial glow
 *     * Active Left Hand    : Royal Lavender (#8B6EFE) key illumination + fallboard radial glow
 * - Sculpted 3D Human Hands:
 *     * Anatomically proportioned Left and Right hands with 3D dorsal shading, cylindrical
 *       wrists, angled thumbs (finger 1), and 4 articulated fingers (fingers 2..5).
 *     * Smooth horizontal anticipation tracking + downward finger key-strike flexion.
 */

(function(global) {
    'use strict';

    const WHITE_PCS = new Set([0, 2, 4, 5, 7, 9, 11]);

    const HAND_STRIKE_COLORS = {
        left: {
            keyTop: '#7B64FF',
            keyFront: '#523CE0',
            glowCore: 'rgba(139, 110, 254, 0.72)',
            glowEdge: 'rgba(139, 110, 254, 0.0)'
        },
        right: {
            keyTop: '#FF5A7A',
            keyFront: '#D43858',
            glowCore: 'rgba(255, 90, 122, 0.72)',
            glowEdge: 'rgba(255, 90, 122, 0.0)'
        }
    };

    const NOTE_SOURCE_STYLES = {
        melody: {
            top: '#F7F4EF',
            side: '#D0C9BE',
            front: '#FFFFFF',
            activeGlow: 'rgba(247, 244, 239, 0.55)'
        },
        accompaniment: {
            top: '#9696A2',
            side: '#646470',
            front: '#B8B8C4',
            activeGlow: 'rgba(163, 163, 175, 0.40)'
        },
        chord: {
            top: '#666672',
            side: '#454550',
            front: '#858592',
            activeGlow: 'rgba(139, 110, 254, 0.35)'
        }
    };

    const CAMERA_PRESETS = Object.freeze({
        performer: {
            id: 'performer',
            label: 'Performer',
            description: "Over the pianist's shoulder",
            tiltDeg: 38.0,
            camY: 22.47,
            camZ: 146.62,
            fov: 45,
            horizonRatio: 0.14,
            strikeRatio: 0.65,
            keybedDepthRatio: 0.19,
            farWidthRatio: 0.80,
            nearWidthRatio: 0.93,
            frontWidthRatio: 0.95
        },
        overhead: {
            id: 'overhead',
            label: 'Overhead',
            description: 'Straight down the lanes',
            tiltDeg: 76.0,
            camY: 292.18,
            camZ: 3.30,
            fov: 40,
            horizonRatio: 0.04,
            strikeRatio: 0.50,
            keybedDepthRatio: 0.22,
            farWidthRatio: 0.91,
            nearWidthRatio: 0.94,
            frontWidthRatio: 0.95
        },
        closeup: {
            id: 'closeup',
            label: 'Close-up',
            description: 'Low, near the hands',
            tiltDeg: 20.0,
            camY: 13.80,
            camZ: 142.01,
            fov: 38,
            horizonRatio: 0.22,
            strikeRatio: 0.64,
            keybedDepthRatio: 0.17,
            farWidthRatio: 0.78,
            nearWidthRatio: 0.94,
            frontWidthRatio: 0.96
        }
    });

    class PianoStudio3D {
        constructor(containerEl, options = {}) {
            this.container = typeof containerEl === 'string'
                ? (typeof document !== 'undefined' ? document.getElementById(containerEl) : null)
                : containerEl;
            this.adapter = options.adapter || global.StudioTimelineAdapter;
            this.lookAheadSec = options.lookAheadSec || 3.2;
            this.cameraPreset = options.cameraPreset || 'performer';
            this.showHands = options.showHands !== undefined ? Boolean(options.showHands) : true;
            this.showColourKey = options.showColourKey !== undefined ? Boolean(options.showColourKey) : true;
            this.currentTime = 0;

            const initCam = CAMERA_PRESETS[this.cameraPreset] || CAMERA_PRESETS.performer;
            this._animCam = Object.assign({}, initCam);
            this._lastRenderTime = 0;

            const makeHandState = (defaultMidi) => {
                const defaultU = Math.max(0.08, Math.min(0.92, (defaultMidi - 21) / 87));
                const fingerSprings = {};
                for (let f = 1; f <= 5; f++) {
                    fingerSprings[f] = {
                        u: { x: defaultU, v: 0 },
                        depth: { x: 0.64, v: 0 },
                        lift: { x: 1.0, v: 0 },
                        splay: { x: 0, v: 0 },
                        curl: { x: 0.38, v: 0 }
                    };
                }
                return {
                    centerMidi: defaultMidi,
                    targetMidi: defaultMidi,
                    wristU: defaultU,
                    wristDepth: 0.92,
                    yaw: 0,
                    roll: 0,
                    zLo: 0.78,
                    zHi: 1.04,
                    splays: { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 },
                    curls: { 1: 0.38, 2: 0.38, 3: 0.38, 4: 0.38, 5: 0.38 },
                    springU: { x: defaultU, v: 0 },
                    springDepth: { x: 0.92, v: 0 },
                    springYaw: { x: 0, v: 0 },
                    springRoll: { x: 0, v: 0 },
                    fingerSprings,
                    activeFingers: {},
                    upcomingFingers: {},
                    fingers: [],
                    visible: true
                };
            };

            this._fingerTable = this._buildFingerKinematicsTable();

            this.handState = {
                left: makeHandState(46),
                right: makeHandState(68)
            };

            this.keyGeometry = {};
            this.canvas = null;
            this.ctx = null;
            this.webglHandOverlay = null;
            this.width = 0;
            this.height = 0;

            if (this.container) {
                this._initDOM();
            }
        }

        static getCameraPresets() {
            return CAMERA_PRESETS;
        }

        _initDOM() {
            if (!this.container || typeof document === 'undefined') return;
            this.container.innerHTML = '';
            this.canvas = document.createElement('canvas');
            this.canvas.className = 'piano-studio-3d-canvas';
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

        setCameraPreset(presetName) {
            if (CAMERA_PRESETS[presetName]) {
                this.cameraPreset = presetName;
                if (this.unifiedScene) {
                    this.unifiedScene.setCameraPreset(presetName);
                }
                this.render(this.currentTime);
                if (!this.unifiedScene && typeof global.requestAnimationFrame === 'function') {
                    const stepCam = () => {
                        if (!this.cameraState || !this.cameraState.animating) return;
                        this.render(this.currentTime);
                        if (this.cameraState.animating) {
                            global.requestAnimationFrame(stepCam);
                        }
                    };
                    global.requestAnimationFrame(stepCam);
                }
                return true;
            }
            return false;
        }

        setShowHands(visible) {
            this.showHands = Boolean(visible);
            if (this.unifiedScene) {
                this.unifiedScene.setShowHands(this.showHands);
            }
            this.render(this.currentTime);
            return this.showHands;
        }

        setShowColourKey(visible) {
            this.showColourKey = Boolean(visible);
            this.render(this.currentTime);
            return this.showColourKey;
        }

        _buildNormalizedKeyMap() {
            const map = {};
            const whiteNormW = 1 / 52;
            const blackNormW = whiteNormW * 0.60;
            let wIdx = 0;

            for (let midi = 21; midi <= 108; midi++) {
                const pc = midi % 12;
                if (WHITE_PCS.has(pc)) {
                    const u0 = wIdx * whiteNormW;
                    map[midi] = {
                        midi,
                        isBlack: false,
                        u0,
                        u1: u0 + whiteNormW,
                        uCenter: u0 + whiteNormW / 2
                    };
                    wIdx++;
                }
            }

            for (let midi = 21; midi <= 108; midi++) {
                const pc = midi % 12;
                if (!WHITE_PCS.has(pc)) {
                    const prev = map[midi - 1];
                    const baseU = prev ? prev.u1 : 0;
                    const u0 = baseU - blackNormW / 2;
                    map[midi] = {
                        midi,
                        isBlack: true,
                        u0,
                        u1: u0 + blackNormW,
                        uCenter: u0 + blackNormW / 2,
                        gapU: u0 + blackNormW / 2
                    };
                }
            }

            // Compute safe upper-gap center (`gapU`) on white keys between adjacent black keys
            for (let midi = 21; midi <= 108; midi++) {
                const kg = map[midi];
                if (!kg || kg.isBlack) continue;
                const leftBlack = map[midi - 1] && map[midi - 1].isBlack ? map[midi - 1] : null;
                const rightBlack = map[midi + 1] && map[midi + 1].isBlack ? map[midi + 1] : null;
                const safeLeft = leftBlack ? Math.max(kg.u0, leftBlack.u1) : kg.u0;
                const safeRight = rightBlack ? Math.min(kg.u1, rightBlack.u0) : kg.u1;
                kg.gapU = (safeLeft + safeRight) * 0.5;
            }
            this.keyGeometry = map;
            return map;
        }

        resize() {
            if (!this.container || !this.canvas) return;
            const W = this.container.clientWidth || 1080;
            const H = this.container.clientHeight || 560;
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

            this._buildNormalizedKeyMap();
            if (this.unifiedScene) {
                this.unifiedScene.resize();
            }
            this.render(this.currentTime);
        }

        /**
         * Projects normalized lateral coordinate `u` in [0, 1] and waterfall depth `zNorm` in [0=strikeLine, 1=farHorizon].
         */
        project3DPoint(u, zNorm) {
            const W = this.width || 1080;
            const H = this.height || 560;
            const cam = this._animCam;

            const strikeY = H * cam.strikeRatio;
            const horizonY = H * cam.horizonRatio;

            const depthCurve = Math.pow(Math.max(0, Math.min(1, zNorm)), 0.86);
            const y = strikeY - depthCurve * (strikeY - horizonY);

            const spanRatio = cam.nearWidthRatio + (cam.farWidthRatio - cam.nearWidthRatio) * depthCurve;
            const leftEdge = W * (0.5 - spanRatio * 0.5);
            const spanW = W * spanRatio;
            const x = leftEdge + u * spanW;
            const scale = spanRatio / cam.nearWidthRatio;

            return { x, y, scale, strikeY, horizonY };
        }

        /**
         * Projects a point on the 3D keybed where `kDepth` is in [0=rearStrikeLine, 1=frontKeyLip].
         */
        projectKeybedPoint(u, kDepth) {
            const W = this.width || 1080;
            const H = this.height || 560;
            const cam = this._animCam;

            const strikeY = H * cam.strikeRatio;
            const frontY = strikeY + H * cam.keybedDepthRatio;
            const y = strikeY + kDepth * (frontY - strikeY);

            const spanRatio = cam.nearWidthRatio + (cam.frontWidthRatio - cam.nearWidthRatio) * kDepth;
            const leftEdge = W * (0.5 - spanRatio * 0.5);
            const spanW = W * spanRatio;
            const x = leftEdge + u * spanW;

            return { x, y, strikeY, frontY };
        }

        _handleCanvasClick(e) {
            if (!this.canvas || !this.height) return;
            const rect = this.canvas.getBoundingClientRect ? this.canvas.getBoundingClientRect() : { left: 0, top: 0 };
            const x = (e.clientX || 0) - rect.left;
            const y = (e.clientY || 0) - rect.top;

            const strikeY = this.height * this._animCam.strikeRatio;
            const frontY = strikeY + this.height * this._animCam.keybedDepthRatio;

            if (y >= strikeY - 10 && y <= frontY + 20) {
                // Audition clicked 3D piano key
                const spanW = this.width * this._animCam.frontWidthRatio;
                const leftEdge = (this.width - spanW) * 0.5;
                const u = (x - leftEdge) / Math.max(1, spanW);
                if (u >= 0 && u <= 1) {
                    let hitMidi = null;
                    for (let m = 21; m <= 108; m++) {
                        const kg = this.keyGeometry[m];
                        if (kg && kg.isBlack && u >= kg.u0 && u <= kg.u1 && y <= strikeY + (frontY - strikeY) * 0.64) {
                            hitMidi = m;
                            break;
                        }
                    }
                    if (!hitMidi) {
                        for (let m = 21; m <= 108; m++) {
                            const kg = this.keyGeometry[m];
                            if (kg && !kg.isBlack && u >= kg.u0 && u <= kg.u1) {
                                hitMidi = m;
                                break;
                            }
                        }
                    }
                    this._auditionMidi(hitMidi);
                }
            }
        }

        _auditionMidi(hitMidi) {
            if (!hitMidi) return;
            if (global.PianoPlaybackService) {
                global.PianoPlaybackService.playNote(hitMidi, 0.85, 0.45);
            }
            if (global.LearnModeController && global.LearnModeController.enabled) {
                global.LearnModeController.submitUserNotes([hitMidi]);
            }
        }

        _stepSpring(spring, target, omega, dt) {
            if (!spring) return target;
            if (dt <= 0 || dt > 0.25) {
                spring.x = target;
                spring.v = 0;
                return target;
            }
            const clampedDt = Math.min(dt, 0.08);
            const diff = spring.x - target;
            const vel = spring.v + omega * diff;
            const decay = Math.exp(-omega * clampedDt);
            spring.x = target + (diff + vel * clampedDt) * decay;
            spring.v = (vel - omega * (diff + vel * clampedDt)) * decay;
            return spring.x;
        }

        _buildFingerKinematicsTable() {
            const CURL_STEPS = 32;
            const SPLAY_STEPS = 41;
            const phalanx = [0.45, 0.32, 0.23];
            const reaches = { 1: 0.26, 2: 0.44, 3: 0.48, 4: 0.44, 5: 0.36 };
            const maxSplayRad = { 1: 0.46, 2: 0.24, 3: 0.16, 4: 0.22, 5: 0.32 };
            const table = {};

            for (let f = 1; f <= 5; f++) {
                const fLen = reaches[f];
                const rows = [];
                for (let ci = 0; ci < CURL_STEPS; ci++) {
                    const curl = ci / (CURL_STEPS - 1); // 0 = extended, 1 = deep strike curl
                    const totalBend = curl * 1.45;
                    let forwardReach = 0;
                    let dropY = 0;
                    let cumAngle = 0;
                    for (let p = 0; p < 3; p++) {
                        cumAngle += totalBend * phalanx[p];
                        forwardReach += fLen * phalanx[p] * Math.cos(cumAngle);
                        dropY += fLen * phalanx[p] * Math.sin(cumAngle);
                    }
                    const splayCols = [];
                    for (let si = 0; si < SPLAY_STEPS; si++) {
                        const splay = -1 + (2 * si) / (SPLAY_STEPS - 1);
                        const ang = splay * maxSplayRad[f];
                        splayCols.push({
                            latOffset: forwardReach * Math.sin(ang),
                            fwdReach: forwardReach * Math.cos(ang),
                            dropY
                        });
                    }
                    rows.push(splayCols);
                }
                table[f] = rows;
            }
            return table;
        }

        _sampleFingerKinematics(finger, curl, splay) {
            if (!this._fingerTable || !this._fingerTable[finger]) {
                return { latOffset: 0, fwdReach: 0.38, dropY: 0.1 };
            }
            const cClamped = Math.max(0, Math.min(1, Number(curl) || 0));
            const sClamped = Math.max(-1, Math.min(1, Number(splay) || 0));
            const ci = Math.round(cClamped * 31);
            const si = Math.round(((sClamped + 1) * 0.5) * 40);
            return this._fingerTable[finger][ci][si];
        }

        _solveHandPose(handName, activeForHand, upcomingForHand, hObj) {
            if (!this.keyGeometry || Object.keys(this.keyGeometry).length === 0) {
                this._buildNormalizedKeyMap();
            }
            const isLeft = handName === 'left';
            const whiteNormW = 1 / 52;
            const fingerSlotOffsets = isLeft
                ? { 5: -2.0 * whiteNormW, 4: -1.0 * whiteNormW, 3: 0, 2: 1.0 * whiteNormW, 1: 2.05 * whiteNormW }
                : { 1: -2.05 * whiteNormW, 2: -1.0 * whiteNormW, 3: 0, 4: 1.0 * whiteNormW, 5: 2.0 * whiteNormW };
            const fingerReaches = { 1: 0.26, 2: 0.44, 3: 0.48, 4: 0.44, 5: 0.36 };

            const activeMap = {};
            activeForHand.forEach(n => {
                const f = Math.max(1, Math.min(5, Number(n.finger || 1)));
                if (!activeMap[f]) activeMap[f] = n;
            });

            const nearUpcoming = {};
            upcomingForHand.forEach(n => {
                const f = Math.max(1, Math.min(5, Number(n.finger || 1)));
                if (!activeMap[f] && n.timeUntilStrike <= 0.42) {
                    if (!nearUpcoming[f] || n.timeUntilStrike < nearUpcoming[f].timeUntilStrike) {
                        nearUpcoming[f] = n;
                    }
                }
            });

            const chordNotes = Object.values(activeMap).length > 0
                ? Object.values(activeMap)
                : Object.values(nearUpcoming);
            const hasBlackInChord = chordNotes.some(n => {
                const kg = this.keyGeometry[n.midi];
                return kg && kg.isBlack;
            });

            const targets = [];
            for (let f = 1; f <= 5; f++) {
                const note = activeMap[f] || nearUpcoming[f];
                if (!note || !this.keyGeometry[note.midi]) continue;
                const kg = this.keyGeometry[note.midi];
                const useGap = !kg.isBlack && hasBlackInChord && f !== 1;
                const targetU = useGap && typeof kg.gapU === 'number' ? kg.gapU : kg.uCenter;
                const targetDepth = kg.isBlack ? 0.39 : (useGap ? 0.56 : 0.67);
                targets.push({
                    finger: f,
                    u: targetU,
                    depth: targetDepth,
                    isBlack: kg.isBlack,
                    pressed: Boolean(activeMap[f]),
                    weight: activeMap[f] ? 1.0 : Math.max(0.25, 1.0 - (note.timeUntilStrike / 0.42))
                });
            }

            let targetWristU = hObj.wristU;
            let targetWristDepth = 0.93;
            let targetYaw = 0;
            let targetRoll = 0;
            let zLo = 0.72;
            let zHi = 1.06;
            const targetSplays = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 };
            const targetCurls = { 1: 0.36, 2: 0.38, 3: 0.38, 4: 0.38, 5: 0.38 };

            if (targets.length > 0) {
                // 25 yaw candidates in [-0.35, +0.35] rad
                let bestScore = Infinity;
                for (let yi = 0; yi < 25; yi++) {
                    const yaw = -0.35 + (0.70 * yi) / 24;
                    const cosY = Math.cos(yaw);
                    const sinY = Math.sin(yaw);

                    let sumU = 0;
                    let sumW = 0;
                    targets.forEach(t => {
                        const restLat = fingerSlotOffsets[t.finger] * cosY;
                        sumU += (t.u - restLat) * t.weight;
                        sumW += t.weight;
                    });
                    const wU = Math.max(0.04, Math.min(0.96, sumU / Math.max(0.001, sumW)));

                    let latErr = 0;
                    let lo = 0.68;
                    let hi = 1.08;
                    let sumZ = 0;
                    targets.forEach(t => {
                        const reach = fingerReaches[t.finger];
                        const expectedU = wU + fingerSlotOffsets[t.finger] * cosY + sinY * 0.014;
                        const du = (t.u - expectedU) / whiteNormW;
                        latErr += du * du * t.weight;

                        const minZForFinger = t.depth + reach * 0.42;
                        const maxZForFinger = t.depth + reach * 1.18;
                        lo = Math.max(lo, minZForFinger);
                        hi = Math.min(hi, maxZForFinger);
                        sumZ += (t.depth + reach * (t.isBlack ? 0.68 : 0.78)) * t.weight;
                    });

                    const strain = latErr + 1.8 * yaw * yaw;
                    if (strain < bestScore) {
                        bestScore = strain;
                        targetWristU = wU;
                        targetYaw = yaw;
                        zLo = lo;
                        zHi = hi;
                        const idealZ = sumZ / Math.max(0.001, sumW);
                        targetWristDepth = zLo <= zHi
                            ? Math.min(zHi, Math.max(zLo, idealZ))
                            : (zLo + zHi) * 0.5;
                    }
                }

                // 11 roll candidates in [-0.20, +0.20] rad to balance lateral arch & black/white height
                let bestRollScore = Infinity;
                for (let ri = 0; ri < 11; ri++) {
                    const roll = -0.20 + (0.40 * ri) / 10;
                    let rErr = 0;
                    targets.forEach(t => {
                        const side = fingerSlotOffsets[t.finger] / Math.max(0.001, 2.05 * whiteNormW);
                        const expectedLift = t.isBlack ? 0.18 : 0.0;
                        const actualLift = side * roll * 0.6;
                        const d = expectedLift - actualLift;
                        rErr += d * d * t.weight;
                    });
                    const totalR = rErr + 0.6 * roll * roll;
                    if (totalR < bestRollScore) {
                        bestRollScore = totalR;
                        targetRoll = roll;
                    }
                }

                // Per-finger splay & curl optimization from precomputed kinematics table
                const cosY = Math.cos(targetYaw);
                const sinY = Math.sin(targetYaw);
                targets.forEach(t => {
                    const baseU = targetWristU + fingerSlotOffsets[t.finger] * cosY + sinY * 0.014;
                    const deltaU = t.u - baseU;
                    const reach = fingerReaches[t.finger];
                    const reqFwd = Math.max(0.12, Math.min(reach, targetWristDepth - t.depth));
                    const curlGuess = Math.max(0.15, Math.min(0.95, 1.0 - (reqFwd / reach) * 0.65));
                    targetCurls[t.finger] = t.pressed ? Math.max(0.55, curlGuess) : Math.max(0.32, curlGuess * 0.75);

                    let bestSplay = 0;
                    let bestLatDiff = Infinity;
                    for (let si = 0; si < 41; si += 2) {
                        const s = -1 + (2 * si) / 40;
                        const sample = this._sampleFingerKinematics(t.finger, targetCurls[t.finger], s);
                        const predLatU = sample.latOffset * 0.22;
                        const diff = Math.abs(deltaU - predLatU);
                        if (diff < bestLatDiff) {
                            bestLatDiff = diff;
                            bestSplay = s;
                        }
                    }
                    targetSplays[t.finger] = bestSplay;
                });
            }

            return {
                targetWristU,
                targetWristDepth,
                targetYaw,
                targetRoll,
                targetSplays,
                targetCurls,
                zLo,
                zHi,
                activeMap,
                nearUpcoming,
                hasBlackInChord
            };
        }

        _updateHandKinematics(activeNotes, upcomingNotes, dt = 0.016) {
            const handFilter = this.adapter ? this.adapter.handFilter : 'both';

            ['left', 'right'].forEach(handName => {
                const hObj = this.handState[handName];
                hObj.activeFingers = {};
                hObj.visible = (handFilter === 'both' || handFilter === handName);

                const activeForHand = activeNotes.filter(n => n.hand === handName);
                const upcomingForHand = upcomingNotes.filter(n => n.hand === handName && n.timeUntilStrike <= 0.85);

                activeForHand.forEach(n => {
                    const f = Math.max(1, Math.min(5, Number(n.finger || 1)));
                    hObj.activeFingers[f] = n;
                });
                hObj.upcomingFingers = {};
                upcomingForHand.forEach(n => {
                    const f = Math.max(1, Math.min(5, Number(n.finger || 1)));
                    if (!hObj.upcomingFingers[f] || n.timeUntilStrike < hObj.upcomingFingers[f].timeUntilStrike) {
                        hObj.upcomingFingers[f] = n;
                    }
                });

                const refNotes = activeForHand.length > 0 ? activeForHand : upcomingForHand;
                if (refNotes.length > 0) {
                    const sumMidi = refNotes.reduce((acc, n) => acc + n.midi, 0);
                    hObj.targetMidi = sumMidi / refNotes.length;
                }

                const solved = this._solveHandPose(handName, activeForHand, upcomingForHand, hObj);
                hObj.zLo = solved.zLo;
                hObj.zHi = solved.zHi;

                // Critically-damped spring smoothing for wrist X, Z-depth, yaw, and roll
                hObj.wristU = this._stepSpring(hObj.springU, solved.targetWristU, 19.5, dt);
                hObj.wristDepth = this._stepSpring(hObj.springDepth, solved.targetWristDepth, 18.0, dt);
                hObj.yaw = this._stepSpring(hObj.springYaw, solved.targetYaw, 16.0, dt);
                hObj.roll = this._stepSpring(hObj.springRoll, solved.targetRoll || 0, 15.0, dt);
                for (let f = 1; f <= 5; f++) {
                    const fSpr = hObj.fingerSprings[f];
                    hObj.splays[f] = this._stepSpring(fSpr.splay, (solved.targetSplays && solved.targetSplays[f]) || 0, 20.0, dt);
                    hObj.curls[f] = this._stepSpring(fSpr.curl, (solved.targetCurls && solved.targetCurls[f]) || 0.38, 22.0, dt);
                }
                hObj.centerMidi = 21 + hObj.wristU * 87;
            });
        }

        render(currentTime = 0) {
            const prevTime = this.currentTime;
            this.currentTime = Number(currentTime) || 0;
            const rawDt = this.currentTime - prevTime;
            const dt = (rawDt > 0 && rawDt <= 0.25) ? rawDt : (rawDt === 0 ? 0.016 : 999);
            this._lastDt = dt;

            if (!this.keyGeometry || Object.keys(this.keyGeometry).length === 0) {
                this._buildNormalizedKeyMap();
            }

            // Smooth camera interpolation toward target preset
            const targetCam = CAMERA_PRESETS[this.cameraPreset] || CAMERA_PRESETS.performer;
            const lerp = 0.25;
            this._animCam.tiltDeg += (targetCam.tiltDeg - this._animCam.tiltDeg) * lerp;
            this._animCam.horizonRatio += (targetCam.horizonRatio - this._animCam.horizonRatio) * lerp;
            this._animCam.strikeRatio += (targetCam.strikeRatio - this._animCam.strikeRatio) * lerp;
            this._animCam.keybedDepthRatio += (targetCam.keybedDepthRatio - this._animCam.keybedDepthRatio) * lerp;
            this._animCam.farWidthRatio += (targetCam.farWidthRatio - this._animCam.farWidthRatio) * lerp;
            this._animCam.nearWidthRatio += (targetCam.nearWidthRatio - this._animCam.nearWidthRatio) * lerp;
            this._animCam.frontWidthRatio += (targetCam.frontWidthRatio - this._animCam.frontWidthRatio) * lerp;

            const winState = this.adapter
                ? this.adapter.getWindowState(this.currentTime, this.lookAheadSec, 0.3)
                : { activeNotes: [], upcomingNotes: [], completedNotes: [] };

            this._updateHandKinematics(winState.activeNotes, winState.upcomingNotes, dt);
            this.lastRenderedState = {
                currentTime: this.currentTime,
                cameraPreset: this.cameraPreset,
                tiltDeg: Math.round(this._animCam.tiltDeg * 10) / 10,
                activeNotesCount: winState.activeNotes.length,
                upcomingNotesCount: winState.upcomingNotes.length,
                handState: this.handState
            };

            if (!this.unifiedScene && typeof global.UnifiedPianoScene === 'function' && this.container && typeof document !== 'undefined') {
                try {
                    this.unifiedScene = new global.UnifiedPianoScene(this.container, {
                        cameraPreset: this.cameraPreset,
                        showHands: this.showHands,
                        showColourKey: this.showColourKey,
                        lookAheadSec: this.lookAheadSec,
                        onKeyClick: (midi) => this._auditionMidi(midi),
                        onContextLost: () => {
                            this.unifiedScene = null;
                            if (this.canvas && this.canvas.style) this.canvas.style.display = 'block';
                            this.render(this.currentTime);
                        }
                    });
                } catch (e) {
                    this.unifiedScene = null;
                }
            }

            if (this.unifiedScene && this.unifiedScene.ready) {
                if (this.canvas && this.canvas.style) {
                    this.canvas.style.display = 'none';
                }
                this.unifiedScene.setShowColourKey(this.showColourKey);
                this.unifiedScene.renderState({
                    currentTime: this.currentTime,
                    activeNotes: winState.activeNotes,
                    upcomingNotes: winState.upcomingNotes,
                    chords: (this.adapter && typeof this.adapter.getChords === 'function') ? this.adapter.getChords() : [],
                    handFilter: (this.adapter && this.adapter.handFilter) || 'both'
                });
                return this.lastRenderedState;
            }
            if (this.canvas && this.canvas.style) {
                this.canvas.style.display = 'block';
            }

            const ctx = this.ctx;
            if (!ctx) return this.lastRenderedState;

            const W = this.width || 1080;
            const H = this.height || 560;

            // 1. Deep Obsidian Stage Canvas (#101012)
            ctx.fillStyle = '#101012';
            ctx.fillRect(0, 0, W, H);

            // 2. Subtle Perspective Octave Guides in Waterfall
            for (let midi = 24; midi <= 96; midi += 12) {
                const kg = this.keyGeometry[midi];
                if (!kg) continue;
                const nearPt = this.project3DPoint(kg.u0, 0);
                const farPt = this.project3DPoint(kg.u0, 1);
                ctx.strokeStyle = 'rgba(255, 255, 255, 0.035)';
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(farPt.x, farPt.y);
                ctx.lineTo(nearPt.x, nearPt.y);
                ctx.stroke();
            }

            // 3. Extruded 3D Falling Note Bars (Sorted Far-to-Near)
            const notesToRender = [...winState.upcomingNotes, ...winState.activeNotes]
                .sort((a, b) => b.end - a.end);

            notesToRender.forEach(n => {
                const kg = this.keyGeometry[n.midi];
                if (!kg) return;

                const zNear = Math.max(0, Math.min(1, (n.start - this.currentTime) / this.lookAheadSec));
                const zFar = Math.max(0, Math.min(1, (n.end - this.currentTime) / this.lookAheadSec));
                if (zFar <= zNear + 0.002) return;

                const padU = kg.isBlack ? 0.0006 : 0.0011;
                const nL = this.project3DPoint(kg.u0 + padU, zNear);
                const nR = this.project3DPoint(kg.u1 - padU, zNear);
                const fL = this.project3DPoint(kg.u0 + padU, zFar);
                const fR = this.project3DPoint(kg.u1 - padU, zFar);

                const thickness = Math.max(3.5, 8.5 * nL.scale);
                const style = this.showColourKey
                    ? (NOTE_SOURCE_STYLES[n.source] || NOTE_SOURCE_STYLES.melody)
                    : NOTE_SOURCE_STYLES.melody;

                ctx.save();
                // 3D Extruded Slab Body (Top Face)
                ctx.fillStyle = style.top;
                ctx.globalAlpha = n.state === 'active' ? 1.0 : 0.92;
                ctx.beginPath();
                ctx.moveTo(fL.x, fL.y - thickness * 0.55);
                ctx.lineTo(fR.x, fR.y - thickness * 0.55);
                ctx.lineTo(nR.x, nR.y - thickness);
                ctx.lineTo(nL.x, nL.y - thickness);
                ctx.closePath();
                ctx.fill();

                // 3D Front Bevel Thickness Face
                ctx.fillStyle = n.state === 'active' ? style.front : style.side;
                ctx.fillRect(nL.x, nL.y - thickness, Math.max(2.5, nR.x - nL.x), thickness);

                ctx.restore();
            });

            // 4. Floating Billboard Chord Symbols in Waterfall (collision-safe, camera-frustum clamped)
            if (this.adapter) {
                const chords = this.adapter.getChords();
                let lastLabelY = Infinity;
                chords.forEach(c => {
                    const cStart = Number(c.startTime ?? c.time ?? 0);
                    const cEnd = Number(c.endTime ?? c.end ?? (cStart + 1.5));
                    if (cStart >= this.currentTime - 0.15 && cStart <= this.currentTime + this.lookAheadSec * 0.92) {
                        const cName = c.chordName || c.chord || '';
                        if (!cName || cName === 'N') return;

                        const zChord = Math.max(0.01, Math.min(0.95, (cStart - this.currentTime) / this.lookAheadSec));
                        const bassKg = this.keyGeometry[41] || this.keyGeometry[43] || { u0: 0.25 };
                        const pt = this.project3DPoint(bassKg.u0 - 0.025, zChord);
                        if (Math.abs(lastLabelY - pt.y) < 22) return;
                        lastLabelY = pt.y;

                        const isActive = (this.currentTime >= cStart && this.currentTime < cEnd) || zChord < 0.08;

                        ctx.save();
                        const fontSize = Math.max(11, Math.round(14 * pt.scale));
                        ctx.font = `700 ${fontSize}px -apple-system, BlinkMacSystemFont, "Geist Sans", sans-serif`;
                        const textW = typeof ctx.measureText === 'function' ? ctx.measureText(cName).width : cName.length * fontSize * 0.6;
                        const pillW = Math.max(32, textW + 14);
                        const pillH = Math.max(18, fontSize + 7);
                        const labelX = Math.max(14 + pillW / 2, Math.min(W - 14 - pillW / 2, pt.x - pillW * 0.35));
                        const pillY = pt.y - pillH - 2;

                        ctx.fillStyle = isActive ? '#F7F4EF' : 'rgba(18, 18, 22, 0.86)';
                        ctx.strokeStyle = isActive ? '#F7F4EF' : 'rgba(255, 255, 255, 0.20)';
                        ctx.lineWidth = 1;
                        ctx.beginPath();
                        if (typeof ctx.roundRect === 'function') {
                            ctx.roundRect(labelX - pillW / 2, pillY, pillW, pillH, 5);
                        } else {
                            ctx.rect(labelX - pillW / 2, pillY, pillW, pillH);
                        }
                        ctx.fill();
                        if (!isActive) ctx.stroke();

                        ctx.fillStyle = isActive ? '#101012' : 'rgba(247, 244, 239, 0.94)';
                        ctx.textAlign = 'center';
                        ctx.fillText(cName, labelX, pillY + pillH - 5);
                        ctx.restore();
                    }
                });
            }

            // 5. 3D Acoustic Piano Chassis, Fallboard & Radial Strike Glow Orbs
            const rearLeft = this.projectKeybedPoint(0, 0);
            const rearRight = this.projectKeybedPoint(1, 0);
            const frontLeft = this.projectKeybedPoint(0, 1);
            const frontRight = this.projectKeybedPoint(1, 1);
            const cheekW = Math.max(14, W * 0.018);

            // Outer Ebony Piano Cabinet Body
            ctx.fillStyle = '#070709';
            ctx.beginPath();
            ctx.moveTo(rearLeft.x - cheekW * 0.7, rearLeft.y - 16);
            ctx.lineTo(rearRight.x + cheekW * 0.7, rearRight.y - 16);
            ctx.lineTo(frontRight.x + cheekW, frontRight.y + 18);
            ctx.lineTo(frontLeft.x - cheekW, frontLeft.y + 18);
            ctx.closePath();
            ctx.fill();

            // Recessed Fallboard Strip
            ctx.fillStyle = '#121216';
            ctx.beginPath();
            ctx.moveTo(rearLeft.x - 4, rearLeft.y - 11);
            ctx.lineTo(rearRight.x + 4, rearRight.y - 11);
            ctx.lineTo(rearRight.x + 4, rearRight.y);
            ctx.lineTo(rearLeft.x - 4, rearLeft.y);
            ctx.closePath();
            ctx.fill();

            // Active Key Strike Radial Glow Orbs on Fallboard
            const activeMap = {};
            winState.activeNotes.forEach(n => { activeMap[n.midi] = n; });

            winState.activeNotes.forEach(n => {
                const kg = this.keyGeometry[n.midi];
                if (!kg) return;
                const strikePt = this.projectKeybedPoint(kg.uCenter, 0);
                const hTheme = HAND_STRIKE_COLORS[n.hand] || HAND_STRIKE_COLORS.right;
                const radius = Math.max(18, W * 0.024);

                if (typeof ctx.createRadialGradient === 'function') {
                    const grad = ctx.createRadialGradient(strikePt.x, strikePt.y - 4, 2, strikePt.x, strikePt.y - 4, radius);
                    grad.addColorStop(0, hTheme.glowCore);
                    grad.addColorStop(1, hTheme.glowEdge);
                    ctx.fillStyle = grad;
                    ctx.beginPath();
                    ctx.arc(strikePt.x, strikePt.y - 4, radius, 0, Math.PI * 2);
                    ctx.fill();
                }
            });

            // 6. 88-Key Physical 3D Keybed (52 White Keys with Rear-Pivot Depression)
            const monoTheme = {
                keyTop: '#D4CFC6',
                keyFront: '#ABA69C',
                glowCore: 'rgba(247, 244, 239, 0.55)',
                glowEdge: 'rgba(247, 244, 239, 0.0)'
            };

            for (let midi = 21; midi <= 108; midi++) {
                const kg = this.keyGeometry[midi];
                if (!kg || kg.isBlack) continue;
                const act = activeMap[midi];
                const hTheme = act
                    ? (this.showColourKey ? (HAND_STRIKE_COLORS[act.hand] || HAND_STRIKE_COLORS.right) : monoTheme)
                    : null;

                const rL = this.projectKeybedPoint(kg.u0 + 0.0004, 0);
                const rR = this.projectKeybedPoint(kg.u1 - 0.0004, 0);
                const fL = this.projectKeybedPoint(kg.u0 + 0.0004, 1);
                const fR = this.projectKeybedPoint(kg.u1 - 0.0004, 1);

                // Rear-pivot depression: front edge dips 4.5px when struck
                const dipY = act ? 4.5 : 0;

                ctx.fillStyle = act ? hTheme.keyTop : '#EAE7E1';
                ctx.beginPath();
                ctx.moveTo(rL.x, rL.y);
                ctx.lineTo(rR.x, rR.y);
                ctx.lineTo(fR.x, fR.y + dipY);
                ctx.lineTo(fL.x, fL.y + dipY);
                ctx.closePath();
                ctx.fill();

                ctx.strokeStyle = '#18181C';
                ctx.lineWidth = 0.7;
                ctx.stroke();

                // White key front vertical lip
                const lipH = act ? 5 : 8;
                ctx.fillStyle = act ? hTheme.keyFront : '#C8C4BC';
                ctx.fillRect(fL.x, fL.y + dipY, Math.max(2, fR.x - fL.x), lipH);
            }

            // 7. 36 Black Keys (Elevated 3D Ebony Prisms with Bevels)
            for (let midi = 21; midi <= 108; midi++) {
                const kg = this.keyGeometry[midi];
                if (!kg || !kg.isBlack) continue;
                const act = activeMap[midi];
                const hTheme = act
                    ? (this.showColourKey ? (HAND_STRIKE_COLORS[act.hand] || HAND_STRIKE_COLORS.right) : { keyTop: '#565662', keyFront: '#383842' })
                    : null;

                const rL = this.projectKeybedPoint(kg.u0, 0);
                const rR = this.projectKeybedPoint(kg.u1, 0);
                const fL = this.projectKeybedPoint(kg.u0, 0.62);
                const fR = this.projectKeybedPoint(kg.u1, 0.62);

                const elev = act ? 2.5 : 5.5;

                // Black key top surface
                ctx.fillStyle = act ? hTheme.keyTop : '#1D1D22';
                ctx.beginPath();
                ctx.moveTo(rL.x, rL.y - elev);
                ctx.lineTo(rR.x, rR.y - elev);
                ctx.lineTo(fR.x, fR.y - elev);
                ctx.lineTo(fL.x, fL.y - elev);
                ctx.closePath();
                ctx.fill();

                // Black key front sloped bevel
                ctx.fillStyle = act ? hTheme.keyFront : '#0B0B0E';
                ctx.beginPath();
                ctx.moveTo(fL.x, fL.y - elev);
                ctx.lineTo(fR.x, fR.y - elev);
                ctx.lineTo(fR.x + 1, fR.y + 2);
                ctx.lineTo(fL.x - 1, fL.y + 2);
                ctx.closePath();
                ctx.fill();
            }

            // 8. Sculpted 3D Articulated Virtual Hands (Left & Right)
            if (this.showHands) {
                this._render3DArticulatedHands(ctx, W, H);
            }

            return this.lastRenderedState;
        }

        /**
         * Renders realistic sculpted 3D skin-shaded Left and Right pianist hands
         * with cylindrical wrists, contoured dorsal palms, angled thumbs, and 5 articulated fingers.
         */
        _render3DArticulatedHands(ctx, W, H) {
            if (!this.webglHandOverlay && typeof global.HotChordsRiggedHandsOverlay === 'function' && this.container && typeof document !== 'undefined') {
                try {
                    this.webglHandOverlay = new global.HotChordsRiggedHandsOverlay(this.container);
                } catch (e) {
                    this.webglHandOverlay = null;
                }
            }
            const webglReady = Boolean(this.webglHandOverlay && this.webglHandOverlay.ready);
            if (this.webglHandOverlay) {
                this.webglHandOverlay.renderFrame({
                    showHands: this.showHands,
                    cameraPreset: (this.cameraState && this.cameraState.targetPreset) || this.cameraPreset,
                    cameraState: this.cameraState,
                    handState: this.handState,
                    currentTime: this.currentTime,
                    dt: this._lastDt || 0.016,
                });
            }

            const handDefinitions = [
                {
                    key: 'left',
                    // Left hand fingers left-to-right: Pinky(5), Ring(4), Middle(3), Index(2), Thumb(1)
                    fingerOrder: [5, 4, 3, 2, 1],
                    lengthFactors: { 5: 0.72, 4: 0.90, 3: 1.00, 2: 0.88, 1: 0.62 },
                    spreadOffsets: [-1.85, -0.95, 0.0, 0.95, 1.95]
                },
                {
                    key: 'right',
                    // Right hand fingers left-to-right: Thumb(1), Index(2), Middle(3), Ring(4), Pinky(5)
                    fingerOrder: [1, 2, 3, 4, 5],
                    lengthFactors: { 1: 0.62, 2: 0.88, 3: 1.00, 4: 0.90, 5: 0.72 },
                    spreadOffsets: [-1.95, -0.95, 0.0, 0.95, 1.85]
                }
            ];

            handDefinitions.forEach(def => {
                const hState = this.handState[def.key];
                if (!hState.visible) return;

                const isLeft = def.key === 'left';
                const whiteNormW = 1 / 52;
                const wristU = Math.max(0.04, Math.min(0.96, hState.wristU !== undefined ? hState.wristU : ((hState.centerMidi - 21) / 87)));
                const wristDepth = Math.max(0.68, Math.min(1.08, hState.wristDepth !== undefined ? hState.wristDepth : 0.92));
                const yaw = hState.yaw || 0;
                const cosY = Math.cos(yaw);
                const sinY = Math.sin(yaw);

                const palmAnchor = this.projectKeybedPoint(wristU, wristDepth);
                const palmW = Math.max(46, W * 0.056);
                const palmH = Math.max(38, H * 0.072);
                const palmX = palmAnchor.x;
                const palmY = palmAnchor.y + palmH * 0.14;

                const activeNotesList = Object.values(hState.activeFingers || {});
                const upcomingNotesList = Object.values(hState.upcomingFingers || {});
                const hasBlackInChord = [...activeNotesList, ...upcomingNotesList].some(n => {
                    const kg = this.keyGeometry[n.midi];
                    return kg && kg.isBlack;
                });

                if (!webglReady) {
                    ctx.save();

                    // 1. Soft Shadow Cast by Hand onto Keys
                    ctx.fillStyle = 'rgba(0, 0, 0, 0.36)';
                    ctx.beginPath();
                    if (typeof ctx.ellipse === 'function') {
                        ctx.ellipse(palmX, palmY - 4, palmW * 0.68, palmH * 0.58, yaw * 0.65, 0, Math.PI * 2);
                    } else {
                        ctx.arc(palmX, palmY - 4, palmW * 0.6, 0, Math.PI * 2);
                    }
                    ctx.fill();
                }

                // 2. Render 5 Articulated 3D Fingers using solved wrist X/Z, yaw, and black/white keybed targets
                hState.fingers = [];
                hState.archLift = 4.0;
                const dt = this._lastDt || 0.016;
                const restSlotU = isLeft
                    ? { 5: -2.0 * whiteNormW, 4: -1.0 * whiteNormW, 3: 0, 2: 1.0 * whiteNormW, 1: 2.05 * whiteNormW }
                    : { 1: -2.05 * whiteNormW, 2: -1.0 * whiteNormW, 3: 0, 4: 1.0 * whiteNormW, 5: 2.0 * whiteNormW };
                const restTipDepth = { 1: 0.72, 2: 0.54, 3: 0.50, 4: 0.54, 5: 0.60 };

                def.fingerOrder.forEach((fNum, slotIdx) => {
                    const activeNote = hState.activeFingers[fNum];
                    const upcomingNote = hState.upcomingFingers && hState.upcomingFingers[fNum];
                    const spread = def.spreadOffsets[slotIdx];
                    const lenFactor = def.lengthFactors[fNum];
                    const isThumb = (fNum === 1);

                    // Metacarpal arch + yaw rotation on knuckle base
                    const archLift = (1.0 - Math.abs(spread) * 0.22) * 4.0;
                    const localKX = spread * (palmW * 0.23);
                    const localKY = isThumb ? palmH * 0.06 : -palmH * 0.36 - archLift;
                    const splayVal = (hState.splays && hState.splays[fNum]) || 0;
                    const curlVal = (hState.curls && hState.curls[fNum]) || 0.38;
                    const rollVal = hState.roll || 0;
                    const kin = this._sampleFingerKinematics(fNum, curlVal, splayVal);

                    const knuckleX = palmX + localKX * cosY - localKY * sinY * 0.35;
                    const knuckleY = palmY + localKY * cosY + localKX * sinY * 0.35 - spread * rollVal * 6.0;

                    let targetTipU = Math.max(0.01, Math.min(0.99, wristU + (restSlotU[fNum] + kin.latOffset * 0.08) * cosY + sinY * 0.012));
                    let targetTipDepth = Math.max(0.28, Math.min(0.95, wristDepth - (1.0 - restTipDepth[fNum]) * 0.58 * lenFactor));
                    let targetLift = 1.0; // 1.0 = arched resting clearance, 0.0 = depressed key strike
                    let strikeDepth = 0;

                    if (activeNote && this.keyGeometry[activeNote.midi]) {
                        const kg = this.keyGeometry[activeNote.midi];
                        const useGap = !kg.isBlack && hasBlackInChord && !isThumb;
                        targetTipU = useGap && typeof kg.gapU === 'number' ? kg.gapU : kg.uCenter;
                        targetTipDepth = kg.isBlack ? 0.39 : (useGap ? 0.56 : 0.67);
                        targetLift = 0.0;
                        strikeDepth = 3.5;
                    } else if (upcomingNote && this.keyGeometry[upcomingNote.midi]) {
                        const kg = this.keyGeometry[upcomingNote.midi];
                        const useGap = !kg.isBlack && hasBlackInChord && !isThumb;
                        const hoverU = useGap && typeof kg.gapU === 'number' ? kg.gapU : kg.uCenter;
                        const hoverDepth = kg.isBlack ? 0.42 : (useGap ? 0.58 : 0.69);
                        const blend = Math.max(0, Math.min(1, 1 - (upcomingNote.timeUntilStrike / 0.85)));
                        targetTipU = targetTipU + (hoverU - targetTipU) * blend * 0.85;
                        targetTipDepth = targetTipDepth + (hoverDepth - targetTipDepth) * blend * 0.85;
                        targetLift = 1.15 - 0.5 * blend; // slight pre-strike anticipation lift
                    }

                    const fSpring = hState.fingerSprings && hState.fingerSprings[fNum];
                    const smoothU = fSpring ? this._stepSpring(fSpring.u, targetTipU, 24.0, dt) : targetTipU;
                    const smoothDepth = fSpring ? this._stepSpring(fSpring.depth, targetTipDepth, 22.0, dt) : targetTipDepth;
                    const smoothLift = fSpring ? this._stepSpring(fSpring.lift, targetLift, 26.0, dt) : targetLift;

                    const tipPt = this.projectKeybedPoint(smoothU, smoothDepth);
                    const tipX = tipPt.x;
                    const tipY = tipPt.y + (activeNote ? 2.5 : -(7.5 + kin.dropY * 14) * smoothLift);

                    // Proximal (PIP) joint lifted vertically for natural arched clearance over neighbouring keys
                    const pipArch = activeNote ? (3.5 + curlVal * 4.5) : (9.5 + curlVal * 5.0);
                    const pipX = knuckleX + (tipX - knuckleX) * 0.48 + (isThumb ? (isLeft ? 3.5 : -3.5) : splayVal * 2.5);
                    const pipY = knuckleY + (tipY - knuckleY) * 0.48 - pipArch;

                    hState.fingers.push({
                        fNum,
                        active: Boolean(activeNote),
                        tipU: smoothU,
                        tipDepth: smoothDepth,
                        proximalX: knuckleX,
                        proximalY: knuckleY,
                        pipX,
                        pipY,
                        tipX,
                        tipY,
                        strikeDepth,
                        archLift
                    });

                    if (!webglReady) {
                        const fingerWidth = isThumb ? Math.max(9.2, palmW * 0.19) : Math.max(7.6, palmW * 0.155);

                        // Finger 3D cylinder shadow border
                        ctx.strokeStyle = '#6A4B39';
                        ctx.lineWidth = fingerWidth + 2.2;
                        ctx.lineCap = 'round';
                        ctx.lineJoin = 'round';
                        ctx.beginPath();
                        ctx.moveTo(knuckleX, knuckleY);
                        ctx.quadraticCurveTo(pipX, pipY, tipX, tipY);
                        ctx.stroke();

                        // Finger 3D warm skin fill
                        ctx.strokeStyle = activeNote ? '#DCAC91' : '#C4987E';
                        ctx.lineWidth = fingerWidth;
                        ctx.beginPath();
                        ctx.moveTo(knuckleX, knuckleY);
                        ctx.quadraticCurveTo(pipX, pipY, tipX, tipY);
                        ctx.stroke();

                        // Finger dorsal highlight ridge
                        ctx.strokeStyle = 'rgba(248, 218, 198, 0.38)';
                        ctx.lineWidth = fingerWidth * 0.36;
                        ctx.beginPath();
                        ctx.moveTo(knuckleX, knuckleY);
                        ctx.quadraticCurveTo(pipX, pipY, tipX, tipY);
                        ctx.stroke();

                        // Subtle PIP knuckle crease line
                        ctx.strokeStyle = 'rgba(106, 75, 57, 0.42)';
                        ctx.lineWidth = 1.0;
                        ctx.beginPath();
                        ctx.moveTo(pipX - fingerWidth * 0.28, pipY);
                        ctx.lineTo(pipX + fingerWidth * 0.28, pipY);
                        ctx.stroke();

                        // Anatomically shaped fingernail plate at fingertip
                        ctx.fillStyle = activeNote ? '#F6D9C6' : 'rgba(238, 206, 188, 0.72)';
                        ctx.beginPath();
                        ctx.arc(tipX, tipY + 1, fingerWidth * 0.34, 0, Math.PI * 2);
                        ctx.fill();
                    }
                });

                if (!webglReady) {
                    // 3. Sculpted 3D Dorsal Palm Body
                let palmSkin = '#BD9278';
                if (typeof ctx.createRadialGradient === 'function') {
                    const pGrad = ctx.createRadialGradient(
                        palmX - palmW * 0.1,
                        palmY - palmH * 0.1,
                        palmW * 0.08,
                        palmX,
                        palmY,
                        palmW * 0.72
                    );
                    pGrad.addColorStop(0, '#D4AA90');
                    pGrad.addColorStop(0.65, '#B68B72');
                    pGrad.addColorStop(1, '#7D5B47');
                    palmSkin = pGrad;
                }

                ctx.fillStyle = palmSkin;
                ctx.strokeStyle = '#6E4F3D';
                ctx.lineWidth = 1.4;
                ctx.beginPath();
                if (typeof ctx.ellipse === 'function') {
                    ctx.ellipse(palmX, palmY, palmW * 0.54, palmH * 0.46, (isLeft ? -0.08 : 0.08) + yaw * 0.8, 0, Math.PI * 2);
                } else {
                    ctx.arc(palmX, palmY, palmW * 0.5, 0, Math.PI * 2);
                }
                ctx.fill();
                ctx.stroke();

                // 4. Cylindrical 3D Wrist Cuff (rotates with yaw)
                const wristW = palmW * 0.38;
                const wristH = palmH * 0.22;
                const wristX = palmX + (isLeft ? -3 : 3) - sinY * palmH * 0.35;
                const wristY = palmY + palmH * 0.44 * cosY;

                ctx.fillStyle = '#A67C64';
                ctx.fillRect(wristX - wristW, wristY - wristH * 0.6, wristW * 2, wristH * 0.8);

                // Wrist cross-section cap
                ctx.fillStyle = '#755442';
                ctx.strokeStyle = '#593E2F';
                ctx.lineWidth = 1.2;
                ctx.beginPath();
                if (typeof ctx.ellipse === 'function') {
                    ctx.ellipse(wristX, wristY + wristH * 0.2, wristW, wristH * 0.48, 0, 0, Math.PI * 2);
                } else {
                    ctx.arc(wristX, wristY, wristW * 0.6, 0, Math.PI * 2);
                }
                    ctx.fill();
                    ctx.stroke();

                    ctx.restore();
                }
            });
        }
    }

    global.PianoStudio3D = PianoStudio3D;
    global.CAMERA_PRESETS_3D = CAMERA_PRESETS;
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = { PianoStudio3D, CAMERA_PRESETS };
    }
})(typeof window !== 'undefined' ? window : global);
