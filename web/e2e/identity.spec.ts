import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";

const fixture = (name: string) => path.join(import.meta.dirname, ".fixtures", name);
const axeSource = readFileSync(createRequire(import.meta.url).resolve("axe-core/axe.min.js"), "utf8");

async function violations(page: Page) {
  // addScriptTag injects inline code, which the strict CSP blocks; evaluate runs it via CDP instead.
  await page.evaluate(axeSource);
  return page.evaluate(async () => {
    // @ts-expect-error axe is injected above
    const r = await window.axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] } });
    return r.violations.map((v: { id: string; nodes: { target: unknown }[] }) => `${v.id}: ${v.nodes.map((n) => n.target + " " + (n as unknown as {html:string}).html.slice(0,160)).join(" | ")}`);
  });
}

test("every registered tool has its own icon and a known group in the sidebar", async ({ page }) => {
  const tools: { id: string; group: string }[] = await (await page.request.get("/api/v1/tools")).json();
  await page.goto("/");
  const nav = page.getByRole("navigation", { name: "Tools" });
  for (const t of tools) {
    expect(["organize", "optimize", "convert", "edit", "security"]).toContain(t.group);
    await expect(nav.locator(`[data-tool-icon="${t.id}"]`)).toHaveCount(1);
  }
  await expect(page.locator('[data-tool-icon="fallback"]')).toHaveCount(0);
});

for (const theme of ["light", "dark"] as const) {
  test(`five views are axe-clean, same-origin only, fonts self-hosted (${theme})`, async ({ browser, baseURL }) => {
    const origin = new URL(baseURL!).origin;
    const context = await browser.newContext({ locale: "en-US" });
    await context.addInitScript((th) => localStorage.setItem("doctool.theme", th), theme);
    const page = await context.newPage();
    const foreign: string[] = [];
    page.on("request", (r) => {
      const u = r.url();
      if (!u.startsWith(origin) && !u.startsWith("data:") && !u.startsWith("blob:")) foreign.push(u);
    });
    const found: Record<string, string[]> = {};

    await page.goto("/");
    await page.getByTestId("file-input").setInputFiles(fixture("alpha.pdf"));
    await expect(page.getByRole("link", { name: "Open: alpha.pdf" }).first()).toBeVisible();
    found.home = await violations(page);

    await page.keyboard.press("Control+k");
    await expect(page.getByRole("dialog")).toBeVisible();
    found.palette = await violations(page);
    await page.keyboard.press("Escape");

    await page.goto("/tools/merge");
    await page.getByTestId("file-input").setInputFiles([fixture("alpha.pdf"), fixture("beta.pdf")]);
    await page.getByRole("button", { name: "Run", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Done" })).toBeVisible();
    found.tool = await violations(page);
    await page.getByRole("link", { name: "Open in library" }).click();
    await expect(page.getByTitle("Preview: merged.pdf")).toBeVisible();
    found.document = await violations(page);

    await page.getByRole("button", { name: "Organize pages" }).click();
    await expect(page.getByRole("list", { name: "Organize pages" }).getByRole("listitem").first()).toBeVisible();
    found.organizer = await violations(page);

    const fonts = await page.evaluate(async () => {
      await document.fonts.ready;
      return [...document.fonts].filter((f) => f.status === "loaded").map((f) => f.family);
    });
    expect(fonts.join(",")).toContain("Fraunces");
    expect(fonts.join(",")).toContain("Inter");
    expect(foreign).toEqual([]);
    expect(found).toEqual({ home: [], palette: [], tool: [], document: [], organizer: [] });
    await context.close();
  });
}

test("system theme follows the OS, and a stored choice overrides it", async ({ browser }) => {
  const bg = (page: Page) => page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  const dark = await browser.newContext({ colorScheme: "dark" });
  const p1 = await dark.newPage();
  await p1.goto("/");
  await expect(p1.locator("html")).not.toHaveAttribute("data-theme", /.*/);
  expect(await bg(p1)).toBe("rgb(20, 22, 28)");
  await dark.close();

  const light = await browser.newContext({ colorScheme: "dark" });
  await light.addInitScript(() => localStorage.setItem("doctool.theme", "light"));
  const p2 = await light.newPage();
  await p2.goto("/");
  expect(await bg(p2)).toBe("rgb(247, 248, 250)");
  await light.close();
});

test("reduced motion removes the entrance animation", async ({ browser }) => {
  const ctx = await browser.newContext({ reducedMotion: "reduce" });
  const page = await ctx.newPage();
  await page.goto("/tools/merge");
  await page.getByTestId("file-input").setInputFiles(fixture("alpha.pdf"));
  const row = page.getByRole("list", { name: "Files" }).getByRole("listitem").first();
  await expect(row).toBeVisible();
  expect(await row.evaluate((e) => getComputedStyle(e).animationName)).toBe("none");
  await ctx.close();
});
