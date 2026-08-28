/**
 * scripts/capture_v03_release_screenshots.js
 *
 * Captures clean, high-resolution documentation screenshots for the HotChords v0.3 release:
 * 01-upload.png                - Initial upload landing screen (1440x900)
 * 02-analysis.png              - Live audio processing & pipeline milestone checklist (1440x900)
 * 03-workspace.png             - Single interactive music stand workspace (1440x900)
 * 04-simplified-mode.png       - Simplified beginner chord mode with hero chord & hand voicings (1440x900)
 * 05-original-mode.png         - Original rich harmonic chord mode (1440x900)
 * 06-playback-current-chord.png- Live playback with hero current chord & real-time progress bar (1440x900)
 * 07-chord-transition.png      - Coordinated physical slide transition between chords (1440x900)
 * 08-hands-and-piano.png       - Highlighting synchronized Left/Right hands and 61-key piano (1440x900)
 * 09-mobile-workspace.png      - Responsive mobile workspace layout (390x844)
 * 10-mobile-playback.png       - Responsive mobile live playback (390x844)
 */

const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

const CHROME_PATH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const DOCS_SCREENSHOT_DIR = '/Volumes/TIKDI/APP Development/HotChords App/docs/screenshots/v0.3';
const TEST_SONG_PATH = '/Volumes/TIKDI/APP Development/HotChords App/test songs/Song1-HotFix-TuMera.mp3';

if (!fs.existsSync(DOCS_SCREENSHOT_DIR)) {
    fs.mkdirSync(DOCS_SCREENSHOT_DIR, { recursive: true });
}

