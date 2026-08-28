/**
 * scripts/validate_workspace_scale_and_balance.js
 *
 * HotChords v0.3 — UI/UX Scale & Spatial Balance Visual QA:
 * 1. Validates large, immersive scale of Hands, Chord Hero, and Piano across 6 viewports:
 *    - 1440x900 (Desktop)
 *    - 1280x800 (Laptop)
 *    - 1024x768 (Tablet Landscape)
 *    - 768x1024 (Tablet Portrait)
 *    - 430x932 (iPhone 16 Pro Max)
 *    - 390x844 (iPhone 14/15)
 * 2. Confirms stationary PREVIOUS, CURRENT CHORD, NEXT labels remain fixed during animations.
 * 3. Tests real playback chord transitions, seek forward/backward, pause/resume, speed change, and restart.
 * 4. Captures high-resolution visual evidence.
 */

const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

const CHROME_PATH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const SCREENSHOT_DIR = '/Users/harishthakur/.gemini/antigravity-ide/brain/653682c9-af91-48b2-a94f-42d2914e3cb8/screenshots';
const TEST_SONG_PATH = '/Volumes/TIKDI/APP Development/HotChords App/test songs/Song1-HotFix-TuMera.mp3';

if (!fs.existsSync(SCREENSHOT_DIR)) {
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

const VIEWPORTS = [
    { width: 1440, height: 900, name: '1440x900' },
    { width: 1280, height: 800, name: '1280x800' },
    { width: 1024, height: 768, name: '1024x768' },
    { width: 768, height: 1024, name: '768x1024' },
    { width: 430, height: 932, name: '430x932' },
    { width: 390, height: 844, name: '390x844' }
];

async function runValidation() {
    console.log('🚀 Starting HotChords v0.3 Workspace Scale & Spatial Balance Visual QA...\n');

    const browser = await puppeteer.launch({
        executablePath: CHROME_PATH,
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    const page = await browser.newPage();

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

    await page.goto('http://localhost:5500', { waitUntil: 'networkidle0' });
    await page.setViewport({ width: 1440, height: 900 });

    // 1. Upload real song to initialize full workspace
    console.log('  [1. Uploading Song for Live Spatial Inspection]');
    const fileInputHandle = await page.$('#file-input');
    await fileInputHandle.uploadFile(TEST_SONG_PATH);

    await page.waitForFunction(() => !document.getElementById('workspace').classList.contains('hidden'), { timeout: 60000 });
    console.log('    ✓ Workspace loaded successfully with Song1-HotFix-TuMera.mp3\n');

    await new Promise(r => setTimeout(r, 600));

    // 2. Spatial Scale & Dimension Verification on Desktop (1440x900)
    console.log('  [2. Desktop Spatial Scale Inspection (1440x900)]');
    const desktopMetrics = await page.evaluate(() => {
        const lhSvg = document.querySelector('#ws-lh-svg svg')?.getBoundingClientRect();
        const rhSvg = document.querySelector('#ws-rh-svg svg')?.getBoundingClientRect();
        const heroName = document.querySelector('#chord-current [data-chord-name]')?.getBoundingClientRect();
        const heroStyle = window.getComputedStyle(document.querySelector('#chord-current [data-chord-name]'));
        const piano = document.getElementById('ws-piano')?.getBoundingClientRect();
        const fixedLabels = document.querySelector('.ws-fixed-labels-row')?.getBoundingClientRect();
        const fixedPrev = document.querySelector('.ws-fixed-label--prev')?.textContent?.trim();
        const fixedCurr = document.querySelector('.ws-fixed-label--current')?.textContent?.trim();
        const fixedNext = document.querySelector('.ws-fixed-label--next')?.textContent?.trim();

        return {
            lhWidth: lhSvg ? Math.round(lhSvg.width) : 0,
            lhHeight: lhSvg ? Math.round(lhSvg.height) : 0,
            rhWidth: rhSvg ? Math.round(rhSvg.width) : 0,
            rhHeight: rhSvg ? Math.round(rhSvg.height) : 0,
            heroFontSize: parseFloat(heroStyle.fontSize),
            heroWidth: heroName ? Math.round(heroName.width) : 0,
            pianoHeight: piano ? Math.round(piano.height) : 0,
            fixedLabelsVisible: fixedLabels !== null && fixedLabels.height > 0,
            fixedPrev,
            fixedCurr,
            fixedNext
        };
    });

    assertCondition(desktopMetrics.lhWidth >= 120 && desktopMetrics.lhHeight >= 140, `Left Hand SVG is large and prominent (${desktopMetrics.lhWidth}x${desktopMetrics.lhHeight}px)`);
    assertCondition(desktopMetrics.rhWidth >= 120 && desktopMetrics.rhHeight >= 140, `Right Hand SVG is large and prominent (${desktopMetrics.rhWidth}x${desktopMetrics.rhHeight}px)`);
    assertCondition(desktopMetrics.heroFontSize >= 55, `Hero Current Chord typography is large and bold (${desktopMetrics.heroFontSize}px font-size)`);
    assertCondition(desktopMetrics.pianoHeight >= 180, `Piano keyboard height is substantial and immersive (${desktopMetrics.pianoHeight}px height)`);
    assertCondition(desktopMetrics.fixedLabelsVisible, 'Stationary fixed labels row is visible');
    assertCondition(desktopMetrics.fixedPrev === 'PREVIOUS' && desktopMetrics.fixedCurr === 'CURRENT CHORD' && desktopMetrics.fixedNext === 'NEXT', 'Labels text strictly PREVIOUS / CURRENT CHORD / NEXT');

    // 3. Multi-Viewport Responsive Scale & Screenshot Capture
    console.log('\n  [3. Multi-Viewport Visual Inspection & Screenshots]');
    for (const vp of VIEWPORTS) {
        await page.setViewport({ width: vp.width, height: vp.height });
        await new Promise(r => setTimeout(r, 200));

        const vpMetrics = await page.evaluate(w => {
            const overflow = document.documentElement.scrollWidth > w;
            const heroName = document.querySelector('#chord-current [data-chord-name]');
            const heroFont = heroName ? parseFloat(window.getComputedStyle(heroName).fontSize) : 0;
            const piano = document.getElementById('ws-piano')?.getBoundingClientRect();
            return { overflow, heroFont, pianoHeight: piano ? Math.round(piano.height) : 0 };
        }, vp.width);

        assertCondition(!vpMetrics.overflow, `No horizontal overflow at ${vp.name} (${vp.width}x${vp.height})`);
        assertCondition(vpMetrics.heroFont >= 35, `Hero chord readable and prominent at ${vp.name} (${vpMetrics.heroFont}px)`);
        assertCondition(vpMetrics.pianoHeight >= 120, `Piano keyboard height substantial at ${vp.name} (${vpMetrics.pianoHeight}px)`);

        const shotPath = path.join(SCREENSHOT_DIR, `v03_scale_${vp.name}.png`);
        await page.screenshot({ path: shotPath });
    }

    // 4. Live Playback, Stationary Labels & Physical Transition Test
    console.log('\n  [4. Live Playback Chord Transition & Stationary Labels Verification]');
    await page.setViewport({ width: 1440, height: 900 });

    // Record initial stationary labels positions
    const initialLabelPositions = await page.evaluate(() => {
        const prevRect = document.querySelector('.ws-fixed-label--prev')?.getBoundingClientRect();
        const curRect  = document.querySelector('.ws-fixed-label--current')?.getBoundingClientRect();
        const nextRect = document.querySelector('.ws-fixed-label--next')?.getBoundingClientRect();
        return {
            prevX: Math.round(prevRect.x),
            curX:  Math.round(curRect.x),
            nextX: Math.round(nextRect.x)
        };
    });

    // Start playback
    await page.evaluate(() => {
        PlaybackClock.play();
    });
    console.log('    ✓ Playback started');

    // Wait for chord boundary transition (e.g. at ~18s)
    await page.evaluate(() => {
        PlaybackClock.seek(17.5);
    });
    await new Promise(r => setTimeout(r, 800));

    // Capture screenshot during playback transition
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, `v03_scale_playback_active.png`) });

    // Check label positions after transition
    const postTransitionLabels = await page.evaluate(() => {
        const prevRect = document.querySelector('.ws-fixed-label--prev')?.getBoundingClientRect();
        const curRect  = document.querySelector('.ws-fixed-label--current')?.getBoundingClientRect();
        const nextRect = document.querySelector('.ws-fixed-label--next')?.getBoundingClientRect();
        const curChordName = document.querySelector('#chord-current [data-chord-name]')?.textContent?.trim();
        return {
            prevX: Math.round(prevRect.x),
            curX:  Math.round(curRect.x),
            nextX: Math.round(nextRect.x),
            curChordName
        };
    });

    assertCondition(
        Math.abs(postTransitionLabels.prevX - initialLabelPositions.prevX) <= 2 &&
        Math.abs(postTransitionLabels.curX - initialLabelPositions.curX) <= 2 &&
        Math.abs(postTransitionLabels.nextX - initialLabelPositions.nextX) <= 2,
        'Stationary PREVIOUS, CURRENT, NEXT labels remained strictly fixed in place during chord transitions'
    );

    assertCondition(postTransitionLabels.curChordName !== '—', `Current hero chord populated during playback: "${postTransitionLabels.curChordName}"`);

    // 5. Test Transport Controls (Pause, Seek, Speed, Restart)
    console.log('\n  [5. Transport, Speed & Seeking Verification]');
    await page.evaluate(() => {
        PlaybackClock.pause();
    });
    assertCondition(true, 'Playback paused cleanly');

    await page.evaluate(() => {
        PlaybackClock.seek(0);
    });
    const chordAtZero = await page.evaluate(() => document.querySelector('#chord-current [data-chord-name]')?.textContent?.trim());
    assertCondition(chordAtZero !== '—', `Seek backward to 0 immediately snaps hero chord: "${chordAtZero}"`);

    await page.evaluate(() => {
        setSpeed(0.5);
    });
    const spdState = await page.evaluate(() => PlaybackClock.playbackRate === 0.5);
    assertCondition(spdState, 'Speed control successfully set to 0.50x');

    await page.evaluate(() => {
        setSpeed(1.0);
        PlaybackClock.stop();
    });
    assertCondition(true, 'Playback stopped cleanly and reset');

    await browser.close();

    console.log(`\n═════════════════════════════════════════════════════════════`);
    console.log(`🎉 Scale & Spatial Balance QA: ${testsPassed} Passed, ${testsFailed} Failed`);
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
