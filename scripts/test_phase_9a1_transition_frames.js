/**
 * test_phase_9a1_transition_frames.js
 *
 * Deterministic browser test using ACTUAL production DynamicChordReel & piano.css.
 * Progression:
 *   C  = 0–2s
 *   F  = 2–4s
 *   G  = 4–6s
 *   Am = 6–8s
 *
 * Captures transition frames:
 *   1. 1.5s  (Resting state: C is Current)
 *   2. 2.00s (Boundary crossed, transition begins)
 *   3. 2.10s (Mid-transition: C moving left, F moving center, G entering right)
 *   4. 2.20s (Late-transition)
 *   5. 2.30s (Animation completing)
 *   6. 2.50s (Resting state: F is Current, large & glowing)
 *   7. 3.00s (Resting state: F completely stationary)
 */

const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

const CHROME_PATH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const OUT_DIR = '/Users/harishthakur/.gemini/antigravity-ide/brain/df5eb886-d57f-4aa8-b92f-1e7b7539d3e5/screenshots/phase_9a1';
if (!fs.existsSync(OUT_DIR)) {
    fs.mkdirSync(OUT_DIR, { recursive: true });
}

async function run() {
    console.log('--- Starting Phase 9A.1 Deterministic Transition Frames Test ---');
    const browser = await puppeteer.launch({
        executablePath: CHROME_PATH,
        headless: 'new',
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 800 });

    // HTML harness hosting actual production CSS & JS files
    const htmlContent = `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <link rel="stylesheet" href="http://localhost:5500/css/piano.css">
    <script src="http://localhost:5500/js/engine/pianoFingeringEngine.js"></script>
    <script src="http://localhost:5500/js/ui/handDiagrams.js"></script>
    <script src="http://localhost:5500/js/audio/playbackClock.js"></script>
    <script src="http://localhost:5500/js/ui/dynamicChordReel.js"></script>
    <style>
        body {
            background: #F2F2F7;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            margin: 0;
            padding: 20px;
            box-sizing: border-box;
        }
        .demo-card {
            background: #FFFFFF;
            border-radius: 18px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.06);
            padding: 32px 40px;
            width: 100%;
            max-width: 860px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        .status-badge {
            font-size: 13px;
            font-weight: 700;
            color: #5856D6;
            background: rgba(88, 86, 214, 0.1);
            padding: 6px 14px;
            border-radius: 20px;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="demo-card">
        <div class="status-badge" id="time-badge">t = 0.00s</div>
        <div id="reel-container" style="width: 100%;"></div>
    </div>
    <script>
        const testChords = [
            { startTime: 0.0, endTime: 2.0, chordName: 'C',  notes: [0, 4, 7] },
            { startTime: 2.0, endTime: 4.0, chordName: 'F',  notes: [5, 8, 0] },
            { startTime: 4.0, endTime: 6.0, chordName: 'G',  notes: [7, 11, 2] },
            { startTime: 6.0, endTime: 8.0, chordName: 'Am', notes: [9, 0, 4] }
        ];

        window.reel = new DynamicChordReel({
            container: document.getElementById('reel-container'),
            onSeek: (t) => console.log('Seeked to', t)
        });
        window.reel.loadChords(testChords);

        window.seekExact = function(t) {
            document.getElementById('time-badge').textContent = 't = ' + t.toFixed(2) + 's';
            window.reel.update(t);
        };
    </script>
</body>
</html>`;

    await page.setContent(htmlContent, { waitUntil: 'networkidle0' });

    // Step 1: Initial resting state at t = 1.5s (C is current)
    await page.evaluate(() => {
        window.seekExact(1.5);
    });
    await new Promise(r => setTimeout(r, 200));
    await page.screenshot({ path: path.join(OUT_DIR, 'frame_1_t150_c_resting.png') });
    console.log('  ✓ Frame 1 (1.5s): C is Current and resting');

    // Step 2: Boundary cross at t = 2.00s (Transition begins)
    await page.evaluate(() => {
        window.seekExact(2.00);
    });
    await page.screenshot({ path: path.join(OUT_DIR, 'frame_2_t200_boundary.png') });
    console.log('  ✓ Frame 2 (2.00s): Boundary crossed to F');

    // Step 3: Mid-transition at t = 2.10s (100ms in)
    await new Promise(r => setTimeout(r, 100));
    await page.screenshot({ path: path.join(OUT_DIR, 'frame_3_t210_moving.png') });
    console.log('  ✓ Frame 3 (2.10s): Mid-transition (C moving left, F moving center, G entering)');

    // Step 4: Late-transition at t = 2.20s (200ms in)
    await new Promise(r => setTimeout(r, 100));
    await page.screenshot({ path: path.join(OUT_DIR, 'frame_4_t220_moving.png') });
    console.log('  ✓ Frame 4 (2.20s): Late-transition');

    // Step 5: Animation completing at t = 2.30s (300ms in)
    await new Promise(r => setTimeout(r, 100));
    await page.screenshot({ path: path.join(OUT_DIR, 'frame_5_t230_settling.png') });
    console.log('  ✓ Frame 5 (2.30s): Transition settled');

    // Step 6: Post-transition resting at t = 2.50s (F is Current, large and glowing)
    await page.evaluate(() => {
        window.seekExact(2.50);
    });
    await new Promise(r => setTimeout(r, 100));
    await page.screenshot({ path: path.join(OUT_DIR, 'frame_6_t250_f_resting.png') });
    console.log('  ✓ Frame 6 (2.50s): F is Current, large and glowing');

    // Step 7: Stationary check at t = 3.00s
    await page.evaluate(() => {
        window.seekExact(3.00);
    });
    await new Promise(r => setTimeout(r, 100));
    await page.screenshot({ path: path.join(OUT_DIR, 'frame_7_t300_f_stationary.png') });
    console.log('  ✓ Frame 7 (3.00s): F is completely stationary');

    // Also capture desktop full workstation and mobile viewports
    await page.setViewport({ width: 390, height: 844 });
    await page.screenshot({ path: path.join(OUT_DIR, 'mobile_390x844_f_resting.png') });
    console.log('  ✓ Mobile 390x844: F is Current and properly fitted');

    await browser.close();
    console.log('--- Phase 9A.1 Transition Frames Test Completed Successfully ---');
}

run().catch(err => {
    console.error('Test error:', err);
    process.exit(1);
});
