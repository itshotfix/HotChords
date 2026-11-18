/**
 * pianoHandRig.js
 *
 * Standalone 3D Rigged Piano Hand Controller for HotChords Prototype.
 * Drives MIT-licensed WebXR 25-joint rigged GLB hands (hand_left.glb / hand_right.glb)
 * over a real 3D 88-key Three.js piano keyboard using bone-space flex axes,
 * wrist X/Z/Yaw optimization, and critically damped spring interpolation.
 */

import * as THREE from 'three';

export const FINGER_NAMES = {
    1: 'thumb',
    2: 'index-finger',
    3: 'middle-finger',
    4: 'ring-finger',
    5: 'pinky-finger',
};

const BLACK_KEY_PCS = new Set([1, 3, 6, 8, 10]);

export function build88KeyLayout() {
    const keys = {};
    const whiteWidth = 0.0235;   // 23.5 mm standard piano white key width
    const whiteLength = 0.148;   // 148 mm
    const whiteHeight = 0.020;
    const blackWidth = 0.0135;
    const blackLength = 0.095;
    const blackHeight = 0.013;

    // Count 52 white keys first so C4/middle is centered near X = 0
    let whiteCount = 0;
    for (let m = 21; m <= 108; m++) {
        if (!BLACK_KEY_PCS.has(m % 12)) whiteCount++;
    }
    const totalWidth = whiteCount * whiteWidth;
    const startX = -totalWidth * 0.5 + whiteWidth * 0.5;

    let wIdx = 0;
    const whiteCenters = {};
    for (let m = 21; m <= 108; m++) {
        const pc = m % 12;
        if (!BLACK_KEY_PCS.has(pc)) {
            const x = startX + wIdx * whiteWidth;
            whiteCenters[m] = x;
            keys[m] = {
                midi: m,
                isBlack: false,
                x,
                y: 0,
                z: 0,
                width: whiteWidth * 0.94,
                length: whiteLength,
                height: whiteHeight,
                // Ideal target point for finger pad on white key
                targetX: x,
                targetY: whiteHeight * 0.5,
                targetZ: whiteLength * 0.30, // front-middle of white key
            };
            wIdx++;
        }
    }

    for (let m = 21; m <= 108; m++) {
        const pc = m % 12;
        if (BLACK_KEY_PCS.has(pc)) {
            const prevX = whiteCenters[m - 1] ?? 0;
            const nextX = whiteCenters[m + 1] ?? prevX + whiteWidth;
            const x = (prevX + nextX) * 0.5;
            keys[m] = {
                midi: m,
                isBlack: true,
                x,
                y: whiteHeight * 0.5 + blackHeight * 0.5 - 0.002,
                z: -(whiteLength - blackLength) * 0.5,
                width: blackWidth,
                length: blackLength,
                height: blackHeight,
                targetX: x,
                targetY: whiteHeight * 0.5 + blackHeight - 0.002,
                targetZ: -0.015, // front third of black key
            };
        }
    }

    return { keys, whiteWidth, whiteLength, totalWidth };
}

export class RiggedPianoHand {
    constructor(side, gltfScene, keyLayout) {
        this.side = side; // 'left' | 'right'
        this.isLeft = side === 'left';
        this.root = new THREE.Group();
        this.model = gltfScene;
        this.keyLayout = keyLayout;
        this.bones = {};
        this.restQuats = {};
        this.flexAxes = {}; // local bone axis for positive curl (downward toward keys)
        this.splayAxes = {}; // local bone axis for lateral splay
        this.oppAxes = {}; // local bone axis for thumb palmar opposition/pronation

        // Spring states
        this.wristX = this.isLeft ? -0.22 : 0.22;
        this.wristY = 0.060;
        this.wristZ = 0.228;
        this.wristYaw = 0;
        this.wristPitch = -0.10;
        this.wristRoll = 0;

        this.fingerStates = {};
        for (let f = 1; f <= 5; f++) {
            this.fingerStates[f] = {
                curl: 0.28,
                targetCurl: 0.28,
                splay: 0.0,
                targetSplay: 0.0,
                press: 0.0,
                targetPress: 0.0,
            };
        }

        this._setupModel();
    }

