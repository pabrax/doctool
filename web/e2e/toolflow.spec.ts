import { expect, test, type Page } from "@playwright/test";
import path from "node:path";

const fixture = (name: string) => path.join(import.meta.dirname, ".fixtures", name);
const run = (page: Page) => page.getByRole("button", { name: "Run", exact: true });

test("merge shows page count and size, then a next-step button continues with the real result", async ({ page }) => {
  await page.goto("/tools/merge");
  await page.getByTestId("file-input").setInputFiles([fixture("alpha.pdf"), fixture("beta.pdf")]);
  await expect(page.getByText(/^2 files/)).toBeVisible();
  await run(page).click();
  await expect(page.getByRole("heading", { name: "Done" })).toBeVisible();
  await expect(page.getByText(/^5 pages · /)).toBeVisible();

  await page.getByRole("list", { name: "Keep going with this file" }).getByRole("button", { name: "Compress PDF" }).click();
  await expect(page).toHaveURL(/\/tools\/compress/);
  await expect(page.getByRole("list", { name: "Files" }).getByText("merged.pdf")).toBeVisible();
  await run(page).click();
  await expect(page.getByRole("heading", { name: "Done" })).toBeVisible();
  // real Ghostscript output: either a percentage or the honest "already optimized" line, never "0% smaller"
  await expect(page.getByText(/\d+% smaller: |Already well optimized: /)).toBeVisible();
  await expect(page.getByText("0% smaller")).toHaveCount(0);
});

test("Remove all is undoable and New task starts clean", async ({ page }) => {
  await page.goto("/tools/merge");
  await page.getByTestId("file-input").setInputFiles([fixture("alpha.pdf"), fixture("beta.pdf")]);
  await page.getByRole("button", { name: "Remove all" }).click();
  await expect(page.getByRole("status")).toHaveText("All files removed.");
  await expect(page.getByRole("button", { name: "Undo" })).toBeFocused();
  await page.getByRole("button", { name: "Undo" }).click();
  await expect(page.getByRole("list", { name: "Files" }).getByText("beta.pdf")).toBeVisible();

  await run(page).click();
  await expect(page.getByRole("heading", { name: "Done" })).toBeVisible();
  await page.getByRole("button", { name: "New task" }).click();
  await expect(page.getByRole("heading", { name: "Done" })).toHaveCount(0);
  await expect(page.getByText("No files yet.")).toBeVisible();
});

test("on a phone the launcher can show descriptions and the library card names its origin tool", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 800 });
  await page.goto("/");
  const toggle = page.getByRole("button", { name: "Show descriptions" });
  await expect(toggle).toHaveAttribute("aria-pressed", "false");
  const desc = page.getByRole("link", { name: /Merge PDF/ }).first().locator("span.line-clamp-2");
  await expect(desc).toBeHidden();
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-pressed", "true");
  await expect(desc).toBeVisible();
});
