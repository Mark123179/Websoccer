/* Django-rendered fixture supplied externally; no application data is changed. */
const {chromium} = require("playwright-core");
const fs = require("node:fs");
const assert = require("node:assert/strict");

(async () => {
    const browser = await chromium.launch({
        executablePath: "/repl/tools/bin/chromium", headless: true,
        args: ["--no-sandbox"],
    });
    try {
        const page = await browser.newPage({viewport: {width: 1440, height: 900}});
        const host = `https://${process.env.REPLIT_DEV_DOMAIN}`;
        const url = `${host}/clubs/2/matches/1267/preview/`;
        await page.route(url, route => route.fulfill({
            contentType: "text/html", body: fs.readFileSync("/tmp/preview-ref-stats.html", "utf8")
                .replaceAll("preview-28", "preview-29").replaceAll("layout-15", "layout-16"),
        }));
        await page.goto(url, {waitUntil: "domcontentloaded"});
        await page.waitForTimeout(1200);
        const positions = () => page.locator(".match-preview-panel").evaluateAll(elements =>
            elements.map(element => {
                const rect = element.getBoundingClientRect();
                return {top: rect.top, bottom: rect.bottom};
            }));
        const current = await positions();
        const header = await page.locator(".ws-game-header").boundingBox();
        assert(current[0].top >= header.y + header.height, "panels do not cover the calendar");
        const old = await page.addStyleTag({content: ".match-preview-panels {top:208px !important}"});
        const before = await positions();
        await old.evaluate(element => element.remove());
        for (let index = 0; index < 3; index++) {
            assert(before[index].top > current[index].top);
            assert(Math.abs(before[index].top - current[index].top -
                (before[0].top - current[0].top)) < .2);
            assert(Math.abs(before[index].bottom - current[index].bottom) < .2);
        }
        const check = async name => {
            let stats = await page.locator(".mp-referee-season").boundingBox();
            let panel = await page.locator(".match-preview-panel--center").boundingBox();
            if (stats.y + stats.height > panel.y + panel.height) {
                assert(await page.locator(".match-preview-panel--center,.mp-match-content").evaluateAll(
                    elements => elements.some(element => element.scrollHeight > element.clientHeight)));
                await page.locator(".mp-referee-season").scrollIntoViewIfNeeded();
                stats = await page.locator(".mp-referee-season").boundingBox();
                panel = await page.locator(".match-preview-panel--center").boundingBox();
            }
            await page.screenshot({path: `/tmp/referee-preview-${name}.png`});
            console.log(name, await page.locator(
                ".mp-referee-season,.mp-referee-profile,.mp-referee-info,.mp-weather-profile,.mp-model-card",
            ).evaluateAll(elements => elements.map(element => {
                const rect = element.getBoundingClientRect();
                return {class: element.className, top: rect.top, bottom: rect.bottom, height: rect.height};
            })));
            assert(stats.width > 0 && stats.height > 0);
            assert(stats.y + stats.height <= panel.y + panel.height + .5, `${name}: statistics fit`);
        };
        await check("current");
        await page.evaluate(() => {
            const root = document.querySelector(".match-preview-scene");
            const rect = root.querySelector(".match-preview-panels").getBoundingClientRect();
            const nodes = {};
            for (const [id, selector] of [
                ["scout-0", ".match-preview-panel--scout"],
                ["center-0", ".match-preview-panel--center"],
                ["club-0", ".match-preview-panel--club"],
            ]) {
                const r = document.querySelector(selector).getBoundingClientRect();
                nodes[id] = {x: (r.left - rect.left) / rect.width * 100,
                    y: (r.top - rect.top) / rect.height * 100, width: r.width / rect.width * 100,
                    height: r.height / rect.height * 100, hidden: false};
            }
            localStorage.setItem(`fm:match-preview:layout:1:${root.dataset.layoutOwner}`,
                JSON.stringify({version: 1, revision: 3, detailPatch: 5, nodes}));
        });
        await page.reload({waitUntil: "domcontentloaded"});
        await page.waitForTimeout(1200);
        assert(await page.locator(".match-preview-scene").evaluate(
            element => element.classList.contains("mp-layout-free")));
        await check("saved");
        // Fixture values are browser-only, never notifications/matches in the database.
        await page.addInitScript(() => {
            document.addEventListener("DOMContentLoaded", () => {
                const section = document.querySelector(".mp-referee-season");
                if (!section) return;
                const title = document.createElement("h3");
                title.textContent = "Aktuelle Saison · Testwerte";
                const values = document.createElement("dl");
                values.className = "mp-referee-season-values";
                for (const [label, value, css] of [
                    ["Spiele", "25", ""], ["Ø Gelb", "6,2", "is-high"],
                    ["Rot", "10", "is-elevated"], ["Elfmeter-Tore", "8", "is-low"],
                    ["Umstritten", "—", ""],
                ]) {
                    const row = document.createElement("div");
                    const dt = document.createElement("dt"), dd = document.createElement("dd");
                    dt.textContent = label; dd.textContent = value; dd.className = css;
                    row.append(dt, dd); values.append(row);
                }
                const note = document.createElement("p");
                note.innerHTML = "Vergleich: gesamte Sim · pro Spiel<br>Grün: selten · Gelb: erhöht · Rot: stark erhöht<br>— = nicht vollständig erfasst";
                section.replaceChildren(title, values, note);
            });
        });
        await page.reload({waitUntil: "domcontentloaded"});
        await page.waitForTimeout(1200);
        await check("filled-saved");
        await page.evaluate(() => localStorage.clear());
        await page.reload({waitUntil: "domcontentloaded"});
        await page.waitForTimeout(1200);
        await check("filled-current");
        for (const [width, height] of [[1920,1080], [1280,720], [390,844]]) {
            await page.setViewportSize({width, height});
            await page.waitForTimeout(250);
            const header = await page.locator(".ws-game-header").boundingBox();
            const panel = await page.locator(".match-preview-panel--scout").boundingBox();
            assert(panel.y >= header.y + header.height, "wrapped calendar stays unobstructed");
            await check(`filled-${width}`);
        }
        console.log("PASS: all three panels shift equally; current and saved layouts show season statistics.");
    } finally {
        await browser.close();
    }
})().catch(error => {console.error(error); process.exit(1);});