    _setupModel() {
        // Warm matte-natural skin PBR material
        const skinMat = new THREE.MeshPhysicalMaterial({
            color: new THREE.Color(0xc49a7f),
            roughness: 0.54,
            metalness: 0.0,
            sheen: 0.20,
            sheenRoughness: 0.72,
            sheenColor: new THREE.Color(0xf4cbb4),
            clearcoat: 0.02,
            clearcoatRoughness: 0.65,
        });

        this.model.traverse((obj) => {
            if (obj.isMesh || obj.isSkinnedMesh) {
                obj.material = skinMat;
                obj.castShadow = true;
                obj.receiveShadow = true;
                obj.frustumCulled = false;
            }
            if (obj.isBone) {
                this.bones[obj.name] = obj;
            }
        });

        this.root.add(this.model);
        this.root.updateMatrixWorld(true);

        // Save rest quaternions
        Object.entries(this.bones).forEach(([name, bone]) => {
            this.restQuats[name] = bone.quaternion.clone();
        });

        this._skinMat = skinMat;
        this._calibrateOrientationAndAxes();
    }

    _boneWorldPos(name) {
        const b = this.bones[name];
        if (!b) return new THREE.Vector3();
        const v = new THREE.Vector3();
        b.getWorldPosition(v);
        return v;
    }

    _calibrateOrientationAndAxes() {
        // Inspect rest geometry: vector from wrist -> middle-finger-tip (forward),
        // and index-metacarpal -> pinky-metacarpal (across palm).
        const wristPos = this._boneWorldPos('wrist');
        const midTipPos = this._boneWorldPos('middle-finger-tip');
        const idxPos = this._boneWorldPos('index-finger-phalanx-proximal');
        const pkyPos = this._boneWorldPos('pinky-finger-phalanx-proximal');

        const forward = midTipPos.clone().sub(wristPos);
        const handLen = forward.length() || 0.18;
        // Scale hand to ~4.8-5.2 white keys wide (~15.8 cm wrist-to-mid-tip)
        const targetLen = 0.158;
        const scale = targetLen / handLen;
        this.model.scale.setScalar(scale);
        this.root.updateMatrixWorld(true);

        // Recompute in scaled space
        const wP = this._boneWorldPos('wrist');
        const mP = this._boneWorldPos('middle-finger-tip');
        const iP = this._boneWorldPos('index-finger-phalanx-proximal');
        const pP = this._boneWorldPos('pinky-finger-phalanx-proximal');

        const fwdDir = mP.clone().sub(wP).normalize();
        const acrossDir = pP.clone().sub(iP).normalize();
        // Palm down normal: right hand acrossDir (index->pinky) x fwdDir points UP or DOWN depending on handedness
        let palmDown = new THREE.Vector3().crossVectors(fwdDir, acrossDir).normalize();
        if (this.isLeft) palmDown.negate();

        // Build basis matrix to orient model so:
        //   fwdDir -> -Z (into keyboard), palmDown -> -Y (down toward keys)
        const sideDir = new THREE.Vector3().crossVectors(palmDown, fwdDir).normalize();
        const orthoPalmDown = new THREE.Vector3().crossVectors(fwdDir, sideDir).normalize();
        const srcBasis = new THREE.Matrix4().makeBasis(sideDir, orthoPalmDown.clone().negate(), fwdDir.clone().negate());
        const alignQuat = new THREE.Quaternion().setFromRotationMatrix(srcBasis).invert();
        this.model.quaternion.copy(alignQuat);

        // Center wrist at model origin
        this.root.updateMatrixWorld(true);
        const wristWorldAfter = this._boneWorldPos('wrist');
        this.model.position.sub(wristWorldAfter);
        this.root.updateMatrixWorld(true);

        // Compute exact local flex axis (to curl toward -Y = down) & splay axis for every joint
        const worldDown = new THREE.Vector3(0, -1, 0);
        const worldFwd = new THREE.Vector3(0, 0, -1);

        Object.entries(FINGER_NAMES).forEach(([fNumStr, base]) => {
            const fNum = Number(fNumStr);
            const joints = fNum === 1
                ? ['thumb-metacarpal', 'thumb-phalanx-proximal', 'thumb-phalanx-distal']
                : [`${base}-phalanx-proximal`, `${base}-phalanx-intermediate`, `${base}-phalanx-distal`];

            joints.forEach((jName, idx) => {
                const bone = this.bones[jName];
                if (!bone) return;
                const nextName = joints[idx + 1] || `${base}-tip`;
                const p0 = this._boneWorldPos(jName);
                const p1 = this._boneWorldPos(nextName);
                const segDir = p1.clone().sub(p0).normalize();

                // Right-hand-rule axis that rotates segDir downward toward worldDown: cross(worldDown, segDir)
                let worldFlexAxis = new THREE.Vector3().crossVectors(worldDown, segDir);
                if (worldFlexAxis.lengthSq() < 1e-5) {
                    worldFlexAxis = new THREE.Vector3(1, 0, 0);
                }
                worldFlexAxis.normalize();

                // Convert worldFlexAxis into bone's parent local space
                const parentQuat = new THREE.Quaternion();
                if (bone.parent) bone.parent.getWorldQuaternion(parentQuat);
                const localFlex = worldFlexAxis.clone().applyQuaternion(parentQuat.clone().invert()).normalize();
                this.flexAxes[jName] = localFlex;

                // Splay axis (yaw left/right around world Y)
                const localSplay = new THREE.Vector3(0, 1, 0).applyQuaternion(parentQuat.clone().invert()).normalize();
                this.splayAxes[jName] = localSplay;

                // Thumb opposition axis (palmar pronation toward palm & keys)
                if (jName === 'thumb-metacarpal') {
                    const worldOpp = new THREE.Vector3(0, 0.20, this.isLeft ? 1 : -1).normalize();
                    this.oppAxes[jName] = worldOpp.applyQuaternion(parentQuat.clone().invert()).normalize();
                }
            });
        });
    }