async function captureReleaseScreenshots() {
    console.log('📸 Starting HotChords v0.3 Official Release Screenshot Capture...\n');

    const browser = await puppeteer.launch({
        executablePath: CHROME_PATH,
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    const page = await browser.newPage();
    await page.goto('http://localhost:5500', { waitUntil: 'networkidle0' });

    // ─────────────────────────────────────────────────────────────
    // 01: Upload / Landing Screen (1440x900)
    // ─────────────────────────────────────────────────────────────
    await page.setViewport({ width: 1440, height: 900 });
    await new Promise(r => setTimeout(r, 200));
    await page.screenshot({ path: path.join(DOCS_SCREENSHOT_DIR, '01-upload.png') });
    console.log('  ✓ Captured 01-upload.png (1440x900)');

    // ─────────────────────────────────────────────────────────────
    // 02: Processing / Analysis Screen (1440x900)
    // ─────────────────────────────────────────────────────────────
    await page.evaluate(() => {
        showScreen('analysis-screen');
        document.getElementById('prog-file-name').textContent = 'Song1-HotFix-TuMera.mp3';
        document.getElementById('prog-bar').style.width = '62%';
        document.getElementById('prog-msg').textContent = 'Detecting chords & musical key...';
        _updatePipelineStageUI(62, 'Detecting chords & musical key...');
    });
    await new Promise(r => setTimeout(r, 200));
    await page.screenshot({ path: path.join(DOCS_SCREENSHOT_DIR, '02-analysis.png') });
    console.log('  ✓ Captured 02-analysis.png (1440x900)');

    // ─────────────────────────────────────────────────────────────
    // 03: Workspace Overview with Real Song (1440x900)
    // ─────────────────────────────────────────────────────────────
    await page.evaluate(() => resetApp());
    const fileInput = await page.$('#file-input');
    await fileInput.uploadFile(TEST_SONG_PATH);

    console.log('  ⏳ Processing real song for workspace capture...');
    await page.waitForFunction(() => !document.getElementById('workspace').classList.contains('hidden'), { timeout: 60000 });
    await new Promise(r => setTimeout(r, 600));

    await page.screenshot({ path: path.join(DOCS_SCREENSHOT_DIR, '03-workspace.png') });
    console.log('  ✓ Captured 03-workspace.png (1440x900)');

    // ─────────────────────────────────────────────────────────────
    // 04: Simplified Mode (1440x900)
    // ─────────────────────────────────────────────────────────────
    await page.evaluate(() => {
        setMode('simplified');
        PlaybackClock.seek(0);
    });
    await new Promise(r => setTimeout(r, 300));
    await page.screenshot({ path: path.join(DOCS_SCREENSHOT_DIR, '04-simplified-mode.png') });
    console.log('  ✓ Captured 04-simplified-mode.png (1440x900)');

    // ─────────────────────────────────────────────────────────────
    // 05: Original Mode (1440x900)
    // ─────────────────────────────────────────────────────────────
    await page.evaluate(() => {
        setMode('original');
        PlaybackClock.seek(0);
    });
    await new Promise(r => setTimeout(r, 300));
    await page.screenshot({ path: path.join(DOCS_SCREENSHOT_DIR, '05-original-mode.png') });
    console.log('  ✓ Captured 05-original-mode.png (1440x900)');

    // ─────────────────────────────────────────────────────────────
    // 06: Playback Current Chord (1440x900)
    // ─────────────────────────────────────────────────────────────
    await page.evaluate(() => {
        setMode('simplified');
        PlaybackClock.seek(18.5);
        PlaybackClock.play();
    });
    await new Promise(r => setTimeout(r, 400));
    await page.screenshot({ path: path.join(DOCS_SCREENSHOT_DIR, '06-playback-current-chord.png') });
    console.log('  ✓ Captured 06-playback-current-chord.png (1440x900)');

    // ─────────────────────────────────────────────────────────────
    // 07: Live Chord Transition (1440x900)
    // ─────────────────────────────────────────────────────────────
    await page.evaluate(() => {
        PlaybackClock.seek(40.8);
    });
    await new Promise(r => setTimeout(r, 400));
    await page.screenshot({ path: path.join(DOCS_SCREENSHOT_DIR, '07-chord-transition.png') });
    console.log('  ✓ Captured 07-chord-transition.png (1440x900)');

    // ─────────────────────────────────────────────────────────────
    // 08: Hands and Piano Focus (1440x900)
    // ─────────────────────────────────────────────────────────────
    await page.evaluate(() => {
        PlaybackClock.pause();
        PlaybackClock.seek(20.0);
    });
    await new Promise(r => setTimeout(r, 300));
    await page.screenshot({ path: path.join(DOCS_SCREENSHOT_DIR, '08-hands-and-piano.png') });
    console.log('  ✓ Captured 08-hands-and-piano.png (1440x900)');

    // ─────────────────────────────────────────────────────────────
    // 09: Mobile Workspace (390x844)
    // ─────────────────────────────────────────────────────────────
    await page.setViewport({ width: 390, height: 844 });
    await new Promise(r => setTimeout(r, 300));
    await page.screenshot({ path: path.join(DOCS_SCREENSHOT_DIR, '09-mobile-workspace.png') });
    console.log('  ✓ Captured 09-mobile-workspace.png (390x844)');

    // ─────────────────────────────────────────────────────────────
    // 10: Mobile Playback (390x844)
    // ─────────────────────────────────────────────────────────────
    await page.evaluate(() => {
        PlaybackClock.play();
    });
    await new Promise(r => setTimeout(r, 400));
    await page.screenshot({ path: path.join(DOCS_SCREENSHOT_DIR, '10-mobile-playback.png') });
    console.log('  ✓ Captured 10-mobile-playback.png (390x844)');

    await browser.close();

    console.log(`\n═════════════════════════════════════════════════════════════`);
    console.log(`🎉 All 10 v0.3 Release Screenshots Saved to:`);
    console.log(`   ${DOCS_SCREENSHOT_DIR}`);
    console.log(`═════════════════════════════════════════════════════════════\n`);
}

captureReleaseScreenshots().catch(err => {
    console.error('[Screenshot Error]:', err);
    process.exit(1);
});
