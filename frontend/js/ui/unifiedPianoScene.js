/**
 * unifiedPianoScene.js
 *
 * Unified Three.js 3D Piano Scene for HotChords PianoStudio3D.
 * Renders the 88-key physical piano (52 white + 36 black keys from build88KeyLayout()),
 * cabinet, fallboard, key depression, emissive highlights, radial fallboard glows,
 * 3D falling note bars, centered chord labels, articulated RiggedPianoHand hands,
 * single PerspectiveCamera preset controller, and Raycaster click-to-audition
 * inside ONE shared WebGL scene.
 */

import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { build88KeyLayout, RiggedPianoHand } from '/js/ui/pianoHandRig.js';

const CAMERA_CONFIGS = {
    performer: { tiltDeg: 38.0, fov: 42, targetScreenY: 0.785, nearWidthRatio: 0.90 },
    overhead:  { tiltDeg: 76.0, fov: 35, targetScreenY: 0.614, nearWidthRatio: 0.91 },
    closeup:   { tiltDeg: 20.0, fov: 48, targetScreenY: 0.712, nearWidthRatio: 0.94 },
};

const HAND_COLORS = {
    left:  new THREE.Color(0x7B64FF),
    right: new THREE.Color(0xFF5A7A),
};

const SOURCE_COLORS = {
    melody:        new THREE.Color(0xF7F4EF),
    accompaniment: new THREE.Color(0x9696A2),
    chord:         new THREE.Color(0x6C6C78),
};