    setPose({ wristX, wristY, wristZ, wristYaw, wristPitch, wristRoll, fingers }) {
        if (wristX !== undefined) this.wristX = wristX;
        if (wristY !== undefined) this.wristY = wristY;
        if (wristZ !== undefined) this.wristZ = wristZ;
        if (wristYaw !== undefined) this.wristYaw = wristYaw;
        if (wristPitch !== undefined) this.wristPitch = wristPitch;
        if (wristRoll !== undefined) this.wristRoll = wristRoll;
        if (fingers) {
            for (const [fKey, val] of Object.entries(fingers)) {
                const f = Number(fKey);
                if (!this.fingerStates[f]) continue;
                if (val.curl !== undefined) this.fingerStates[f].targetCurl = val.curl;
                if (val.splay !== undefined) this.fingerStates[f].targetSplay = val.splay;
                if (val.press !== undefined) this.fingerStates[f].targetPress = val.press;
            }
        }
    }

    /**
     * Maps active & upcoming HotChords note events for this hand into wrist + finger targets.
     */
    solveForNotes(activeNotes, upcomingNotes) {
        const keys = this.keyLayout.keys;
        const activeByFinger = {};

        // Ensure deterministic fallback fingering if any note lacks a valid 1..5 finger
        const assignFallbackFingers = (notesList) => {
            const sorted = [...notesList].sort((a, b) => a.midi - b.midi);
            const used = new Set(sorted.filter(n => n.finger >= 1 && n.finger <= 5).map(n => Number(n.finger)));
            const order = this.isLeft ? [5, 4, 3, 2, 1] : [1, 2, 3, 4, 5];
            return sorted.map(n => {
                let f = Number(n.finger);
                if (!(f >= 1 && f <= 5)) {
                    f = order.find(cand => !used.has(cand)) || 3;
                    used.add(f);
                }
                return { ...n, finger: f };
            });
        };

        const resolvedActive = assignFallbackFingers(activeNotes || []);
        const resolvedUpcoming = assignFallbackFingers(upcomingNotes || []);

        resolvedActive.forEach(n => {
            activeByFinger[n.finger] = n;
        });

        const targets = resolvedActive.length > 0 ? resolvedActive : resolvedUpcoming.slice(0, 2);
        if (targets.length > 0) {
            let sumX = 0;
            let wSum = 0;
            let hasBlack = false;
            targets.forEach((n) => {
                const k = keys[n.midi];
                if (!k) return;
                if (k.isBlack) hasBlack = true;
                sumX += k.targetX;
                wSum += 1.0;
            });
            if (wSum > 0) {
                this.wristX = sumX / wSum;
            }
            this.wristZ = hasBlack ? 0.172 : 0.194;
            this.wristY = hasBlack ? 0.060 : 0.052;
            this.wristPitch = hasBlack ? -0.10 : -0.12;

            if (resolvedActive.length >= 2) {
                const xs = resolvedActive.map(n => keys[n.midi]?.targetX ?? this.wristX);
                const span = Math.max(...xs) - Math.min(...xs);
                this.wristYaw = Math.max(-0.20, Math.min(0.20, span * 0.38 * (this.isLeft ? -1 : 1)));
                this.wristRoll = Math.max(-0.08, Math.min(0.08, span * 0.12 * (this.isLeft ? 1 : -1)));
            } else {
                this.wristYaw *= 0.82;
                this.wristRoll *= 0.82;
            }
        }

        // Initial per-finger curl/press targets before closed-loop IK refinement
        const ikTargets = {};
        for (let f = 1; f <= 5; f++) {
            const act = activeByFinger[f];
            const upc = resolvedUpcoming.find(n => n.finger === f);
            const fs = this.fingerStates[f];
            if (act && keys[act.midi]) {
                const k = keys[act.midi];
                fs.targetPress = 1.0;
                fs.targetCurl = f === 1 ? (k.isBlack ? 0.38 : 0.52) : (k.isBlack ? 0.44 : 0.68);
                fs.targetSplay = 0.0;
                ikTargets[f] = { key: k, weight: 1.0 };
            } else if (upc && keys[upc.midi]) {
                const k = keys[upc.midi];
                const tLeft = typeof upc.timeUntilStrike === 'number' ? upc.timeUntilStrike : 0.25;
                const prep = Math.max(0.1, Math.min(0.4, 0.45 - tLeft));
                fs.targetPress = prep * 0.5;
                fs.targetCurl = f === 1 ? 0.38 : (k.isBlack ? 0.36 : 0.50);
                fs.targetSplay = 0.0;
                ikTargets[f] = { key: k, weight: 0.35 };
            } else {
                fs.targetPress = 0.0;
                fs.targetCurl = f === 1 ? 0.36 : 0.46;
                fs.targetSplay = 0.0;
            }
        }

        // Closed-loop world-space fingertip IK (3 iterations)
        if (Object.keys(ikTargets).length > 0) {
            this._runFingertipIK(ikTargets);
        }
    }

