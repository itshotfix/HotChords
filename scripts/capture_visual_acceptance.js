/**
 * scripts/capture_visual_acceptance.js
 * 
 * Automates real-browser visual inspection and screenshot capture
 * across 6 viewports and all 3 primary tabs.
 */

const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

const CHROME_PATH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const ARTIFACTS_DIR = '/Users/harishthakur/.gemini/antigravity-ide/brain/df5eb886-d57f-4aa8-b92f-1e7b7539d3e5/screenshots';

const VIEWPORTS = [
    { width: 1440, height: 900, name: '1440x900' },
    { width: 1280, height: 800, name: '1280x800' },
    { width: 1024, height: 768, name: '1024x768' },
    { width: 768, height: 1024, name: '768x1024' },
    { width: 430, height: 932, name: '430x932' },
    { width: 390, height: 844, name: '390x844' }
];

const MODES = [
    { id: 'simplified_chords', tabBtnId: 'tab-simplified-chords', name: 'simplified_chords' },
    { id: 'practice', tabBtnId: 'tab-practice', name: 'practice' },
    { id: 'play_track', tabBtnId: 'tab-play-track', name: 'play_track' }
];

// Rich 4-minute realistic song with 32 chord changes and synchronized lyrics
const SAMPLE_RICH_SONG = {
    duration: 240.0,
    tempo: 118,
    key: 'F#',
    key_full: 'F# Major',
    easy_key: 'C',
    easy_key_full: 'C Major',
    time_sig: '4/4',
    file: 'Let_It_Be_Remastered.mp3',
    chords: [
        { time: 0.0, end: 4.0, chord: 'F#' },
        { time: 4.0, end: 8.0, chord: 'C#' },
        { time: 8.0, end: 12.0, chord: 'D#m' },
        { time: 12.0, end: 16.0, chord: 'B' },
        { time: 16.0, end: 20.0, chord: 'F#' },
        { time: 20.0, end: 24.0, chord: 'C#' },
        { time: 24.0, end: 28.0, chord: 'B' },
        { time: 28.0, end: 32.0, chord: 'F#' },
        { time: 32.0, end: 36.0, chord: 'D#m' },
        { time: 36.0, end: 40.0, chord: 'C#' },
        { time: 40.0, end: 44.0, chord: 'B' },
        { time: 44.0, end: 48.0, chord: 'F#' },
        { time: 48.0, end: 52.0, chord: 'F#' },
        { time: 52.0, end: 56.0, chord: 'C#' },
        { time: 56.0, end: 60.0, chord: 'D#m' },
        { time: 60.0, end: 64.0, chord: 'B' }
    ],
    beginner_chords: [
        { time: 0.0, end: 4.0, chord: 'C' },
        { time: 4.0, end: 8.0, chord: 'G' },
        { time: 8.0, end: 12.0, chord: 'Am' },
        { time: 12.0, end: 16.0, chord: 'F' },
        { time: 16.0, end: 20.0, chord: 'C' },
        { time: 20.0, end: 24.0, chord: 'G' },
        { time: 24.0, end: 28.0, chord: 'F' },
        { time: 28.0, end: 32.0, chord: 'C' },
        { time: 32.0, end: 36.0, chord: 'Am' },
        { time: 36.0, end: 40.0, chord: 'G' },
        { time: 40.0, end: 44.0, chord: 'F' },
        { time: 44.0, end: 48.0, chord: 'C' },
        { time: 48.0, end: 52.0, chord: 'C' },
        { time: 52.0, end: 56.0, chord: 'G' },
        { time: 56.0, end: 60.0, chord: 'Am' },
        { time: 60.0, end: 64.0, chord: 'F' }
    ],
    transcript: {
        segments: [
            { start_time: 0.0, end_time: 4.0, text: 'When I find myself in times of trouble', words: [
                { start_time: 0.2, end_time: 0.8, text: 'When' },
                { start_time: 0.9, end_time: 1.4, text: 'I' },
                { start_time: 1.5, end_time: 2.2, text: 'find' },
                { start_time: 2.3, end_time: 3.0, text: 'myself' },
                { start_time: 3.1, end_time: 3.9, text: 'in' }
            ]},
            { start_time: 4.0, end_time: 8.0, text: 'Mother Mary comes to me', words: [
                { start_time: 4.2, end_time: 5.0, text: 'Mother' },
                { start_time: 5.1, end_time: 6.0, text: 'Mary' },
                { start_time: 6.1, end_time: 7.0, text: 'comes' },
                { start_time: 7.1, end_time: 7.9, text: 'to me' }
            ]},
            { start_time: 8.0, end_time: 12.0, text: 'Speaking words of wisdom, let it be', words: [
                { start_time: 8.2, end_time: 9.0, text: 'Speaking' },
                { start_time: 9.1, end_time: 9.9, text: 'words' },
                { start_time: 10.0, end_time: 10.8, text: 'of' },
                { start_time: 10.9, end_time: 11.5, text: 'wisdom' },
                { start_time: 11.6, end_time: 12.0, text: 'let it be' }
            ]},
            { start_time: 12.0, end_time: 16.0, text: 'And in my hour of darkness', words: [
                { start_time: 12.2, end_time: 13.0, text: 'And' },
                { start_time: 13.1, end_time: 14.0, text: 'in' },
                { start_time: 14.1, end_time: 15.0, text: 'my' },
                { start_time: 15.1, end_time: 16.0, text: 'hour' }
            ]},
            { start_time: 16.0, end_time: 20.0, text: 'She is standing right in front of me', words: [
                { start_time: 16.2, end_time: 17.0, text: 'She' },
                { start_time: 17.1, end_time: 18.0, text: 'is' },
                { start_time: 18.1, end_time: 19.0, text: 'standing' },
                { start_time: 19.1, end_time: 20.0, text: 'right' }
            ]}
        ]
    },
    beginner_chord_lyric_map: {
        alignments: [
            { chord_name: 'C', chord_start: 0.0, chord_end: 4.0, anchor_word: { segment_index: 0, word_index: 0 } },
            { chord_name: 'G', chord_start: 4.0, chord_end: 8.0, anchor_word: { segment_index: 1, word_index: 0 } },
            { chord_name: 'Am', chord_start: 8.0, chord_end: 12.0, anchor_word: { segment_index: 2, word_index: 0 } },
            { chord_name: 'F', chord_start: 12.0, chord_end: 16.0, anchor_word: { segment_index: 3, word_index: 0 } },
            { chord_name: 'C', chord_start: 16.0, chord_end: 20.0, anchor_word: { segment_index: 4, word_index: 0 } }
        ]
    },
    chord_lyric_map: {
        alignments: [
            { chord_name: 'F#', chord_start: 0.0, chord_end: 4.0, anchor_word: { segment_index: 0, word_index: 0 } },
            { chord_name: 'C#', chord_start: 4.0, chord_end: 8.0, anchor_word: { segment_index: 1, word_index: 0 } },
            { chord_name: 'D#m', chord_start: 8.0, chord_end: 12.0, anchor_word: { segment_index: 2, word_index: 0 } },
            { chord_name: 'B', chord_start: 12.0, chord_end: 16.0, anchor_word: { segment_index: 3, word_index: 0 } },
            { chord_name: 'F#', chord_start: 16.0, chord_end: 20.0, anchor_word: { segment_index: 4, word_index: 0 } }
        ]
    }
};

