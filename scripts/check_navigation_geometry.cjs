/* Real-browser shell regression. Baselines and exported HTML live in /tmp.
 * python scripts/capture_navigation_pages.py /tmp/navigation-before
 * node scripts/check_navigation_geometry.cjs baseline /tmp/navigation-before
 * python scripts/capture_navigation_pages.py /tmp/navigation-after
 * node scripts/check_navigation_geometry.cjs verify /tmp/navigation-after
 */
const {chromium} = require("playwright-core");
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const [mode, directory] = process.argv.slice(2);
const origin = `https://${process.env.REPLIT_DEV_DOMAIN}`;
const selectors = [
    ".dashboard-scaler", ".navbar", ".container", ".ws-game-header",
    ".overview-artboard", ".overview-content", ".overview-grid",
    ".tactics-template-grid", ".tactics-artboard", ".match-preview-panels",
    ".match-preview-panel", ".dashboard-artboard", ".clubs-layout-grid",
    ".aaa-profile", ".club-shell",
    ".overview-card", ".overview-chat-card", ".overview-transfer-card",
    ".overview-table-card", ".overview-news-card", ".overview-social-card",
];
async function measure(page) {
    return page.evaluate(selectors => {
        const result = {};
        for (const selector of selectors) {
            result[selector] = [...document.querySelectorAll(selector)].map(node => {
                const r = node.getBoundingClientRect();
                return [r.x, r.y, r.width, r.height];
            });
        }
        const stage = document.querySelector(".dashboard-scaler");
        const scroll = document.querySelector(".gameScroll");
        result.scale = getComputedStyle(stage).transform;
        result.scroll = [scroll.clientWidth, scroll.clientHeight, scroll.scrollWidth, scroll.scrollHeight];
        result.font = getComputedStyle(document.querySelector(".container")).fontSize;
        return result;
    }, selectors);
}
(async () => {
    const browser = await chromium.launch({executablePath: "/repl/tools/bin/chromium",
        args: ["--no-sandbox", "--disable-dev-shm-usage"]});
    const context = await browser.newContext({viewport: {width: 1440, height: 900}});
    const page = await context.newPage();
    const routes = JSON.parse(fs.readFileSync(path.join(directory, "routes.json")));
    await page.route("**/*", async route => {
        const request = route.request();
        const entry = Object.entries(routes).find(([, url]) => new URL(request.url()).pathname === url);
        if (request.isNavigationRequest() && entry) {
            return route.fulfill({contentType: "text/html",
                body: fs.readFileSync(path.join(directory, `${entry[0]}.html`))});
        }
        return route.continue();
    });
    for (const [name, url] of Object.entries(routes)) {
        await page.goto(origin + url);
        await page.waitForFunction(() => document.querySelector(".dashboard-scaler")?.style.visibility === "visible");
        await page.waitForTimeout(700);
        const value = await measure(page);
        if (mode === "baseline") {
            fs.writeFileSync(path.join(directory, `${name}.json`), JSON.stringify(value, null, 2));
            await page.screenshot({path: path.join(directory, `${name}.png`)});
        } else {
            const before = JSON.parse(fs.readFileSync(`/tmp/navigation-before/${name}.json`));
            assert.deepEqual(value, before, `${name}: expanded Golden geometry`);
            await page.locator("#nav-toggle").click();
            await page.waitForTimeout(200);
            const collapsed = await measure(page);
            assert.equal(collapsed.scale, before.scale, `${name}: unchanged scale`);
            assert.equal(collapsed.font, before.font, `${name}: unchanged font`);
            const gain = (232 - 80) * 1440 / 1884;
            assert.ok(Math.abs(collapsed[".container"][0][2] - before[".container"][0][2] - gain) < 0.02);
            assert.equal(collapsed[".container"][0][1], before[".container"][0][1]);
            assert.equal(collapsed[".ws-game-header"][0][3], before[".ws-game-header"][0][3]);
            assert.equal(collapsed.scroll[2], before.scroll[2], `${name}: no new horizontal scroll`);
            for (const selector of selectors.filter(s => s.startsWith(".overview-") || s === ".match-preview-panel")) {
                collapsed[selector].forEach((rect, index) => {
                    assert.ok(Math.abs(rect[3] - before[selector][index][3]) < 0.02,
                        `${name}: ${selector} height unchanged`);
                    assert.ok(Math.abs(rect[1] - before[selector][index][1]) < 0.02,
                        `${name}: ${selector} vertical track unchanged`);
                });
            }
            await page.screenshot({path: path.join(directory, `${name}-collapsed.png`)});
            await page.locator("#nav-toggle").click();
            await page.waitForTimeout(200);
            assert.deepEqual(await measure(page), before, `${name}: reversible Golden geometry`);
        }
        console.log(`${name}: ${mode} OK`);
    }
    if (mode !== "baseline") {
        await page.goto(origin + routes.preview);
        await page.waitForTimeout(700);
        const saved = await page.evaluate(() => {
            const root = document.querySelector(".match-preview-scene");
            const canvas = root.querySelector(".match-preview-panels");
            const canvasRect = canvas.getBoundingClientRect();
            const scale = canvasRect.width / canvas.offsetWidth;
            const nodes = {};
            for (const node of canvas.querySelectorAll("[data-mp-layout-item]")) {
                const parent = node.parentElement.closest("[data-mp-layout-item]") || canvas;
                const r = node.getBoundingClientRect(), p = parent.getBoundingClientRect();
                nodes[node.dataset.mpLayoutItem] = {
                    x: ((r.left - p.left) / scale - parent.clientLeft) / parent.clientWidth * 100,
                    y: ((r.top - p.top) / scale - parent.clientTop) / parent.clientHeight * 100,
                    width: r.width / scale / parent.clientWidth * 100,
                    height: r.height / scale / parent.clientHeight * 100,
                    hidden: false,
                };
            }
            // Representative personal composition, not just the factory layout.
            nodes["competition-0"].x += 0.5;
            const value = JSON.stringify({version: 1, revision: Number(root.dataset.layoutRevision),
                detailPatch: Number(root.dataset.layoutDetailPatch), nodes});
            const key = `fm:match-preview:layout:1:${root.dataset.layoutOwner || "guest"}`;
            localStorage.setItem(key, value);
            return {key, value};
        });
        await page.reload();
        await page.waitForTimeout(700);
        assert.ok(await page.locator(".mp-layout-free").count(), "saved composition restored");
        const personal = await measure(page);
        await page.locator("#nav-toggle").focus();
        await page.keyboard.press("Enter");
        await page.waitForTimeout(200);
        assert.equal(await page.locator("#nav-toggle").getAttribute("aria-expanded"), "false");
        const icons = await measure(page);
        assert.equal(icons.scale, personal.scale);
        personal[".match-preview-panel"].forEach((r, i) =>
            assert.ok(Math.abs(r[3] - icons[".match-preview-panel"][i][3]) < 0.02));
        await page.reload();
        await page.waitForTimeout(700);
        assert.equal(await page.locator("#nav-toggle").getAttribute("aria-expanded"), "false");
        assert.equal(await page.evaluate(key => localStorage.getItem(key), saved.key), saved.value,
            "navigation must not rewrite the stored personal composition");
        await page.locator(".nav-menu a").first().focus();
        assert.equal(await page.locator(".nav-menu a").first().evaluate(node =>
            getComputedStyle(node, "::after").display), "block", "keyboard tooltip");
        await page.locator(".nav-menu a").nth(1).hover();
        assert.equal(await page.locator(".nav-menu a").nth(1).evaluate(node =>
            getComputedStyle(node, "::after").display), "block", "hover tooltip");
        await page.locator("#nav-search-open").click();
        assert.ok(await page.locator("#nav-search-input").evaluate(node => node === document.activeElement));
        await page.waitForTimeout(200);
        assert.deepEqual(await measure(page), personal, "personal composition survives return to expanded");
        for (const viewport of [{width: 1920, height: 1080}, {width: 2560, height: 1440}, {width: 390, height: 844}]) {
            await page.setViewportSize(viewport);
            await page.waitForTimeout(200);
            const expanded = await measure(page);
            if (viewport.width > 760) await page.locator("#nav-toggle").click();
            else await page.evaluate(() => { document.documentElement.dataset.navState = "collapsed"; });
            await page.waitForTimeout(200);
            const compact = await measure(page);
            assert.equal(compact.scale, expanded.scale);
            if (viewport.width > 760) {
                assert.ok(compact[".container"][0][2] > expanded[".container"][0][2]);
                await page.locator("#nav-toggle").click();
            } else {
                assert.deepEqual(compact, expanded, "mobile ignores desktop collapsed preference");
                assert.ok(await page.locator("#nav-toggle").isHidden());
                assert.ok(await page.locator("#nav-search-input").isVisible());
            }
        }
        console.log("Personal preview, keyboard/hover labels, reload, search and wide/mobile: OK");
    }
    await browser.close();
})().catch(error => { console.error(error); process.exit(1); });