    _runFingertipIK(ikTargets) {
        const savedPos = this.root.position.clone();
        const savedRot = this.root.rotation.clone();
        const savedQuats = {};
        Object.keys(this.bones).forEach((name) => {
            savedQuats[name] = this.bones[name].quaternion.clone();
        });

        const eps = 0.025;
        this.lastIkMaxErrorMeters = 0;

        for (let iter = 0; iter < 4; iter++) {
            this.root.position.set(this.wristX, this.wristY, this.wristZ);
            this.root.rotation.set(this.wristPitch, this.wristYaw, this.wristRoll, 'YXZ');
            for (let f = 1; f <= 5; f++) {
                const fs = this.fingerStates[f];
                this._applyFingerPose(f, fs.targetCurl, fs.targetSplay, fs.targetPress);
            }
            this.root.updateMatrixWorld(true);

            let dxSum = 0;
            let dySum = 0;
            let dzSum = 0;
            let wSum = 0;

            Object.entries(ikTargets).forEach(([fStr, info]) => {
                const f = Number(fStr);
                const fs = this.fingerStates[f];
                const tipName = `${FINGER_NAMES[f]}-tip`;
                const tip0 = this._boneWorldPos(tipName);
                const k = info.key;

                const errX = k.targetX - tip0.x;
                const errZ = k.targetZ - tip0.z;
                // Fingertip pad flesh radius ~6.5mm; key.targetY already includes live 8mm depression
                const desiredTipY = k.targetY + 0.0065;
                const errY = desiredTipY - tip0.y;

                dxSum += errX * info.weight;
                dySum += errY * info.weight;
                dzSum += errZ * info.weight;
                wSum += info.weight;

                // Numerical Jacobian for splay & curl in exact world space
                this._applyFingerPose(f, fs.targetCurl, fs.targetSplay + eps, fs.targetPress);
                this.root.updateMatrixWorld(true);
                const tipS = this._boneWorldPos(tipName);
                const sx = (tipS.x - tip0.x) / eps;
                const sz = (tipS.z - tip0.z) / eps;

                this._applyFingerPose(f, fs.targetCurl + eps, fs.targetSplay, fs.targetPress);
                this.root.updateMatrixWorld(true);
                const tipC = this._boneWorldPos(tipName);
                const cx = (tipC.x - tip0.x) / eps;
                const cz = (tipC.z - tip0.z) / eps;

                // Damped least-squares updates with anatomical limits
                const dSplay = (errX * sx + errZ * sz) / (sx * sx + sz * sz + 2e-4);
                const dCurl = (errX * cx + errZ * cz) / (cx * cx + cz * cz + 2e-4);

                fs.targetSplay = Math.max(-0.45, Math.min(0.45, fs.targetSplay + dSplay * 0.72));
                fs.targetCurl = Math.max(0.18, Math.min(1.02, fs.targetCurl + dCurl * 0.65));

                this._applyFingerPose(f, fs.targetCurl, fs.targetSplay, fs.targetPress);
                if (iter === 3 && info.weight >= 0.9) {
                    const errDist = Math.hypot(errX, errZ);
                    if (errDist > this.lastIkMaxErrorMeters) {
                        this.lastIkMaxErrorMeters = errDist;
                    }
                }
            });

            if (wSum > 0) {
                const avgDx = dxSum / wSum;
                const avgDy = dySum / wSum;
                const avgDz = dzSum / wSum;
                this.wristX += Math.max(-0.045, Math.min(0.045, avgDx * 0.75));
                this.wristY = Math.max(0.040, Math.min(0.080, this.wristY + avgDy * 0.55));
                this.wristZ = Math.max(0.145, Math.min(0.225, this.wristZ + avgDz * 0.45));
            }
        }

        // Restore live spring state transforms so update(dt) interpolates smoothly
        this.root.position.copy(savedPos);
        this.root.rotation.copy(savedRot);
        Object.keys(savedQuats).forEach((name) => {
            this.bones[name].quaternion.copy(savedQuats[name]);
        });
        this.root.updateMatrixWorld(true);
    }