async function run() {
    if (!fs.existsSync(ARTIFACTS_DIR)) {
        fs.mkdirSync(ARTIFACTS_DIR, { recursive: true });
    }

    console.log('Launching headless Chrome for visual acceptance test...');
    const browser = await puppeteer.launch({
        executablePath: CHROME_PATH,
        headless: 'new',
        args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
    });

    const page = await browser.newPage();
    await page.goto('http://localhost:5500', { waitUntil: 'networkidle0' });

    // Inject rich sample data and initialize results screen
    await page.evaluate(async (song) => {
        window.DATA = song;
        await window.initResults(song);
    }, SAMPLE_RICH_SONG);

    await new Promise(r => setTimeout(r, 600));

    const report = [];

    for (const vp of VIEWPORTS) {
        console.log(`\nTesting viewport: ${vp.name} (${vp.width}x${vp.height})...`);
        await page.setViewport({ width: vp.width, height: vp.height, deviceScaleFactor: 2 });

        for (const mode of MODES) {
            // Switch mode
            await page.evaluate((m) => {
                window.setPrimaryMode(m);
            }, mode.id);

            await new Promise(r => setTimeout(r, 300));

            const screenshotFilename = `vp_${vp.name}_${mode.name}.png`;
            const screenshotPath = path.join(ARTIFACTS_DIR, screenshotFilename);
            await page.screenshot({ path: screenshotPath });

            // Analyze layout metrics and anomalies
            const metrics = await page.evaluate(() => {
                const body = document.body;
                const header = document.querySelector('.app-header');
                const meta = document.querySelector('.song-meta-strip');
                const nav = document.querySelector('.tab-nav-strip');
                const stage = document.querySelector('.music-player-stage');
                const viewport = document.querySelector('.mode-content-viewport');
                const playback = document.querySelector('.playback-bar-container');
                const piano = document.querySelector('.piano-dock');

                const getBox = el => el ? el.getBoundingClientRect() : null;

                const stageBox = getBox(stage);
                const pianoBox = getBox(piano);
                const playbackBox = getBox(playback);
                const viewportBox = getBox(viewport);

                return {
                    bodyOverflowX: body.scrollWidth > window.innerWidth,
                    bodyOverflowY: body.scrollHeight > window.innerHeight,
                    headerHeight: header ? header.offsetHeight : 0,
                    metaHeight: meta ? meta.offsetHeight : 0,
                    navHeight: nav ? nav.offsetHeight : 0,
                    stageHeight: stageBox ? stageBox.height : 0,
                    viewportHeight: viewportBox ? viewportBox.height : 0,
                    playbackHeight: playbackBox ? playbackBox.height : 0,
                    pianoHeight: pianoBox ? pianoBox.height : 0,
                    pianoVisible: pianoBox ? (pianoBox.height > 0 && pianoBox.width > 0) : false
                };
            });

            console.log(`  [${vp.name}] ${mode.name} -> Saved: ${screenshotFilename}`);
            console.log(`     Stage Height: ${Math.round(metrics.stageHeight)}px | Piano: ${Math.round(metrics.pianoHeight)}px (Visible: ${metrics.pianoVisible}) | Viewport Content: ${Math.round(metrics.viewportHeight)}px | Overflows: X=${metrics.bodyOverflowX}, Y=${metrics.bodyOverflowY}`);

            report.push({
                viewport: vp.name,
                mode: mode.name,
                metrics,
                screenshot: screenshotFilename
            });
        }
    }

    // Playback test: test seek, play, and tab switches
    console.log('\nTesting real playback timeline synchronization...');
    await page.evaluate(() => {
        window.handleSeek(6.0); // 6.0s is G in beginner / C# in original
        window.handleTogglePlay();
    });
    await new Promise(r => setTimeout(r, 1200));

    const playbackStatus = await page.evaluate(() => {
        const curTime = window.PlaybackClock.currentTime;
        const curChord = window.currentChordEngine ? window.currentChordEngine.getCurrentChord() : null;
        const isPlaying = window.PlaybackClock.state === 'PLAYING';
        const activeCell = document.querySelector('.ribbon-chord-item.active-chord, .beg-chord-cell.active-chord-cell');
        const activeChordName = activeCell ? activeCell.querySelector('.ribbon-chord-name, .beg-chord-name').textContent.trim() : null;

        return {
            curTime,
            isPlaying,
            engineChord: curChord ? curChord.chordName : null,
            domHighlightedChord: activeChordName
        };
    });

    console.log('Playback Status:', playbackStatus);

    await browser.close();
    console.log('\nVisual acceptance inspection completed successfully!');
    fs.writeFileSync(path.join(ARTIFACTS_DIR, 'report.json'), JSON.stringify({ report, playbackStatus }, null, 2));
}

run().catch(err => {
    console.error('Capture failed:', err);
    process.exit(1);
});
