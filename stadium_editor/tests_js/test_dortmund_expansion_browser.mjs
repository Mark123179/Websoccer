import test from 'node:test';
import assert from 'node:assert/strict';
import {chromium} from 'playwright-core';

// Run against the read-only Django preview:
// DORTMUND_TEST_URL=http://127.0.0.1:5000/stadion/dortmund/original-miniatur/ \
//   node --test stadium_editor/tests_js/test_dortmund_expansion_browser.mjs
const url = process.env.DORTMUND_TEST_URL ||
  'http://127.0.0.1:5000/stadion/dortmund/original-miniatur/';

test('successive 3D expansions and reset update the view without browser errors', async () => {
  const browser = await chromium.launch({
    executablePath: process.env.CHROMIUM_PATH || '/repl/tools/bin/chromium',
    headless: true,
    args: ['--enable-unsafe-swiftshader', '--use-gl=angle',
      '--use-angle=swiftshader', '--disable-dev-shm-usage', '--no-sandbox'],
  });
  try {
    const page = await browser.newPage({viewport: {width: 1100, height: 750}});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(url, {waitUntil: 'domcontentloaded'});
    await page.waitForFunction(() => document.querySelector('#metrics')
      ?.textContent?.includes('fps'), null, {timeout: 60000});
    const total = () => page.locator('#seat-count').textContent();
    assert.match(await total(), /71\.659 modellierte Sitze/);

    await page.locator('[data-side="back"][data-action="plus"]').click();
    assert.match(await total(), /72\.899 modellierte Sitze/);
    await page.locator('[data-side="right"][data-action="plus"]').click();
    assert.match(await total(), /74\.039 modellierte Sitze/);
    await page.locator('[data-side="back"][data-action="minus"]').click();
    assert.match(await total(), /72\.799 modellierte Sitze/);
    await page.locator('[data-preset="original"]').click();
    assert.match(await total(), /71\.659 modellierte Sitze/);
    assert.equal(await page.locator('#fallback').getAttribute('hidden'), '');
    assert.equal(await page.locator('#scene canvas').count(), 1);
    assert.deepEqual(errors, [], 'no click may crash a scene update');
  } finally {
    await browser.close();
  }
});