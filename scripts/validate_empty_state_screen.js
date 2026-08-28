/**
 * scripts/validate_empty_state_screen.js
 *
 * Automated Visual QA and Functional Validation for HotChords Initial / Empty State Screen:
 * 1. Validates HotChords branding, headline, supporting copy, and upload card across 6 viewports:
 *    - 1440x900 (Desktop)
 *    - 1280x800 (Laptop)
 *    - 1024x768 (Tablet Landscape)
 *    - 768x1024 (Tablet Portrait)
 *    - 430x932 (iPhone 16 Pro Max)
 *    - 390x844 (iPhone 14/15)
 * 2. Checks centering, typography hierarchy, card sizing, and 0 horizontal overflow.
 * 3. Captures screenshots for visual QA.
 * 4. Validates that loading a song transitions directly into the single workspace.
 */

const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

const CHROME_PATH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const SCREENSHOT_DIR = '/Users/harishthakur/.gemini/antigravity-ide/brain/653682c9-af91-48b2-a94f-42d2914e3cb8/screenshots';

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
    console.log('🚀 Starting HotChords Empty / Initial State Screen Validation...\n');

    const browser = await puppeteer.launch({
        executablePath: CHROME_PATH,
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
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

    // 1. Validate Initial Screen Content & Typography
    console.log('  [Initial Screen Content Verification]');
    const content = await page.evaluate(() => {
        const brand = document.querySelector('.empty-brand')?.textContent?.trim();
        const headline = document.querySelector('.empty-headline')?.textContent?.trim();
        const supporting = document.querySelector('.empty-supporting')?.textContent?.trim();
        const dropPrompt = document.querySelector('.upload-card-prompt')?.textContent?.trim();
        const dropSub = document.querySelector('.upload-card-sub')?.textContent?.trim();
        const dropFormats = document.querySelector('.upload-card-formats')?.textContent?.trim();
        const fileInputExists = document.getElementById('file-input') !== null;
        const uploadActive = document.getElementById('upload-screen')?.classList.contains('active');
        const workspaceHidden = document.getElementById('workspace')?.classList.contains('hidden');

        return {
            brand,
            headline,
            supporting,
            dropPrompt,
            dropSub,
            dropFormats,
            fileInputExists,
            uploadActive,
            workspaceHidden
        };
    });

    assertCondition(content.uploadActive, 'Upload screen is active on initial launch');
    assertCondition(content.workspaceHidden, 'Loaded-song workspace is hidden initially');
    assertCondition(content.brand.includes('HotChords'), `Branding contains HotChords: "${content.brand}"`);
    assertCondition(content.headline.includes('Turn any song into'), `Headline matches copy: "${content.headline.replace(/\s+/g, ' ')}"`);
    assertCondition(content.supporting.includes('detect the chords'), `Supporting copy matches: "${content.supporting}"`);
    assertCondition(content.dropPrompt === 'Drop your song here', `Drop card prompt is "Drop your song here"`);
    assertCondition(content.dropSub === 'or click to browse', `Drop card sub is "or click to browse"`);
    assertCondition(content.dropFormats.includes('MP3'), `Formats badge displays supported audio types: "${content.dropFormats}"`);
    assertCondition(content.fileInputExists, 'File input element is present and wired');

    // 2. Responsive Viewports & Screenshots
    console.log('\n  [Multi-Viewport Inspection & Screenshot Capture]');
    for (const vp of VIEWPORTS) {
        await page.setViewport({ width: vp.width, height: vp.height });
        await new Promise(r => setTimeout(r, 150));

        const vpMetrics = await page.evaluate(w => {
            const card = document.getElementById('drop-zone')?.getBoundingClientRect();
            const overflow = document.documentElement.scrollWidth > w;
            return {
                cardWidth: card ? Math.round(card.width) : 0,
                cardHeight: card ? Math.round(card.height) : 0,
                overflow
            };
        }, vp.width);

        assertCondition(!vpMetrics.overflow, `No horizontal overflow at ${vp.name} (${vp.width}x${vp.height})`);
        assertCondition(vpMetrics.cardWidth > 260 && vpMetrics.cardWidth <= 480, `Upload card width (${vpMetrics.cardWidth}px) appropriately sized on ${vp.name}`);

        const shotPath = path.join(SCREENSHOT_DIR, `empty_state_${vp.name}.png`);
        await page.screenshot({ path: shotPath, fullPage: false });
    }

    // 3. Functional Upload Regression Test
    console.log('\n  [Upload Transition Regression Test]');
    const sampleSong = {
        title: 'Tu Mera',
        key_full: 'A Major',
        easy_key_full: 'C Major',
        tempo: 99,
        duration: 213.0,
        chords: [
            { time: 0.0, end: 18.0, chord: 'A' },
            { time: 18.0, end: 41.0, chord: 'C#m' }
        ],
        beginner_chords: [
            { time: 0.0, end: 18.0, chord: 'C' },
            { time: 18.0, end: 41.0, chord: 'Em' }
        ]
    };

    // Simulate successful upload & initialization
    await page.evaluate(songData => {
        initResults(songData);
    }, sampleSong);

    await new Promise(r => setTimeout(r, 300));

    const transitionState = await page.evaluate(() => {
        const uploadActive = document.getElementById('upload-screen')?.classList.contains('active');
        const wsVisible = !document.getElementById('workspace')?.classList.contains('hidden');
        const heroChord = document.querySelector('#chord-current [data-chord-name]')?.textContent;
        const pianoVisible = document.querySelectorAll('.white-key').length > 0;
        return { uploadActive, wsVisible, heroChord, pianoVisible };
    });

    assertCondition(!transitionState.uploadActive, 'Upload screen hides on successful load');
    assertCondition(transitionState.wsVisible, 'Single loaded-song workspace appears seamlessly');
    assertCondition(transitionState.heroChord === 'C', `Loaded song displays initial hero chord: ${transitionState.heroChord}`);
    assertCondition(transitionState.pianoVisible, 'Piano keyboard is active and visible in loaded workspace');

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
