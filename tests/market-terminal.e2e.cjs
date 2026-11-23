const { chromium } = require('playwright');

const BASE = process.env.BASE_URL || 'https://technofront.org';
const ROUTES = ['/us/', '/', '/fr/', '/es/', '/de/'];

(async () => {
  const browser = await chromium.launch({ headless: true });
  const failures = [];
  try {
    for (const route of ROUTES) {
      const page = await browser.newPage();
      await page.addInitScript(() => {
        localStorage.removeItem('stockpilot-terminal-watchlist-v1');
        localStorage.removeItem('stockpilot-terminal-practice-v1');
      });
      try {
        const response = await page.goto(BASE + route, { waitUntil: 'domcontentloaded', timeout: 45000 });
        if (!response || !response.ok()) throw new Error('Page HTTP status: ' + (response && response.status()));
        await page.waitForFunction(() => typeof window.StockPilotResolveSymbol === 'function', { timeout: 20000 });

        const apple = await page.evaluate(() => window.StockPilotResolveSymbol('Apple', 'NASDAQ'));
        if (apple !== 'NASDAQ:AAPL') throw new Error('Apple resolved to ' + apple);

        const terminal = page.locator('#market-terminal');
        await terminal.waitFor({ state: 'visible', timeout: 15000 });
        const symbol = page.locator('#sp-terminal-symbol');
        await symbol.fill('Apple');
        await page.locator('#sp-terminal-load').click();
        await page.waitForFunction(() => {
          const chart = document.querySelector('#sp-terminal-chart');
          return !!chart && !!chart.querySelector('script[src*="embed-widget-advanced-chart.js"]');
        }, { timeout: 15000 });

        const tabs = page.locator('#market-terminal [data-sp-tool]');
        if (await tabs.count() !== 5) throw new Error('Expected five terminal tabs; found ' + await tabs.count());
        for (let i = 0; i < 5; i++) {
          await tabs.nth(i).click();
          const panel = page.locator('#sp-terminal-tool-panel-' + i);
          await panel.waitFor({ state: 'visible', timeout: 5000 });
          if (!(await panel.evaluate(el => el.classList.contains('is-active')))) {
            throw new Error('Terminal tab ' + i + ' did not activate its panel');
          }
        }

        await page.locator('#sp-terminal-watch-input').fill('Apple');
        await page.locator('#sp-terminal-watch-add').click();
        await page.locator('#sp-terminal-watch-list').getByText('AAPL', { exact: true }).waitFor({ timeout: 10000 });

        await page.locator('#sp-terminal-screen-search').fill('Apple');
        await page.locator('#sp-terminal-screen-search').waitFor();
        await page.locator('#sp-terminal-ta-widget').waitFor();
        await page.locator('#sp-terminal-tool-panel-2').waitFor();

        await page.locator('#sp-terminal-paper-symbol').fill('Apple');
        await page.locator('#sp-terminal-paper-units').fill('1');
        await page.locator('#sp-terminal-paper-entry').fill('100');
        await page.locator('#sp-terminal-paper-add').click();
        await page.locator('#sp-terminal-paper-list').getByText('AAPL', { exact: false }).waitFor({ timeout: 10000 });

        console.log('PASS ' + route + ' terminal tabs, Apple resolver, chart embed injection, watchlist and practice entry');
      } catch (error) {
        failures.push(route + ': ' + (error && error.stack || error));
        console.error('FAIL ' + route + ': ' + (error && error.message || error));
      } finally {
        await page.close();
      }
    }

    // A non-hard-coded company name exercises the live symbol-search service.
    const page = await browser.newPage();
    try {
      await page.goto(BASE + '/us/', { waitUntil: 'domcontentloaded', timeout: 45000 });
      await page.waitForFunction(() => typeof window.StockPilotResolveSymbol === 'function', { timeout: 20000 });
      const result = await page.evaluate(() => window.StockPilotResolveSymbol('Microsoft Corporation', 'NASDAQ'));
      if (result !== 'NASDAQ:MSFT') throw new Error('Microsoft resolved to ' + result);
      console.log('PASS live company-name lookup: Microsoft Corporation → NASDAQ:MSFT');
    } catch (error) {
      failures.push('live company-name lookup: ' + (error && error.stack || error));
      console.error('FAIL live company-name lookup: ' + (error && error.message || error));
    } finally {
      await page.close();
    }
  } finally {
    await browser.close();
  }

  if (failures.length) {
    console.error('\nEND-TO-END FAILURES\n' + failures.join('\n\n'));
    process.exit(1);
  }
  console.log('\nALL MARKET TERMINAL END-TO-END CHECKS PASSED');
})();
