import { expect, test } from "@playwright/test";

test.describe("desktop sidebar on a short window", () => {
  test.use({ viewport: { width: 1280, height: 480 } });

  test("C1 sidebar bottom edge equals the viewport bottom", async ({ page }) => {
    await page.goto("/");
    const nav = page.getByRole("navigation", { name: "Tools" });
    await expect(nav.locator("a").nth(3)).toBeVisible();
    const aside = page.locator("aside:has(nav[aria-label])");
    const box = await aside.boundingBox();
    const inner = await page.evaluate(() => window.innerHeight);
    expect(Math.round(box!.y + box!.height)).toBe(inner);
    // the nav (not the page) must be what scrolls: its own box ends inside the viewport
    const navBox = await nav.boundingBox();
    expect(navBox!.y + navBox!.height).toBeLessThanOrEqual(inner + 1);
  });

  test("C2 last nav link is fully visible after scrolling the nav to its end", async ({ page }) => {
    await page.goto("/");
    const nav = page.getByRole("navigation", { name: "Tools" });
    await expect(nav.locator("a").nth(3)).toBeVisible();
    const res = await page.request.get("/api/v1/tools");
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const tools = Array.isArray(body) ? body : (body.tools ?? body.items ?? []);
    expect(tools.length).toBeGreaterThan(3);
    await expect.poll(() => nav.locator("a").count()).toBeGreaterThan(3);
    const last = nav.locator("a").last();
    await nav.evaluate((el) => { el.scrollTop = el.scrollHeight; });
    const bottom = await last.evaluate((el) => el.getBoundingClientRect().bottom);
    const inner = await page.evaluate(() => window.innerHeight);
    expect(bottom).toBeLessThanOrEqual(inner);
    await expect(last).toBeInViewport({ ratio: 1 });
  });

  test("C3 the sidebar does not make the page taller than its content", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("navigation", { name: "Tools" }).locator("a").nth(3)).toBeVisible();
    const m = await page.evaluate(() => {
      const aside = document.querySelector("aside:has(nav[aria-label])")!;
      const shell = aside.parentElement!;
      const b = aside.getBoundingClientRect();
      return {
        scrollHeight: document.documentElement.scrollHeight,
        shell: shell.getBoundingClientRect().height,
        asideScroll: aside.scrollHeight,
        asideClient: aside.clientHeight,
        inner: window.innerHeight,
        asideH: b.height,
      };
    });
    // aside content must fit in the aside (old code overflowed it by the logo height)
    expect(m.asideScroll).toBeLessThanOrEqual(m.asideClient);
    expect(m.asideH).toBeLessThanOrEqual(m.inner);
    // document height is driven by the page content, never beyond it
    expect(m.scrollHeight).toBeLessThanOrEqual(Math.ceil(Math.max(m.shell, m.inner))); // scrollHeight is rounded up
  });
});

test("C4 on a phone the aside is hidden until the menu button is clicked", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 800 });
  await page.goto("/");
  const aside = page.locator("aside:has(nav[aria-label])");
  await expect(aside).not.toBeVisible();
  await page.getByRole("button", { name: "Menu" }).click();
  await expect(aside).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Tools" })).toBeVisible();
});
