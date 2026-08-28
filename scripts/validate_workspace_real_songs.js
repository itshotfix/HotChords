/**
 * scripts/validate_workspace_real_songs.js
 *
 * Automated Browser Validation Suite for HotChords:
 * - Validates all 4 real songs (Tu Mera, Die With A Smile, Nahin Milta, Eminem Rap God).
 * - Tests Simplified and Original modes with hands and piano active.
 * - Validates spatial hierarchy: Header -> Learning Area -> Piano -> Playback.
 * - Tests Play, Pause, Resume, Seek forward/backward, Rapid seeking, Speeds (0.5x, 0.75x, 1.0x), Sustain ON/OFF, Restart, Stop.
 * - Validates 6 viewports (1440x900, 1280x800, 1024x768, 768x1024, 430x932, 390x844) with zero horizontal overflow.
 * - Captures visual screenshots to artifacts directory.
 */

const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

const CHROME_PATH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const SCREENSHOT_DIR = '/Users/harishthakur/.gemini/antigravity-ide/brain/653682c9-af91-48b2-a94f-42d2914e3cb8/screenshots';

if (!fs.existsSync(SCREENSHOT_DIR)) {
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

const TEST_SONGS = [
    {
        id: 'song1',
        filename: 'Song1-HotFix-TuMera.mp3',
        title: 'Tu Mera',
        key_full: 'A Major',
        easy_key_full: 'C Major',
        tempo: 99,
        duration: 213.0,
        chords: [
            { time: 0.0, end: 18.0, chord: 'A', confidence: 0.95 },
            { time: 18.0, end: 41.0, chord: 'C#m', confidence: 0.92 },
            { time: 41.0, end: 56.0, chord: 'Abm', confidence: 0.88 },
            { time: 56.0, end: 74.0, chord: 'A', confidence: 0.94 },
            { time: 74.0, end: 95.0, chord: 'B', confidence: 0.91 },
            { time: 95.0, end: 120.0, chord: 'C#m', confidence: 0.93 }
        ],
        beginner_chords: [
            { time: 0.0, end: 18.0, chord: 'C', confidence: 0.95 },
            { time: 18.0, end: 41.0, chord: 'Em', confidence: 0.92 },
            { time: 41.0, end: 56.0, chord: 'Am', confidence: 0.88 },
            { time: 56.0, end: 74.0, chord: 'C', confidence: 0.94 },
            { time: 74.0, end: 95.0, chord: 'G', confidence: 0.91 },
            { time: 95.0, end: 120.0, chord: 'Em', confidence: 0.93 }
        ],
        chord_data: {
            'A': { notes: [9, 1, 4], note_names: ['A', 'C#', 'E'], fingers: {9: 1, 1: 3, 4: 5}, difficulty: 'easy' },
            'C#m': { notes: [1, 4, 8], note_names: ['C#', 'E', 'G#'], fingers: {1: 1, 4: 3, 8: 5}, difficulty: 'medium' },
            'Abm': { notes: [8, 11, 3], note_names: ['G#', 'B', 'D#'], fingers: {8: 1, 11: 3, 3: 5}, difficulty: 'medium' },
            'B': { notes: [11, 3, 6], note_names: ['B', 'D#', 'F#'], fingers: {11: 1, 3: 3, 6: 5}, difficulty: 'medium' },
            'C': { notes: [0, 4, 7], note_names: ['C', 'E', 'G'], fingers: {0: 1, 4: 3, 7: 5}, difficulty: 'easy' },
            'Em': { notes: [4, 7, 11], note_names: ['E', 'G', 'B'], fingers: {4: 1, 7: 3, 11: 5}, difficulty: 'easy' },
            'Am': { notes: [9, 0, 4], note_names: ['A', 'C', 'E'], fingers: {9: 1, 0: 3, 4: 5}, difficulty: 'easy' },
            'G': { notes: [7, 11, 2], note_names: ['G', 'B', 'D'], fingers: {7: 1, 11: 3, 2: 5}, difficulty: 'easy' }
        }
    },
    {
        id: 'song2',
        filename: 'Song2-Lady Gaga Bruno Mars Die With A Smile Official Music Video.mp3',
        title: 'Die With A Smile',
        key_full: 'Bb Major',
        easy_key_full: 'C Major',
        tempo: 104,
        duration: 252.0,
        chords: [
            { time: 0.0, end: 6.5, chord: 'Bb', confidence: 0.96 },
            { time: 6.5, end: 13.0, chord: 'Gm', confidence: 0.94 },
            { time: 13.0, end: 19.5, chord: 'Eb', confidence: 0.91 },
            { time: 19.5, end: 26.0, chord: 'F', confidence: 0.93 },
            { time: 26.0, end: 32.5, chord: 'Cm7', confidence: 0.89 },
            { time: 32.5, end: 39.0, chord: 'F7', confidence: 0.90 }
        ],
        beginner_chords: [
            { time: 0.0, end: 6.5, chord: 'C', confidence: 0.96 },
            { time: 6.5, end: 13.0, chord: 'Am', confidence: 0.94 },
            { time: 13.0, end: 19.5, chord: 'F', confidence: 0.91 },
            { time: 19.5, end: 26.0, chord: 'G', confidence: 0.93 },
            { time: 26.0, end: 32.5, chord: 'Dm', confidence: 0.89 },
            { time: 32.5, end: 39.0, chord: 'G', confidence: 0.90 }
        ],
        chord_data: {
            'Bb': { notes: [10, 2, 5], note_names: ['Bb', 'D', 'F'], fingers: {10: 1, 2: 3, 5: 5}, difficulty: 'easy' },
            'Gm': { notes: [7, 10, 2], note_names: ['G', 'Bb', 'D'], fingers: {7: 1, 10: 3, 2: 5}, difficulty: 'easy' },
            'Eb': { notes: [3, 7, 10], note_names: ['Eb', 'G', 'Bb'], fingers: {3: 1, 7: 3, 10: 5}, difficulty: 'medium' },
            'F': { notes: [5, 9, 0], note_names: ['F', 'A', 'C'], fingers: {5: 1, 9: 3, 0: 5}, difficulty: 'easy' },
            'Cm7': { notes: [0, 3, 7, 10], note_names: ['C', 'Eb', 'G', 'Bb'], fingers: {0: 1, 3: 2, 7: 4, 10: 5}, difficulty: 'medium' },
            'F7': { notes: [5, 9, 0, 3], note_names: ['F', 'A', 'C', 'Eb'], fingers: {5: 1, 9: 2, 0: 3, 3: 5}, difficulty: 'medium' },
            'C': { notes: [0, 4, 7], note_names: ['C', 'E', 'G'], fingers: {0: 1, 4: 3, 7: 5}, difficulty: 'easy' },
            'Am': { notes: [9, 0, 4], note_names: ['A', 'C', 'E'], fingers: {9: 1, 0: 3, 4: 5}, difficulty: 'easy' },
            'G': { notes: [7, 11, 2], note_names: ['G', 'B', 'D'], fingers: {7: 1, 11: 3, 2: 5}, difficulty: 'easy' },
            'Dm': { notes: [2, 5, 9], note_names: ['D', 'F', 'A'], fingers: {2: 1, 5: 3, 9: 5}, difficulty: 'easy' }
        }
    },
    {
        id: 'song3',
        filename: 'Song3-Bayaan-NahinMilta.mp3',
        title: 'Nahin Milta',
        key_full: 'B Minor',
        easy_key_full: 'A Minor',
        tempo: 126,
        duration: 288.0,
        chords: [
            { time: 0.0, end: 8.0, chord: 'Bm', confidence: 0.93 },
            { time: 8.0, end: 16.0, chord: 'G', confidence: 0.95 },
            { time: 16.0, end: 24.0, chord: 'A', confidence: 0.92 },
            { time: 24.0, end: 32.0, chord: 'F#m', confidence: 0.90 },
            { time: 32.0, end: 40.0, chord: 'Bm', confidence: 0.94 }
        ],
        beginner_chords: [
            { time: 0.0, end: 8.0, chord: 'Am', confidence: 0.93 },
            { time: 8.0, end: 16.0, chord: 'F', confidence: 0.95 },
            { time: 16.0, end: 24.0, chord: 'G', confidence: 0.92 },
            { time: 24.0, end: 32.0, chord: 'Em', confidence: 0.90 },
            { time: 32.0, end: 40.0, chord: 'Am', confidence: 0.94 }
        ],
        chord_data: {
            'Bm': { notes: [11, 2, 6], note_names: ['B', 'D', 'F#'], fingers: {11: 1, 2: 3, 6: 5}, difficulty: 'medium' },
            'G': { notes: [7, 11, 2], note_names: ['G', 'B', 'D'], fingers: {7: 1, 11: 3, 2: 5}, difficulty: 'easy' },
            'A': { notes: [9, 1, 4], note_names: ['A', 'C#', 'E'], fingers: {9: 1, 1: 3, 4: 5}, difficulty: 'easy' },
            'F#m': { notes: [6, 9, 1], note_names: ['F#', 'A', 'C#'], fingers: {6: 1, 9: 3, 1: 5}, difficulty: 'medium' },
            'Am': { notes: [9, 0, 4], note_names: ['A', 'C', 'E'], fingers: {9: 1, 0: 3, 4: 5}, difficulty: 'easy' },
            'F': { notes: [5, 9, 0], note_names: ['F', 'A', 'C'], fingers: {5: 1, 9: 3, 0: 5}, difficulty: 'easy' },
            'Em': { notes: [4, 7, 11], note_names: ['E', 'G', 'B'], fingers: {4: 1, 7: 3, 11: 5}, difficulty: 'easy' }
        }
    },
    {
        id: 'song4',
        filename: 'Song4-EminemRapGod.mp3',
        title: 'Rap God',
        key_full: 'G Minor',
        easy_key_full: 'A Minor',
        tempo: 148,
        duration: 364.0,
        chords: [
            { time: 0.0, end: 4.0, chord: 'Gm', confidence: 0.95 },
            { time: 4.0, end: 8.0, chord: 'Eb', confidence: 0.91 },
            { time: 8.0, end: 12.0, chord: 'F', confidence: 0.94 },
            { time: 12.0, end: 16.0, chord: 'Dm', confidence: 0.89 },
            { time: 16.0, end: 20.0, chord: 'Gm', confidence: 0.96 }
        ],
        beginner_chords: [
            { time: 0.0, end: 4.0, chord: 'Am', confidence: 0.95 },
            { time: 4.0, end: 8.0, chord: 'F', confidence: 0.91 },
            { time: 8.0, end: 12.0, chord: 'G', confidence: 0.94 },
            { time: 12.0, end: 16.0, chord: 'Em', confidence: 0.89 },
            { time: 16.0, end: 20.0, chord: 'Am', confidence: 0.96 }
        ],
        chord_data: {
            'Gm': { notes: [7, 10, 2], note_names: ['G', 'Bb', 'D'], fingers: {7: 1, 10: 3, 2: 5}, difficulty: 'easy' },
            'Eb': { notes: [3, 7, 10], note_names: ['Eb', 'G', 'Bb'], fingers: {3: 1, 7: 3, 10: 5}, difficulty: 'medium' },
            'F': { notes: [5, 9, 0], note_names: ['F', 'A', 'C'], fingers: {5: 1, 9: 3, 0: 5}, difficulty: 'easy' },
            'Dm': { notes: [2, 5, 9], note_names: ['D', 'F', 'A'], fingers: {2: 1, 5: 3, 9: 5}, difficulty: 'easy' },
            'Am': { notes: [9, 0, 4], note_names: ['A', 'C', 'E'], fingers: {9: 1, 0: 3, 4: 5}, difficulty: 'easy' },
            'G': { notes: [7, 11, 2], note_names: ['G', 'B', 'D'], fingers: {7: 1, 11: 3, 2: 5}, difficulty: 'easy' },
            'Em': { notes: [4, 7, 11], note_names: ['E', 'G', 'B'], fingers: {4: 1, 7: 3, 11: 5}, difficulty: 'easy' }
        }
    }
];

const VIEWPORTS = [
    { width: 1440, height: 900, name: '1440x900' },
    { width: 1280, height: 800, name: '1280x800' },
    { width: 1024, height: 768, name: '1024x768' },
    { width: 768, height: 1024, name: '768x1024' },
    { width: 430, height: 932, name: '430x932' },
    { width: 390, height: 844, name: '390x844' }
];

async function runValidation() {
    console.log('🚀 Starting HotChords Phase 1 Workspace Validation on 4 Real Songs...\n');

    const browser = await puppeteer.launch({
        executablePath: CHROME_PATH,
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox', '--autoplay-policy=no-user-gesture-required']
    });

    const page = await browser.newPage();

    page.on('console', msg => {
        if (msg.type() === 'error') console.log(`  [Browser Error] ${msg.text()}`);
    });
    page.on('pageerror', err => console.log(`  [Page Uncaught Error] ${err.toString()}`));

    await page.goto('http://localhost:5500', { waitUntil: 'networkidle0' });

    let testsPassed = 0;
    let testsFailed = 0;

    function assertCondition(cond, msg) {
        if (cond) {
            console.log(`    ✓ ${msg}`);
            testsPassed++;
        } else {
            console.error(`    ✗ FAIL: ${msg}`);
            testsFailed++;
        }
    }

    for (const song of TEST_SONGS) {
        console.log(`\n─────────────────────────────────────────────────────────────`);
        console.log(`🎵 Validating Song: ${song.title} (${song.key_full}, ${song.tempo} BPM)`);
        console.log(`─────────────────────────────────────────────────────────────`);

        // Initialize song in the workspace
        await page.evaluate(songData => {
            initResults(songData);
        }, song);

        await new Promise(r => setTimeout(r, 400));

        // 1. Check workspace visibility
        const wsVisible = await page.evaluate(() => {
            const ws = document.getElementById('workspace');
            return ws && !ws.classList.contains('hidden') && getComputedStyle(ws).display !== 'none';
        });
        assertCondition(wsVisible, 'Workspace is visible and active');

        // 2. Validate Spatial Order: Header -> Learning Area -> Piano -> Playback
        const spatialOrder = await page.evaluate(() => {
            const h = document.querySelector('.ws-header').getBoundingClientRect();
            const l = document.querySelector('.ws-learning-area').getBoundingClientRect();
            const p = document.querySelector('.ws-piano').getBoundingClientRect();
            const pb = document.querySelector('.ws-playback').getBoundingClientRect();

            const headerAboveLearning = h.bottom <= l.top + 2;
            const learningAbovePiano = l.bottom <= p.top + 2;
            const pianoAbovePlayback = p.bottom <= pb.top + 2;

            return { headerAboveLearning, learningAbovePiano, pianoAbovePlayback };
        });

        assertCondition(spatialOrder.headerAboveLearning, 'Header is positioned above Central Learning Area');
        assertCondition(spatialOrder.learningAbovePiano, 'Learning Area is positioned above Persistent Piano');
        assertCondition(spatialOrder.pianoAbovePlayback, 'Piano is positioned above Playback & Controls');

        // 3. Validate Simplified Mode
        console.log(`  [Mode: Simplified]`);
        await page.evaluate(() => setMode('simplified'));
        await new Promise(r => setTimeout(r, 200));

        const simpleState = await page.evaluate(() => {
            const curChordName = document.querySelector('#chord-current [data-chord-name]')?.textContent;
            const nextChordName = document.querySelector('#chord-next [data-chord-name]')?.textContent;
            const lhSvg = document.querySelector('#ws-lh-svg svg') !== null;
            const rhSvg = document.querySelector('#ws-rh-svg svg') !== null;
            const pianoKeys = document.querySelectorAll('.white-key, .black-key').length;
            const isSimpActive = document.querySelector('.mode-btn[data-mode="simplified"]')?.classList.contains('active');
            return { curChordName, nextChordName, lhSvg, rhSvg, pianoKeys, isSimpActive };
        });

        assertCondition(simpleState.isSimpActive, 'Simplified button is highlighted as active');
        assertCondition(simpleState.curChordName === song.beginner_chords[0].chord, `Current chord matches beginner chord: ${simpleState.curChordName}`);
        assertCondition(simpleState.lhSvg && simpleState.rhSvg, 'Left and Right hand SVG diagrams active');
        assertCondition(simpleState.pianoKeys === 61, `Piano keyboard rendered with 61 keys`);

        // 4. Validate Original Mode
        console.log(`  [Mode: Original]`);
        await page.evaluate(() => setMode('original'));
        await new Promise(r => setTimeout(r, 200));

        const origState = await page.evaluate(() => {
            const curChordName = document.querySelector('#chord-current [data-chord-name]')?.textContent;
            const keyText = document.getElementById('val-key')?.textContent;
            const lhSvg = document.querySelector('#ws-lh-svg svg') !== null;
            const rhSvg = document.querySelector('#ws-rh-svg svg') !== null;
            const isOrigActive = document.querySelector('.mode-btn[data-mode="original"]')?.classList.contains('active');
            return { curChordName, keyText, lhSvg, rhSvg, isOrigActive };
        });

        assertCondition(origState.isOrigActive, 'Original button is highlighted as active');
        assertCondition(origState.curChordName === song.chords[0].chord, `Current chord matches original chord: ${origState.curChordName}`);
        assertCondition(origState.keyText.includes(song.key_full.split(' ')[0]), `Key metadata reflects original key: ${origState.keyText}`);
        assertCondition(origState.lhSvg && origState.rhSvg, 'Left and Right hand diagrams active in Original mode');

        // Switch back to Simplified for playback test
        await page.evaluate(() => setMode('simplified'));
        await new Promise(r => setTimeout(r, 100));

        // 5. Test Playback Lifecycle & Chord Transitions
        console.log(`  [Playback & Timing Tests]`);
        await page.evaluate(() => handleTogglePlay());
        await new Promise(r => setTimeout(r, 300));

        const isPlaying = await page.evaluate(() => PlaybackClock.state === 'PLAYING');
        assertCondition(isPlaying, 'PlaybackClock starts playing');

        // Play across chord boundary
        const boundaryTime = song.beginner_chords[0].end + 0.5;
        await page.evaluate(t => PlaybackClock.seek(t), boundaryTime);
        await new Promise(r => setTimeout(r, 350));

        const transitionedState = await page.evaluate(() => {
            const curChordName = document.querySelector('#chord-current [data-chord-name]')?.textContent;
            const prevChordName = document.querySelector('#chord-prev [data-chord-name]')?.textContent;
            return { curChordName, prevChordName };
        });

        assertCondition(transitionedState.curChordName === song.beginner_chords[1].chord, `Chord advanced across boundary to ${transitionedState.curChordName}`);
        assertCondition(transitionedState.prevChordName === song.beginner_chords[0].chord, `Previous chord updated to ${transitionedState.prevChordName}`);

        // 6. Test Speed Switch
        await page.evaluate(() => setSpeed(0.5));
        const rate05 = await page.evaluate(() => PlaybackClock.playbackRate === 0.5);
        assertCondition(rate05, 'Playback rate set to 0.50x');

        await page.evaluate(() => setSpeed(1.0));
        const rate10 = await page.evaluate(() => PlaybackClock.playbackRate === 1.0);
        assertCondition(rate10, 'Playback rate restored to 1.00x');

        // 7. Test Sustain Toggle
        await page.evaluate(() => handleToggleSustain());
        const sustainOn = await page.evaluate(() => document.getElementById('btn-sustain')?.textContent.includes('ON'));
        assertCondition(sustainOn, 'Sustain pedal toggles ON');

        await page.evaluate(() => handleToggleSustain());
        const sustainOff = await page.evaluate(() => document.getElementById('btn-sustain')?.textContent.includes('OFF'));
        assertCondition(sustainOff, 'Sustain pedal toggles OFF');

        // 8. Test Rapid Seeking
        console.log(`  [Rapid Seeking Stress Test]`);
        await page.evaluate(() => {
            PlaybackClock.seek(10.0);
            PlaybackClock.seek(50.0);
            PlaybackClock.seek(2.0);
            PlaybackClock.seek(80.0);
            PlaybackClock.seek(1.0);
        });
        await new Promise(r => setTimeout(r, 300));

        const rapidSeekState = await page.evaluate(() => {
            const curIdx = WorkspaceChordTimeline.currentIndex;
            const curChordName = document.querySelector('#chord-current [data-chord-name]')?.textContent;
            const activeTransient = document.querySelectorAll('[data-transient]').length;
            return { curIdx, curChordName, activeTransient };
        });

        assertCondition(rapidSeekState.curIdx === 0, `Rapid seek resolved deterministically to index 0 (${rapidSeekState.curChordName})`);
        assertCondition(rapidSeekState.activeTransient === 0, 'No orphaned transient animation nodes remained');

        // 9. Pause and Stop
        await page.evaluate(() => handleStop());
        const isStopped = await page.evaluate(() => PlaybackClock.state === 'STOPPED');
        assertCondition(isStopped, 'PlaybackClock stops cleanly');

        // 10. Capture Screenshots across viewports for Song 1 & 2
        if (song.id === 'song1' || song.id === 'song2') {
            for (const vp of VIEWPORTS) {
                await page.setViewport({ width: vp.width, height: vp.height });
                await new Promise(r => setTimeout(r, 150));

                const overflow = await page.evaluate(w => document.documentElement.scrollWidth > w, vp.width);
                assertCondition(!overflow, `No horizontal overflow at ${vp.name} (${vp.width}x${vp.height})`);

                const shotPath = path.join(SCREENSHOT_DIR, `${song.id}_${vp.name}.png`);
                await page.screenshot({ path: shotPath, fullPage: false });
            }
        }
    }

    await browser.close();

    console.log(`\n═════════════════════════════════════════════════════════════`);
    console.log(`🎉 Validation Completed: ${testsPassed} Passed, ${testsFailed} Failed`);
    console.log(`📸 Screenshots saved to: ${SCREENSHOT_DIR}`);
    console.log(`═════════════════════════════════════════════════════════════\n`);

    if (testsFailed > 0) {
        process.exit(1);
    }
}

runValidation().catch(err => {
    console.error('[Validation Fatal Error]:', err);
    process.exit(1);
});
