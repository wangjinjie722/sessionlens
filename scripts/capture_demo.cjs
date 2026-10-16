// Capture real rendered demo pages as a five-scene, 25-second walkthrough.
// The reading pauses are editorial; this is not a latency benchmark.
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

const root = path.resolve(__dirname, '..');
const reports = path.join(root, 'reports');
const assets = path.join(root, 'docs', 'assets');

(async () => {
  fs.mkdirSync(assets, { recursive: true });
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.SESSIONLENS_BROWSER_EXECUTABLE ? { executablePath: process.env.SESSIONLENS_BROWSER_EXECUTABLE } : {}),
  });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 });
    const frame = async number => {
      await page.screenshot({ path: path.join(reports, `demo-frame-${number}.png`) });
    };
    await page.goto(pathToFileURL(path.join(reports, 'public-terminal.html')).href);
    await frame(1);
    await page.goto(pathToFileURL(path.join(reports, 'public-demo.html')).href);
    await frame(2);
    await page.locator('summary').first().click();
    await page.locator('details').first().scrollIntoViewIfNeeded();
    await frame(3);
    fs.copyFileSync(path.join(reports, 'demo-frame-3.png'), path.join(assets, 'report-preview.png'));
    await page.getByText('Candidate instruction', { exact: true }).first().scrollIntoViewIfNeeded();
    await frame(4);
    await page.evaluate(() => window.scrollTo(0, 0));
    await frame(5);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
    if (overflow) throw new Error('Demo layout overflows the viewport.');
    fs.writeFileSync(path.join(reports, 'demo-frames.txt'),
      [1, 2, 3, 4, 5].map(n => `file 'demo-frame-${n}.png'\nduration 5`).join('\n') + "\nfile 'demo-frame-5.png'\n");
    console.log('Captured five synthetic demo scenes and the report preview.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
