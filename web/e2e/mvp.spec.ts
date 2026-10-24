import { expect, test, type Page } from "@playwright/test";
import path from "node:path";

const fixture = (name: string) => path.join(import.meta.dirname, ".fixtures", name);
const run = (page: Page) => page.getByRole("button", { name: "Run", exact: true });

test("merge two PDFs, download, and find the result in the library with its history", async ({ page }) => {
  await page.goto("/tools/merge");
  await page.getByTestId("file-input").setInputFiles([fixture("alpha.pdf"), fixture("beta.pdf")]);
  await expect(page.getByText("alpha.pdf")).toBeVisible();
  await expect(page.getByText("beta.pdf")).toBeVisible();
  await run(page).click();
  await expect(page.getByRole("heading", { name: "Done" })).toBeVisible();

  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("link", { name: "Download", exact: true }).click(),
  ]);
  expect(download.suggestedFilename()).toBe("merged.pdf");

  await page.getByRole("link", { name: "Open in library" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "merged.pdf" })).toBeVisible();
  await expect(page.getByText("Created with Merge PDF")).toBeVisible();
  await expect(page.getByTitle("Preview: merged.pdf")).toBeVisible();

  const docs = await (await page.request.get("/api/v1/documents")).json();
  const merged = docs.find((d: { name: string }) => d.name === "merged.pdf");
  expect(merged.latest_version.pages).toBe(5);
});

test("a library document becomes a new version when a tool runs on it; thumbnails render", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("file-input").setInputFiles(fixture("alpha.pdf"));
  const card = page.getByRole("link", { name: "Open: alpha.pdf" }).first();
  await expect(card).toBeVisible();
  await card.click();

  await page.getByRole("button", { name: "Rotate PDF" }).click();
  await expect(page).toHaveURL(/\/tools\/rotate/);
  await expect(page.getByRole("list", { name: "Files" }).getByText("alpha.pdf")).toBeVisible(); // pre-loaded
  await run(page).click();
  await expect(page.getByRole("heading", { name: "Done" })).toBeVisible();
  await page.getByRole("link", { name: "Open in library" }).click();
  await expect(page.getByRole("button", { name: /Version 2/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /Version 1/ })).toBeVisible();

  await page.goto("/");
  const img = page.locator("img[src*='thumbnail']").first();
  await expect.poll(() => img.evaluate((e: HTMLImageElement) => e.naturalWidth)).toBeGreaterThan(0);
});

test("visual organizer: delete a page and apply creates a shorter version", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("file-input").setInputFiles(fixture("beta.pdf"));
  await page.getByRole("link", { name: "Open: beta.pdf" }).first().click();
  await page.getByRole("button", { name: "Organize pages" }).click();
  await expect(page).toHaveURL(/\/organize\//);

  const grid = page.getByRole("list", { name: "Organize pages" });
  await expect(grid.getByRole("listitem")).toHaveCount(3);
  await page.getByRole("button", { name: "Delete page: Page 1" }).click();
  await expect(grid.getByRole("listitem")).toHaveCount(2);
  await page.getByRole("button", { name: "Apply changes" }).click();

  await expect(page.getByRole("heading", { level: 1, name: "beta.pdf" })).toBeVisible();
  await expect(page.getByText("Created with Organize pages")).toBeVisible();
  const docs = await (await page.request.get("/api/v1/documents")).json();
  const beta = docs.find((d: { name: string }) => d.name === "beta.pdf");
  expect(beta.latest_version.pages).toBe(2);
  expect(beta.latest_version.seq).toBe(2);
});

test("protect with a password, then unlock: wrong password is refused, right one works", async ({ page }) => {
  await page.goto("/tools/protect");
  await page.getByTestId("file-input").setInputFiles(fixture("alpha.pdf"));
  await page.getByLabel("Password", { exact: false }).first().fill("pw-123");
  await run(page).click();
  await expect(page.getByRole("heading", { name: "Done" })).toBeVisible();
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("link", { name: "Download", exact: true }).click(),
  ]);
  const locked = path.join(import.meta.dirname, ".fixtures", "locked.pdf");
  await download.saveAs(locked); // downloads are stored without extension; the dropzone filters by it

  await page.goto("/tools/unlock");
  await page.getByTestId("file-input").setInputFiles(locked);
  await run(page).click();
  await expect(page.getByRole("alert")).toContainText("need a password");

  const field = page.getByLabel(/Password for/);
  await field.fill("wrong");
  await page.getByRole("button", { name: "Retry" }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await field.fill("pw-123");
  await page.getByRole("button", { name: "Retry" }).click();
  await expect(page.getByRole("heading", { name: "Done" })).toBeVisible();
});

test("language and theme choices persist across reloads", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Language").selectOption("es");
  await expect(page.getByRole("heading", { level: 1, name: "¿Qué hacemos con tus PDF?" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { level: 1, name: "¿Qué hacemos con tus PDF?" })).toBeVisible();

  await page.getByRole("button", { name: /Tema/ }).click(); // system -> light
  await page.getByRole("button", { name: /Tema/ }).click(); // light -> dark
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
});

test("command palette jumps to a tool from the keyboard", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("Control+k");
  await page.getByRole("combobox").fill("watermark");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/tools\/watermark/);
  await expect(page.getByRole("heading", { level: 1, name: "Add watermark" })).toBeVisible();
});
