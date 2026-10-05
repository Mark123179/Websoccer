/* Read-only browser check; /tmp/creator-asset-auth.json is generated externally.
 * No uploads or source-ID changes are performed against application data.
 */
const {chromium} = require("playwright-core");
const fs = require("node:fs");
const assert = require("node:assert/strict");

(async () => {
    const auth = JSON.parse(fs.readFileSync("/tmp/creator-asset-auth.json", "utf8"));
    const host = `https://${process.env.REPLIT_DEV_DOMAIN}`;
    const browser = await chromium.launch({
        executablePath: "/repl/tools/bin/chromium", headless: true,
        args: ["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader",
            "--enable-unsafe-swiftshader"],
    });
    try {
        const context = await browser.newContext({viewport: {width:1440, height:900}});
        await context.addCookies([{name:auth.name, value:auth.value, url:host}]);
        const page = await context.newPage();
        const errors = [];
        page.on("pageerror", error => errors.push(error.message));
        await page.goto(`${host}/creator/clubs/3/?tab=bilder`, {waitUntil:"domcontentloaded"});
        await page.locator(".creator-3d-kit").first().scrollIntoViewIfNeeded();
        assert.equal(await page.locator(".creator-3d-kit").count(), 3);
        assert.equal(await page.locator('input[name="cmtracker_id"]').count(), 1);
        const forms = await page.locator(".creator-3d-kit form").evaluateAll(elements =>
            elements.map(form => ({action:form.action, method:form.method,
                file:form.querySelector('input[type="file"]').accept,
                csrf:!!form.querySelector('input[name="csrfmiddlewaretoken"]')})));
        assert(forms.every(form => form.method === "post" && form.csrf && form.file === "image/png"));
        assert(forms.some(form => form.action.endsWith("/3d-kit/home/")));
        await page.screenshot({path:"/tmp/creator-texture-slots.jpg"});
        const viewers = page.locator(".creator-3d-stadium iframe");
        assert.equal(await viewers.count(), 2);
        await viewers.first().scrollIntoViewIfNeeded();
        for (const iframe of await viewers.all()) {
            await iframe.scrollIntoViewIfNeeded();
            const handle = await iframe.elementHandle();
            const frame = await handle.contentFrame();
            await frame.waitForSelector("[data-creator-stadium-viewer]");
            await frame.waitForFunction(() => {
                const status = document.querySelector("[data-viewer-status]");
                return status.hidden || !status.textContent.includes("wird geladen");
            }, {timeout:30000});
            const status = await frame.locator("[data-viewer-status]").textContent();
            assert(!/nicht geladen|nicht gestartet|Ungültig|fehlt/i.test(status), status);
            assert(await frame.locator("canvas").count() > 0);
            console.log("Verified stadium viewer:", await frame.locator(
                "[data-creator-stadium-viewer]").getAttribute("data-view-kind"));
        }
        await page.screenshot({path:"/tmp/creator-stadium-models.jpg"});
        await page.setViewportSize({width:390,height:844});
        await page.locator(".creator-3d-kit").first().scrollIntoViewIfNeeded();
        const fits = await page.locator(".creator-3d-panel").evaluateAll(elements =>
            elements.every(element => element.scrollWidth <= element.clientWidth + 1));
        assert(fits, "asset sections do not overflow their layout");
        assert.equal(errors.length, 0, errors.join("\n"));
        console.log("PASS: three PNG forms, CMTracker field, both live viewers and narrow layout.");
    } finally {
        await browser.close();
    }
})().catch(error => {console.error(error); process.exit(1);});
