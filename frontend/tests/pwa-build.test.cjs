const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const { chromium } = require('@playwright/test');

test('production PWA keeps offline navigation and explicit updates without losing local data', { timeout: 60000 }, async () => {
  const { preview } = await import('vite');
  const server = await preview({ configFile: false, preview: { host: '127.0.0.1', port: 5190, strictPort: true } });
  const browser = await chromium.launch();
  const worker = await fs.readFile('dist/sw.js', 'utf8');
  try {
    const context = await browser.newContext();
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('http://127.0.0.1:5190/');
    await page.evaluate(async () => {
      await navigator.serviceWorker.ready;
      if (!navigator.serviceWorker.controller) await new Promise(resolve => navigator.serviceWorker.addEventListener('controllerchange', resolve, { once: true }));
      await new Promise((resolve, reject) => {
        const request = indexedDB.open('pwa-regression', 1);
        request.onupgradeneeded = () => request.result.createObjectStore('pending');
        request.onerror = reject;
        request.onsuccess = () => {
          const tx = request.result.transaction('pending', 'readwrite');
          tx.objectStore('pending').put('boarding-unsynced', 'record');
          tx.oncomplete = () => { request.result.close(); resolve(); };
        };
      });
    });
    const cached = await page.evaluate(async () => (await Promise.all((await caches.keys()).map(async key => (await (await caches.open(key)).keys()).map(request => new URL(request.url).pathname)))).flat());
    assert.ok(cached.includes('/index.html'));
    assert.ok(cached.some(url => url.endsWith('.js')));
    assert.ok(cached.every(url => !url.startsWith('/api/') && !url.startsWith('/documentacao/')));
    await context.setOffline(true);
    await page.reload();
    await page.getByRole('heading', { name: 'Embarque offline', exact: true }).waitFor();
    for (const pathname of ['/api/v1/private-check', '/documentacao/private-check']) {
      const result = await page.evaluate(async pathname => {
        try { return (await fetch(pathname)).ok; } catch { return false; }
      }, pathname);
      assert.equal(result, false, `${pathname} must not receive the cached app shell`);
    }
    await context.setOffline(false);
    await fs.writeFile('dist/sw.js', `${worker}\n// PWA update regression ${Date.now()}\n`);
    await page.evaluate(async () => (await navigator.serviceWorker.getRegistration()).update());
    const update = page.getByRole('button', { name: 'Atualizar aplicativo', exact: true });
    await update.waitFor();
    assert.equal(await page.evaluate(async () => !!(await navigator.serviceWorker.getRegistration()).waiting), true);
    page.on('dialog', dialog => dialog.accept());
    await Promise.all([page.waitForEvent('load'), update.click()]);
    const record = await page.evaluate(() => new Promise(resolve => {
      const request = indexedDB.open('pwa-regression', 1);
      request.onsuccess = () => {
        const read = request.result.transaction('pending').objectStore('pending').get('record');
        read.onsuccess = () => { request.result.close(); resolve(read.result); };
      };
    }));
    assert.equal(record, 'boarding-unsynced');
    assert.deepEqual(errors, []);
    await context.close();
  } finally {
    await fs.writeFile('dist/sw.js', worker);
    await browser.close();
    await new Promise(resolve => server.httpServer.close(resolve));
  }
});
