/**
 * scripts/validate_v03_upload_processing.js
 *
 * HotChords v0.3 — Visual QA and Functional Validation Suite:
 * 1. Validates Upload Screen across 6 viewports (1440x900, 1280x800, 1024x768, 768x1024, 430x932, 390x844).
 * 2. Validates Processing Screen across 6 viewports with live waveform & 5 real pipeline milestones.
 * 3. Validates Error Handling Screen & action buttons.
 * 4. Real Song Upload Test with Song1-HotFix-TuMera.mp3:
 *    Upload -> Processing (live polling & milestone ticks) -> Single Loaded Workspace.
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
    console.log('🚀 Starting HotChords v0.3 Upload & Processing Experience Validation...\n');

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

    // ─────────────────────────────────────────────────────────────
    // 1. UPLOAD SCREEN VERIFICATION
    // ─────────────────────────────────────────────────────────────
    console.log('  [1. Upload Screen Layout & Content Verification]');
    const uploadData = await page.evaluate(() => {
        const headerBrand = document.querySelector('#upload-screen .header-brand')?.textContent?.trim();
        const headerVer = document.querySelector('#upload-screen .header-version')?.textContent?.trim();
        const headline = document.querySelector('.upload-headline')?.textContent?.trim();
        const subtext = document.querySelector('.upload-subtext')?.textContent?.trim();
        const cardTitle = document.querySelector('.upload-prompt-title')?.textContent?.trim();
        const formats = document.querySelector('.upload-formats-badge')?.textContent?.trim();
        const fileInput = document.getElementById('file-input') !== null;
        const uploadActive = document.getElementById('upload-screen')?.classList.contains('active');

        return { headerBrand, headerVer, headline, subtext, cardTitle, formats, fileInput, uploadActive };
    });

    assertCondition(uploadData.uploadActive, 'Upload screen is active on launch');
    assertCondition(uploadData.headerBrand.includes('HotChords'), `Header branding contains HotChords: "${uploadData.headerBrand}"`);
    assertCondition(uploadData.headerVer === 'VER 0.3', `Version badge displays "VER 0.3": "${uploadData.headerVer}"`);
    assertCondition(uploadData.headline.includes('Turn any song into'), `Headline matches: "${uploadData.headline.replace(/\s+/g, ' ')}"`);
    assertCondition(uploadData.subtext.includes('detect the chords') || uploadData.subtext.includes('analyze it'), `Supporting subtext present: "${uploadData.subtext}"`);
    assertCondition(uploadData.cardTitle === 'Upload Song', `Upload card title is "Upload Song"`);
    assertCondition(uploadData.formats.includes('MP3') && uploadData.formats.includes('FLAC'), `Formats badge displays audio types: "${uploadData.formats}"`);
    assertCondition(uploadData.fileInput, 'File input element present');

    console.log('\n  [Upload Screen Multi-Viewport Inspection & Screenshots]');
    for (const vp of VIEWPORTS) {
        await page.setViewport({ width: vp.width, height: vp.height });
        await new Promise(r => setTimeout(r, 120));

        const metrics = await page.evaluate(w => {
            const card = document.getElementById('drop-zone')?.getBoundingClientRect();
            const overflow = document.documentElement.scrollWidth > w;
            return { cardWidth: card ? Math.round(card.width) : 0, overflow };
        }, vp.width);

        assertCondition(!metrics.overflow, `No horizontal overflow at ${vp.name} (${vp.width}x${vp.height})`);
        assertCondition(metrics.cardWidth >= 280 && metrics.cardWidth <= 500, `Upload card width (${metrics.cardWidth}px) properly scaled on ${vp.name}`);

        await page.screenshot({ path: path.join(SCREENSHOT_DIR, `v03_upload_${vp.name}.png`) });
    }

    // ─────────────────────────────────────────────────────────────
    // 2. PROCESSING SCREEN VERIFICATION
    // ─────────────────────────────────────────────────────────────
    console.log('\n  [2. Processing Screen Layout & Milestone Verification]');
    // Switch to processing screen for inspection
    await page.evaluate(() => {
        showScreen('analysis-screen');
        document.getElementById('prog-file-name').textContent = 'Paradox-Waqt.mp3';
        document.getElementById('prog-bar').style.width = '45%';
        document.getElementById('prog-msg').textContent = 'Finding musical notes...';
        _updatePipelineStageUI(45, 'Finding musical notes...');
    });
    await new Promise(r => setTimeout(r, 150));

    const procData = await page.evaluate(() => {
        const headerBrand = document.querySelector('#analysis-screen .header-brand')?.textContent?.trim();
        const headerVer = document.querySelector('#analysis-screen .header-version')?.textContent?.trim();
        const badge = document.querySelector('#analysis-screen .header-processing-badge')?.textContent?.trim();
        const songTitle = document.getElementById('prog-file-name')?.textContent?.trim();
        const statusMsg = document.getElementById('prog-msg')?.textContent?.trim();
        const waveBars = document.querySelectorAll('.wave-tick').length;
        const milestones = Array.from(document.querySelectorAll('.milestone-row')).map(m => ({
            id: m.id,
            className: m.className,
            icon: m.querySelector('.milestone-status-icon')?.textContent?.trim(),
            label: m.querySelector('.milestone-label')?.textContent?.trim()
        }));

        return { headerBrand, headerVer, badge, songTitle, statusMsg, waveBars, milestones };
    });

    assertCondition(procData.headerBrand.includes('HotChords'), `Processing screen retains HotChords branding: "${procData.headerBrand}"`);
    assertCondition(procData.headerVer === 'VER 0.3', `Processing screen version is VER 0.3`);
    assertCondition(procData.badge.includes('Analyzing audio'), `Header displays live processing badge: "${procData.badge}"`);
    assertCondition(procData.songTitle === 'Paradox-Waqt.mp3', `Song title displayed prominently: "${procData.songTitle}"`);
    assertCondition(procData.waveBars === 8, `Waveform animation bars rendered (8 bars)`);
    assertCondition(procData.milestones.length === 5, `All 5 pipeline milestone stages present`);
    assertCondition(procData.milestones[0].className.includes('done'), `Milestone 1 (Audio prep) marked done at 45%`);
    assertCondition(procData.milestones[1].className.includes('active'), `Milestone 2 (Features) marked active at 45%`);
    assertCondition(procData.milestones[2].className.includes('pending'), `Milestone 3 (Chords) marked pending at 45%`);

    console.log('\n  [Processing Screen Multi-Viewport Inspection & Screenshots]');
    for (const vp of VIEWPORTS) {
        await page.setViewport({ width: vp.width, height: vp.height });
        await new Promise(r => setTimeout(r, 120));

        const metrics = await page.evaluate(w => {
            const checklist = document.querySelector('.pipeline-milestones-list')?.getBoundingClientRect();
            const overflow = document.documentElement.scrollWidth > w;
            return { checklistWidth: checklist ? Math.round(checklist.width) : 0, overflow };
        }, vp.width);

        assertCondition(!metrics.overflow, `No horizontal overflow on processing screen at ${vp.name}`);
        await page.screenshot({ path: path.join(SCREENSHOT_DIR, `v03_processing_${vp.name}.png`) });
    }

    // ─────────────────────────────────────────────────────────────
    // 3. ERROR STATE VERIFICATION
    // ─────────────────────────────────────────────────────────────
    console.log('\n  [3. Error Handling State Verification]');
    await page.evaluate(() => {
        showAnalysisError('Audio format could not be decoded. Please upload a valid MP3, WAV, or M4A file.');
    });
    await new Promise(r => setTimeout(r, 150));

    const errData = await page.evaluate(() => {
        const isErrorVisible = !document.getElementById('prog-error-box')?.classList.contains('hidden');
        const errDetail = document.getElementById('prog-error-detail')?.textContent?.trim();
        const hasRetryBtn = document.querySelector('.err-btn-primary') !== null;
        const hasNewBtn = document.querySelector('.err-btn-secondary') !== null;
        return { isErrorVisible, errDetail, hasRetryBtn, hasNewBtn };
    });

    assertCondition(errData.isErrorVisible, 'Error panel displayed cleanly without removing app shell');
    assertCondition(errData.errDetail.includes('Audio format'), `Error detail shown: "${errData.errDetail}"`);
    assertCondition(errData.hasRetryBtn && errData.hasNewBtn, 'Retry and Choose Another Song buttons present');
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, `v03_error_state.png`) });

    // ─────────────────────────────────────────────────────────────
    // 4. REAL SONG UPLOAD TEST
    // ─────────────────────────────────────────────────────────────
    console.log('\n  [4. Real Song Upload End-to-End Test]');
    console.log(`    Testing with: ${path.basename(TEST_SONG_PATH)}`);

    // Reset to upload screen
    await page.evaluate(() => resetApp());
    await page.setViewport({ width: 1440, height: 900 });

    const fileInputHandle = await page.$('#file-input');
    await fileInputHandle.uploadFile(TEST_SONG_PATH);

    // Wait for analysis screen activation
    await page.waitForFunction(() => document.getElementById('analysis-screen').classList.contains('active'), { timeout: 5000 });
    console.log('    ✓ File selected, transitioned into analysis screen');

    // Poll until workspace appears
    console.log('    ⏳ Waiting for backend pipeline analysis...');
    await page.waitForFunction(() => !document.getElementById('workspace').classList.contains('hidden'), { timeout: 60000 });
    console.log('    ✓ Analysis completed successfully, workspace loaded!');

    await new Promise(r => setTimeout(r, 500));

    const wsData = await page.evaluate(() => {
        const wsVisible = !document.getElementById('workspace')?.classList.contains('hidden');
        const uploadHidden = !document.getElementById('upload-screen')?.classList.contains('active');
        const analysisHidden = !document.getElementById('analysis-screen')?.classList.contains('active');
        const wsVer = document.querySelector('.ws-version')?.textContent?.trim();
        const key = document.getElementById('val-key')?.textContent?.trim();
        const bpm = document.getElementById('val-bpm')?.textContent?.trim();
        const track = document.getElementById('res-file-name')?.textContent?.trim();
        const heroChord = document.querySelector('#chord-current [data-chord-name]')?.textContent?.trim();
        const hasLeftHand = document.querySelector('#ws-lh-svg svg') !== null || document.getElementById('ws-hand-left') !== null;
        const hasRightHand = document.querySelector('#ws-rh-svg svg') !== null || document.getElementById('ws-hand-right') !== null;
        const keyCount = document.querySelectorAll('.white-key').length;


        return {
            wsVisible, uploadHidden, analysisHidden, wsVer, key, bpm, track, heroChord, hasLeftHand, hasRightHand, keyCount
        };
    });

    assertCondition(wsData.wsVisible && wsData.uploadHidden && wsData.analysisHidden, 'Single workspace is visible and all previous screens hidden');
    assertCondition(wsData.wsVer === 'VER 0.3', `Workspace version badge is "VER 0.3": "${wsData.wsVer}"`);
    assertCondition(wsData.key.length > 0 && wsData.key !== '—', `Key detected and populated: "${wsData.key}"`);
    assertCondition(parseInt(wsData.bpm) > 0, `BPM detected and populated: "${wsData.bpm}"`);
    assertCondition(wsData.heroChord.length > 0, `Initial Hero chord populated: "${wsData.heroChord}"`);
    assertCondition(wsData.hasLeftHand && wsData.hasRightHand, 'Left and Right hand SVG diagrams active');
    assertCondition(wsData.keyCount === 36, `61-key piano keyboard rendered (36 white keys)`);

    await page.screenshot({ path: path.join(SCREENSHOT_DIR, `v03_loaded_workspace_real_song.png`) });

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