function createRadialGlowTexture() {
    const size = 128;
    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d');
    const grad = ctx.createRadialGradient(size / 2, size / 2, 2, size / 2, size / 2, size / 2);
    grad.addColorStop(0.0, 'rgba(255,255,255,0.95)');
    grad.addColorStop(0.35, 'rgba(255,255,255,0.45)');
    grad.addColorStop(1.0, 'rgba(255,255,255,0.0)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, size, size);
    const tex = new THREE.CanvasTexture(canvas);
    tex.needsUpdate = true;
    return tex;
}

export class UnifiedPianoScene {
    constructor(container, options = {}) {
        this.container = container;
        this.onKeyClick = options.onKeyClick || null;
        this.onContextLost = options.onContextLost || null;
        this.keyLayout = build88KeyLayout();

        this.ready = false;
        this.handsReady = false;
        this.disposed = false;
        this.showHands = options.showHands !== undefined ? Boolean(options.showHands) : true;
        this.showColourKey = options.showColourKey !== undefined ? Boolean(options.showColourKey) : true;
        this.layerVisibility = { melody: true, instrumental: true, chords: true };
        this.lookAheadSec = options.lookAheadSec || 3.2;

        this.cameraPreset = options.cameraPreset || 'performer';
        const initCam = CAMERA_CONFIGS[this.cameraPreset] || CAMERA_CONFIGS.performer;
        this._camCurrent = { ...initCam };
        this._camFrom = { ...initCam };
        this._camTo = { ...initCam };
        this._camAnimStart = 0;
        this._camAnimDuration = 400;
        this._camAnimating = false;
        this._camRafId = null;

        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x101012);

        this.camera = new THREE.PerspectiveCamera(initCam.fov, 16 / 9, 0.02, 12);

        this.renderer = new THREE.WebGLRenderer({
            alpha: false,
            antialias: true,
            powerPreference: 'high-performance',
        });
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
        this.renderer.toneMappingExposure = 1.06;

        this.canvas = this.renderer.domElement;
        this.canvas.className = 'piano-studio-3d-webgl';
        this.canvas.style.position = 'absolute';
        this.canvas.style.inset = '0';
        this.canvas.style.width = '100%';
        this.canvas.style.height = '100%';
        this.canvas.style.display = 'block';
        this.canvas.style.zIndex = '2';
        this.container.appendChild(this.canvas);

        this.raycaster = new THREE.Raycaster();
        this.pointerNdc = new THREE.Vector2();

        this._keyMeshes = [];
        this._keyMeshByMidi = {};
        this._glowSprites = {};
        this._notePool = [];
        this._activeNoteCount = 0;
        this._chordSprites = [];
        this._chordTexCache = new Map();

        this.leftHand = null;
        this.rightHand = null;
        this._lastRenderMs = null;
        this._lastTimeSec = 0;
        this._lastState = null;
        this._auditionedMidi = null;
        this._auditionUntilMs = 0;

        this._setupLights();
        this._buildPianoCabinetAndKeys();
        this._buildFallingNotePool();
        this._bindEvents();
        this.resize();
        this._applyCamera(this._camCurrent);
        this.ready = true;
        this._loadHands();
    }

    _setupLights() {
        this.scene.add(new THREE.HemisphereLight(0xe2e8f0, 0x18181b, 0.85));

        const keyLight = new THREE.DirectionalLight(0xfff1e6, 2.35);
        keyLight.position.set(0.32, 1.05, 0.58);
        keyLight.castShadow = true;
        keyLight.shadow.mapSize.set(2048, 2048);
        keyLight.shadow.camera.left = -0.82;
        keyLight.shadow.camera.right = 0.82;
        keyLight.shadow.camera.top = 0.55;
        keyLight.shadow.camera.bottom = -0.55;
        keyLight.shadow.camera.near = 0.2;
        keyLight.shadow.camera.far = 3.0;
        keyLight.shadow.bias = -0.0004;
        this.scene.add(keyLight);

        const rimLight = new THREE.DirectionalLight(0x93c5fd, 0.75);
        rimLight.position.set(-0.55, 0.65, -0.75);
        this.scene.add(rimLight);
    }

    _buildPianoCabinetAndKeys() {
        const totalW = this.keyLayout.totalWidth;
        const cabinetMat = new THREE.MeshStandardMaterial({
            color: 0x0b0b0e,
            roughness: 0.34,
            metalness: 0.14,
        });
        const feltMat = new THREE.MeshStandardMaterial({
            color: 0x5c1118,
            roughness: 0.9,
            metalness: 0.0,
        });

        // Piano cabinet root group (pianoBody -> frontFascia -> hotFixLogoGroup)
        this.pianoBody = new THREE.Group();
        this.pianoBody.name = 'pianoBody';
        this.scene.add(this.pianoBody);

        // Keybed chassis
        const bed = new THREE.Mesh(
            new THREE.BoxGeometry(totalW + 0.072, 0.036, 0.190),
            cabinetMat
        );
        bed.position.set(0, -0.022, 0.002);
        bed.receiveShadow = true;
        this.pianoBody.add(bed);

        // Front keyslip rail
        const frontLip = new THREE.Mesh(
            new THREE.BoxGeometry(totalW + 0.072, 0.024, 0.016),
            cabinetMat
        );
        frontLip.position.set(0, -0.006, 0.084);
        frontLip.receiveShadow = true;
        this.pianoBody.add(frontLip);

        // Rear fallboard (upper front fascia)
        const fallboard = new THREE.Mesh(
            new THREE.BoxGeometry(totalW + 0.072, 0.048, 0.024),
            cabinetMat
        );
        fallboard.name = 'frontFascia';
        fallboard.position.set(0, 0.018, -0.088);
        fallboard.castShadow = true;
        fallboard.receiveShadow = true;
        this.pianoBody.add(fallboard);

        // Subtle red keybed felt strip along fallboard base
        const felt = new THREE.Mesh(
            new THREE.BoxGeometry(totalW + 0.006, 0.004, 0.006),
            feltMat
        );
        felt.position.set(0, 0.012, -0.074);
        this.pianoBody.add(felt);

        // Physical champagne-gold HotFix brand imprint attached to frontFascia
        this._buildHotFixBrandMark(fallboard, totalW);

        // Left & Right cheek blocks
        const cheekGeo = new THREE.BoxGeometry(0.034, 0.044, 0.194);
        const leftCheek = new THREE.Mesh(cheekGeo, cabinetMat);
        leftCheek.position.set(-totalW * 0.5 - 0.019, 0.005, 0.002);
        leftCheek.castShadow = true;
        leftCheek.receiveShadow = true;
        this.pianoBody.add(leftCheek);

        const rightCheek = new THREE.Mesh(cheekGeo, cabinetMat);
        rightCheek.position.set(totalW * 0.5 + 0.019, 0.005, 0.002);
        rightCheek.castShadow = true;
        rightCheek.receiveShadow = true;
        this.pianoBody.add(rightCheek);

        // Shared geometries for white and black keys
        const sampleWhite = this.keyLayout.keys[21];
        const sampleBlack = this.keyLayout.keys[22];
        const whiteGeo = new THREE.BoxGeometry(sampleWhite.width, sampleWhite.height, sampleWhite.length);
        const blackGeo = new THREE.BoxGeometry(sampleBlack.width, sampleBlack.height, sampleBlack.length);

        const glowTex = createRadialGlowTexture();

        for (let midi = 21; midi <= 108; midi++) {
            const k = this.keyLayout.keys[midi];
            if (!k) continue;

            const baseColor = k.isBlack ? 0x16161b : 0xf2efe9;
            const mat = new THREE.MeshStandardMaterial({
                color: baseColor,
                roughness: k.isBlack ? 0.26 : 0.22,
                metalness: k.isBlack ? 0.10 : 0.02,
                emissive: 0x000000,
                emissiveIntensity: 0.0,
            });

            const mesh = new THREE.Mesh(k.isBlack ? blackGeo : whiteGeo, mat);
            mesh.position.set(k.x, k.y, k.z);
            mesh.castShadow = k.isBlack;
            mesh.receiveShadow = true;
            mesh.userData = {
                midi,
                isBlack: k.isBlack,
                restY: k.y,
                baseColor,
                press: 0,
            };

            this.scene.add(mesh);
            this._keyMeshes.push(mesh);
            this._keyMeshByMidi[midi] = mesh;

            // Pooled radial glow sprite at rear strike line
            const spriteMat = new THREE.SpriteMaterial({
                map: glowTex,
                color: 0xffffff,
                transparent: true,
                opacity: 0.0,
                blending: THREE.AdditiveBlending,
                depthWrite: false,
            });
            const sprite = new THREE.Sprite(spriteMat);
            sprite.position.set(k.x, 0.024, -0.072);
            sprite.scale.set(0.068, 0.068, 1);
            sprite.visible = false;
            this.scene.add(sprite);
            this._glowSprites[midi] = sprite;
        }
    }

    _buildFallingNotePool() {
        // Shared unit box geometry scaled per-note without reallocating geometry
        this._unitNoteGeo = new THREE.BoxGeometry(1, 1, 1);
        this._noteMaterials = {
            melody: new THREE.MeshStandardMaterial({ color: SOURCE_COLORS.melody, roughness: 0.28, metalness: 0.05 }),
            accompaniment: new THREE.MeshStandardMaterial({ color: SOURCE_COLORS.accompaniment, roughness: 0.35, metalness: 0.08 }),
            chord: new THREE.MeshStandardMaterial({ color: SOURCE_COLORS.chord, roughness: 0.40, metalness: 0.08 }),
        };

        const poolSize = 180;
        for (let i = 0; i < poolSize; i++) {
            const mesh = new THREE.Mesh(this._unitNoteGeo, this._noteMaterials.melody);
            mesh.visible = false;
            mesh.castShadow = false;
            mesh.receiveShadow = false;
            this.scene.add(mesh);
            this._notePool.push(mesh);
        }

        // Pool of 12 chord label sprites (initialized with valid texture so USE_MAP compiles)
        const placeholderTex = this._getChordTexture(' ');
        for (let i = 0; i < 12; i++) {
            const mat = new THREE.SpriteMaterial({ map: placeholderTex, transparent: true, depthWrite: false, depthTest: true });
            const sp = new THREE.Sprite(mat);
            sp.renderOrder = 10;
            sp.visible = false;
            this.scene.add(sp);
            this._chordSprites.push(sp);
        }
    }

    async _loadHands() {
        try {
            const loader = new GLTFLoader();
            const [leftGltf, rightGltf] = await Promise.all([
                loader.loadAsync('/js/assets/hands/hand_left.glb?v=6'),
                loader.loadAsync('/js/assets/hands/hand_right.glb?v=6'),
            ]);
            if (this.disposed) return;
            this.leftHand = new RiggedPianoHand('left', leftGltf.scene, this.keyLayout);
            this.rightHand = new RiggedPianoHand('right', rightGltf.scene, this.keyLayout);
            this.scene.add(this.leftHand.root);
            this.scene.add(this.rightHand.root);
            this.handsReady = true;
            if (this._lastState) {
                this.renderState(this._lastState);
            } else {
                this.renderer.render(this.scene, this.camera);
            }
        } catch (err) {
            console.warn('[UnifiedPianoScene] Hand GLB load failed:', err);
        }
    }

    _bindEvents() {
        this._onPointerDown = (e) => {
            if (!this.canvas || !this.onKeyClick) return;
            const rect = this.canvas.getBoundingClientRect();
            if (rect.width <= 0 || rect.height <= 0) return;
            this.pointerNdc.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
            this.pointerNdc.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
            this.raycaster.setFromCamera(this.pointerNdc, this.camera);
            const hits = this.raycaster.intersectObjects(this._keyMeshes, false);
            if (hits.length > 0) {
                const midi = hits[0].object.userData.midi;
                if (typeof midi === 'number') {
                    this._auditionedMidi = midi;
                    this._auditionUntilMs = performance.now() + 260;
                    this.onKeyClick(midi);
                    if (this._lastState) this.renderState(this._lastState);
                }
            }
        };
        this.canvas.addEventListener('pointerdown', this._onPointerDown);

        this._onWebGLContextLost = (e) => {
            e.preventDefault();
            if (typeof this.onContextLost === 'function') this.onContextLost();
        };
        this.canvas.addEventListener('webglcontextlost', this._onWebGLContextLost);
    }

    resize() {
        if (this.disposed || !this.container) return;
        const w = this.container.clientWidth || 1040;
        const h = this.container.clientHeight || 440;
        if (w <= 0 || h <= 0) return;
        this.renderer.setSize(w, h, false);
        this._applyCamera(this._camCurrent);
        if (this.ready) {
            this.renderer.render(this.scene, this.camera);
        }
    }

    _applyCamera(cfg) {
        const w = this.container.clientWidth || 1040;
        const h = this.container.clientHeight || 440;
        const aspect = w / Math.max(1, h);

        const fovRad = (cfg.fov * Math.PI) / 180;
        const tiltRad = (cfg.tiltDeg * Math.PI) / 180;
        const halfVisibleW = (this.keyLayout.totalWidth * 0.5) / Math.max(0.35, cfg.nearWidthRatio);
        const halfVisibleH = halfVisibleW / Math.max(0.4, aspect);
        const dist = halfVisibleH / Math.tan(fovRad * 0.5);

        this.camera.fov = cfg.fov;
        this.camera.aspect = aspect;
        this.camera.position.set(0.0, dist * Math.sin(tiltRad), dist * Math.cos(tiltRad));
        this.camera.lookAt(0.0, 0.0, 0.0);

        const offsetY = -(cfg.targetScreenY - 0.5) * h;
        this.camera.setViewOffset(w, h, 0, offsetY, w, h);
        this.camera.updateProjectionMatrix();
    }

    setCameraPreset(presetName) {
        const target = CAMERA_CONFIGS[presetName];
        if (!target) return false;
        this.cameraPreset = presetName;
        this._camFrom = { ...this._camCurrent };
        this._camTo = { ...target };
        this._camAnimStart = performance.now();
        this._camAnimating = true;

        if (!this._camRafId) {
            const tick = (now) => {
                if (this.disposed || !this._camAnimating) {
                    this._camRafId = null;
                    return;
                }
                const raw = Math.min(1, (now - this._camAnimStart) / this._camAnimDuration);
                const ease = 1 - Math.pow(1 - raw, 3);
                this._camCurrent = {
                    tiltDeg: this._camFrom.tiltDeg + (this._camTo.tiltDeg - this._camFrom.tiltDeg) * ease,
                    fov: this._camFrom.fov + (this._camTo.fov - this._camFrom.fov) * ease,
                    targetScreenY: this._camFrom.targetScreenY + (this._camTo.targetScreenY - this._camFrom.targetScreenY) * ease,
                    nearWidthRatio: this._camFrom.nearWidthRatio + (this._camTo.nearWidthRatio - this._camFrom.nearWidthRatio) * ease,
                };
                this._applyCamera(this._camCurrent);
                this.renderer.render(this.scene, this.camera);
                if (raw >= 1) {
                    this._camAnimating = false;
                    this._camRafId = null;
                } else {
                    this._camRafId = requestAnimationFrame(tick);
                }
            };
            this._camRafId = requestAnimationFrame(tick);
        }
        return true;
    }

    setShowHands(visible) {
        this.showHands = Boolean(visible);
        if (this.leftHand) this.leftHand.root.visible = this.showHands;
        if (this.rightHand) this.rightHand.root.visible = this.showHands;
        if (this.ready) this.renderer.render(this.scene, this.camera);
    }

    setShowColourKey(visible) {
        this.showColourKey = Boolean(visible);
        if (this._lastState) this.renderState(this._lastState);
    }

    setLayerVisibility(layers) {
        if (layers) Object.assign(this.layerVisibility, layers);
        if (this._lastState) this.renderState(this._lastState);
    }

    _getChordTexture(label) {
        if (this._chordTexCache.has(label)) return this._chordTexCache.get(label);
        const canvas = document.createElement('canvas');
        canvas.width = 192;
        canvas.height = 72;
        const ctx = canvas.getContext('2d');
        ctx.font = '700 40px -apple-system, BlinkMacSystemFont, "Inter", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillStyle = 'rgba(245, 243, 240, 0.94)';
        ctx.fillText(label, 96, 36);
        const tex = new THREE.CanvasTexture(canvas);
        tex.needsUpdate = true;
        this._chordTexCache.set(label, tex);
        return tex;
    }

    renderState(state) {
        if (!this.ready || this.disposed) return;
        this._lastState = state;

        const nowMs = performance.now();
        const dt = this._lastRenderMs === null ? 0.016 : Math.max(0.004, Math.min(0.05, (nowMs - this._lastRenderMs) / 1000));
        this._lastRenderMs = nowMs;

        const t = state.currentTime || 0;
        const seekDelta = Math.abs(t - this._lastTimeSec);
        const snap = seekDelta > 0.15;
        this._lastTimeSec = t;

        const activeNotes = state.activeNotes || [];
        const upcomingNotes = state.upcomingNotes || [];
        const handFilter = state.handFilter || 'both';

        // 1. Update 88 physical key depressions, emissive colors & radial glows
        const activeByMidi = {};
        for (let i = 0; i < activeNotes.length; i++) {
            const n = activeNotes[i];
            if (!activeByMidi[n.midi]) activeByMidi[n.midi] = n;
        }
        if (this._auditionedMidi !== null && nowMs < this._auditionUntilMs && !activeByMidi[this._auditionedMidi]) {
            activeByMidi[this._auditionedMidi] = { midi: this._auditionedMidi, hand: this._auditionedMidi < 60 ? 'left' : 'right' };
        }

        const keyAlpha = snap ? 1.0 : (1.0 - Math.exp(-26.0 * dt));
        for (let i = 0; i < this._keyMeshes.length; i++) {
            const mesh = this._keyMeshes[i];
            const ud = mesh.userData;
            const act = activeByMidi[ud.midi];
            const targetPress = act ? 1.0 : 0.0;
            ud.press += (targetPress - ud.press) * keyAlpha;

            // 8 mm realistic key depression + sync live world-space key surface height for fingertip IK
            mesh.position.y = ud.restY - ud.press * 0.008;
            const layoutKey = this.keyLayout.keys[ud.midi];
            if (layoutKey) {
                layoutKey.targetY = mesh.position.y + (ud.isBlack ? 0.0065 : 0.010);
            }

            const sprite = this._glowSprites[ud.midi];
            if (act && this.showColourKey) {
                const col = HAND_COLORS[act.hand === 'left' ? 'left' : 'right'];
                mesh.material.color.copy(col);
                mesh.material.emissive.copy(col);
                mesh.material.emissiveIntensity = 0.42;
                if (sprite) {
                    sprite.material.color.copy(col);
                    sprite.material.opacity = 0.65;
                    sprite.visible = true;
                }
            } else {
                mesh.material.color.setHex(ud.baseColor);
                mesh.material.emissive.setHex(0x000000);
                mesh.material.emissiveIntensity = 0.0;
                if (sprite) {
                    sprite.material.opacity = 0.0;
                    sprite.visible = false;
                }
            }
        }

        // 2. Update 3D falling note bars (aligned directly with build88KeyLayout().keys[midi])
        const noteSpeed = 0.42; // meters per second along -Z into fallboard
        const strikeZ = -0.074;
        const maxBars = this._notePool.length;
        let poolIdx = 0;

        const allBars = [...activeNotes, ...upcomingNotes];
        for (let i = 0; i < allBars.length && poolIdx < maxBars; i++) {
            const n = allBars[i];
            const k = this.keyLayout.keys[n.midi];
            if (!k) continue;

            const src = (n.source || 'melody').toLowerCase();
            if (src === 'melody' && !this.layerVisibility.melody) continue;
            if ((src === 'accompaniment' || src === 'instrumental') && !this.layerVisibility.instrumental) continue;
            if (src === 'chord' && !this.layerVisibility.chords) continue;

            const nStart = n.start ?? t;
            const nEnd = n.end ?? (nStart + 0.35);
            if (nEnd < t || nStart > t + this.lookAheadSec) continue;

            const zFront = strikeZ - Math.max(0, nStart - t) * noteSpeed;
            const zBack = strikeZ - Math.min(this.lookAheadSec, Math.max(0, nEnd - t)) * noteSpeed;
            const len = Math.max(0.012, zFront - zBack);
            const zCenter = (zFront + zBack) * 0.5;

            const bar = this._notePool[poolIdx++];
            bar.material = this._noteMaterials[src] || this._noteMaterials.accompaniment;
            bar.scale.set(k.width * 0.86, 0.012, len);
            bar.position.set(k.x, 0.022, zCenter);
            bar.visible = true;
        }
        for (let i = poolIdx; i < this._activeNoteCount; i++) {
            this._notePool[i].visible = false;
        }
        this._activeNoteCount = poolIdx;

        // 3. Update centered chord labels in the falling-note highway (strictly behind piano fascia)
        const chords = state.chords || [];
        let chIdx = 0;
        let lastChordStart = -999;
        for (let i = 0; i < chords.length && chIdx < this._chordSprites.length; i++) {
            const c = chords[i];
            const cStart = c.start ?? 0;
            // Keep chord labels strictly in the highway (z <= -0.164) so they never overlap the piano fascia
            if (cStart < t + 0.22 || cStart > t + this.lookAheadSec) continue;
            if (cStart - lastChordStart < 0.45) continue;
            const label = c.chord || c.symbol || c.label;
            if (!label || label === 'N' || label === 'NC') continue;
            lastChordStart = cStart;

            const zPos = strikeZ - Math.max(0, cStart - t) * noteSpeed;
            // Center horizontally over matching LH/chord notes near cStart
            let xSum = 0;
            let xCount = 0;
            for (let j = 0; j < allBars.length; j++) {
                const bn = allBars[j];
                if (bn.hand === 'left' && Math.abs((bn.start ?? 0) - cStart) < 0.25 && this.keyLayout.keys[bn.midi]) {
                    xSum += this.keyLayout.keys[bn.midi].x;
                    xCount++;
                }
            }
            const xPos = xCount > 0 ? (xSum / xCount) : -0.22;

            const sp = this._chordSprites[chIdx++];
            sp.material.map = this._getChordTexture(label);
            sp.material.needsUpdate = true;
            sp.position.set(xPos, 0.048, zPos);
            sp.scale.set(0.11, 0.042, 1);
            sp.visible = true;
        }
        for (let i = chIdx; i < this._chordSprites.length; i++) {
            this._chordSprites[i].visible = false;
        }

        // 4. Update articulated 3D Left & Right hands in the exact same scene
        if (this.handsReady && this.leftHand && this.rightHand) {
            const showL = this.showHands && (handFilter === 'both' || handFilter === 'left');
            const showR = this.showHands && (handFilter === 'both' || handFilter === 'right');
            this.leftHand.root.visible = showL;
            this.rightHand.root.visible = showR;

            if (showL) {
                const actL = activeNotes.filter(n => n.hand === 'left');
                const upcL = upcomingNotes.filter(n => n.hand === 'left' && (n.timeUntilStrike ?? 1) <= 0.65);
                this.leftHand.solveForNotes(actL, upcL);
                this.leftHand.update(dt, snap);
            }
            if (showR) {
                const actR = activeNotes.filter(n => n.hand === 'right');
                const upcR = upcomingNotes.filter(n => n.hand === 'right' && (n.timeUntilStrike ?? 1) <= 0.65);
                this.rightHand.solveForNotes(actR, upcR);
                this.rightHand.update(dt, snap);
            }
        }

        this.renderer.render(this.scene, this.camera);
    }

    _buildHotFixBrandMark(frontFascia, totalW) {
        if (!frontFascia || this.hotFixLogoGroup) return;

        // Fixed local coordinates on the horizontal top-facing surface of frontFascia
        // frontFascia BoxGeometry is (totalW + 0.072, 0.048, 0.024), so top surface is at local y = +0.024
        const logoW = 0.21;
        const logoH = 0.021;
        const localX = -totalW * 0.5 + 0.145;
        const localY = 0.0243;
        const localZ = 0.0;

        const group = new THREE.Group();
        group.name = 'hotFixLogoGroup';
        group.position.set(localX, localY, localZ);
        group.rotation.set(-Math.PI / 2, 0, 0);

        if (typeof document !== 'undefined') {
            const canvas = document.createElement('canvas');
            canvas.width = 1536;
            canvas.height = 192;
            const tex = new THREE.CanvasTexture(canvas);
            tex.colorSpace = THREE.SRGBColorSpace;
            tex.anisotropy = 4;
            this._brandTex = tex;

            const svgMarkup = `
                <svg xmlns="http://www.w3.org/2000/svg" width="1536" height="192" viewBox="0 0 1536 192">
                    <defs>
                        <linearGradient id="champagneGold" x1="0%" y1="0%" x2="0%" y2="100%">
                            <stop offset="0%" stop-color="#F6E2A0"/>
                            <stop offset="42%" stop-color="#DFB958"/>
                            <stop offset="78%" stop-color="#A88024"/>
                            <stop offset="100%" stop-color="#E6C56A"/>
                        </linearGradient>
                    </defs>
                    <g fill="url(#champagneGold)">
                        <rect x="64" y="76" width="12" height="40" rx="4"/>
                        <rect x="86" y="58" width="12" height="76" rx="4"/>
                        <rect x="108" y="42" width="12" height="108" rx="4"/>
                        <rect x="130" y="64" width="12" height="64" rx="4"/>
                        <rect x="152" y="80" width="12" height="32" rx="4"/>
                    </g>
                    <text
                        x="196"
                        y="130"
                        fill="url(#champagneGold)"
                        font-family="'Helvetica Neue', 'Inter', Arial, sans-serif"
                        font-size="116"
                        font-weight="600"
                        font-style="italic"
                        letter-spacing="8"
                    >HotFix</text>
                </svg>
            `.trim();

            const img = new Image();
            img.onload = () => {
                if (this.disposed) return;
                const ctx = canvas.getContext('2d');
                if (ctx) {
                    ctx.clearRect(0, 0, canvas.width, canvas.height);
                    ctx.shadowColor = 'rgba(0, 0, 0, 0.85)';
                    ctx.shadowBlur = 3;
                    ctx.shadowOffsetX = 0;
                    ctx.shadowOffsetY = 2;
                    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                    tex.needsUpdate = true;
                    if (this.ready && this.renderer && this.scene && this.camera) {
                        this.renderer.render(this.scene, this.camera);
                    }
                }
            };
            img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svgMarkup);

            const imprintMat = new THREE.MeshStandardMaterial({
                map: tex,
                transparent: true,
                alphaTest: 0.05,
                roughness: 0.28,
                metalness: 0.84,
                emissive: new THREE.Color(0x3a2a08),
                emissiveMap: tex,
                emissiveIntensity: 0.34,
            });
            const logoMesh = new THREE.Mesh(
                new THREE.PlaneGeometry(logoW, logoH),
                imprintMat
            );
            logoMesh.name = 'logoMesh';
            group.add(logoMesh);
        }

        frontFascia.add(group);
        this.hotFixLogoGroup = group;
    }

    dispose() {
        this.disposed = true;
        if (this._camRafId) cancelAnimationFrame(this._camRafId);
        if (this.canvas) {
            this.canvas.removeEventListener('pointerdown', this._onPointerDown);
            this.canvas.removeEventListener('webglcontextlost', this._onWebGLContextLost);
            if (this.canvas.parentElement === this.container) {
                this.container.removeChild(this.canvas);
            }
        }
        if (this._brandTex) this._brandTex.dispose();
        this._chordTexCache.forEach(tex => tex.dispose());
        this.renderer.dispose();
    }
}

if (typeof window !== 'undefined') {
    window.UnifiedPianoScene = UnifiedPianoScene;
}