    _applyFingerPose(f, curl, splay, press) {
        const base = FINGER_NAMES[f];
        const pressAngle = press * (f === 1 ? 0.28 : 0.36);

        if (f === 1) {
            const oppRad = 0.44 + curl * 0.30 + press * 0.16;
            this._applyBoneAngle('thumb-metacarpal', curl * 0.35 + pressAngle * 0.4, splay * 0.6, oppRad);
            this._applyBoneAngle('thumb-phalanx-proximal', curl * 0.55 + pressAngle * 0.6, 0, 0);
            this._applyBoneAngle('thumb-phalanx-distal', curl * 0.45, 0, 0);
        } else {
            this._applyBoneAngle(`${base}-phalanx-proximal`, curl * 0.55 + pressAngle, splay, 0);
            this._applyBoneAngle(`${base}-phalanx-intermediate`, curl * 0.78 + pressAngle * 0.35, 0, 0);
            this._applyBoneAngle(`${base}-phalanx-distal`, curl * 0.45, 0, 0);
        }
    }

    update(dt, snap = false) {
        const alpha = snap ? 1.0 : (1.0 - Math.exp(-18.0 * Math.min(0.05, Math.max(0.004, dt))));
        this.root.position.x += (this.wristX - this.root.position.x) * alpha;
        this.root.position.y += (this.wristY - this.root.position.y) * alpha;
        this.root.position.z += (this.wristZ - this.root.position.z) * alpha;

        this.root.rotation.set(
            this.wristPitch,
            this.wristYaw,
            this.wristRoll,
            'YXZ'
        );

        Object.keys(FINGER_NAMES).forEach((fNumStr) => {
            const f = Number(fNumStr);
            const st = this.fingerStates[f];
            st.curl += (st.targetCurl - st.curl) * alpha;
            st.splay += (st.targetSplay - st.splay) * alpha;
            st.press += (st.targetPress - st.press) * alpha;
            this._applyFingerPose(f, st.curl, st.splay, st.press);
        });
    }

    _applyBoneAngle(boneName, flexRad, splayRad, oppRad = 0) {
        const bone = this.bones[boneName];
        const rest = this.restQuats[boneName];
        const flexAxis = this.flexAxes[boneName];
        const splayAxis = this.splayAxes[boneName];
        const oppAxis = this.oppAxes[boneName];
        if (!bone || !rest || !flexAxis) return;

        const qFlex = new THREE.Quaternion().setFromAxisAngle(flexAxis, flexRad);
        const q = rest.clone().multiply(qFlex);
        if (splayRad && splayAxis) {
            const qSplay = new THREE.Quaternion().setFromAxisAngle(splayAxis, splayRad);
            q.multiply(qSplay);
        }
        if (oppRad && oppAxis) {
            const qOpp = new THREE.Quaternion().setFromAxisAngle(oppAxis, oppRad);
            q.multiply(qOpp);
        }
        bone.quaternion.copy(q);
    }
}
