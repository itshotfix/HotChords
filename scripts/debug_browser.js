const puppeteer = require('puppeteer-core');
const CHROME_PATH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

(async () => {
    const browser = await puppeteer.launch({
        executablePath: CHROME_PATH,
        headless: 'new',
        args: ['--no-sandbox']
    });
    const page = await browser.newPage();
    page.on('console', msg => console.log('PAGE LOG:', msg.text()));
    page.on('pageerror', err => console.log('PAGE ERROR:', err.message));

    await page.goto('http://localhost:5500', { waitUntil: 'networkidle0' });

    const result = await page.evaluate(async () => {
        try {
            window.DATA = {
                duration: 16.0,
                tempo: 120,
                key: 'C',
                key_full: 'C Major',
                easy_key: 'C',
                easy_key_full: 'C Major',
                time_sig: '4/4',
                file: 'test.mp3',
                chords: [{ time: 0, end: 4, chord: 'C' }, { time: 4, end: 8, chord: 'G' }],
                beginner_chords: [{ time: 0, end: 4, chord: 'C' }, { time: 4, end: 8, chord: 'G' }]
            };
            await window.initResults();
            const activeScreen = document.querySelector('.screen.active');
            return {
                activeScreenId: activeScreen ? activeScreen.id : null,
                resultsDisplay: document.getElementById('results-screen').style.display,
                resultsClass: document.getElementById('results-screen').className
            };
        } catch (e) {
            return { error: e.stack };
        }
    });

    console.log('INIT RESULT:', result);
    await browser.close();
})();
