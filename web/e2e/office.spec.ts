import { expect, test, type Page } from "@playwright/test";
import path from "node:path";

/** Office module end to end against the real API (LibreOffice must be installed for the *2pdf tools). */
const fixtures = path.join(import.meta.dirname, ".fixtures");
const run = (page: Page) => page.getByRole("button", { name: /^(Run|Ejecutar)$/ });

async function download(page: Page): Promise<{ bytes: Buffer; name: string }> {
  const [dl] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("link", { name: /^(Download|Descargar)$/ }).click(),
  ]);
  const chunks: Buffer[] = [];
  for await (const c of (await dl.createReadStream())!) chunks.push(c as Buffer);
  return { bytes: Buffer.concat(chunks), name: dl.suggestedFilename() };
}

const TOOLS = [
  { id: "word2pdf", title: "Word to PDF", file: "letter.docx", out: "letter.pdf", magic: "%PDF" },
  { id: "excel2pdf", title: "Excel to PDF", file: "book.xlsx", out: "book.pdf", magic: "%PDF", warn: /hidden slides or sheets were skipped/ },
  { id: "ppt2pdf", title: "PowerPoint to PDF", file: "deck.pptx", out: "deck.pdf", magic: "%PDF" },
  { id: "html2pdf", title: "HTML to PDF", file: "page.html", out: "page.pdf", magic: "%PDF", warn: /were not loaded/ },
  { id: "pdf2word", title: "PDF to Word", file: "table.pdf", out: "table.docx", magic: "PK" },
  { id: "pdf2excel", title: "PDF to Excel", file: "table.pdf", out: "table.xlsx", magic: "PK" },
  { id: "pdf2ppt", title: "PDF to PowerPoint", file: "table.pdf", out: "table.pptx", magic: "PK" },
];

test.describe.configure({ timeout: 120_000 }); // the first LibreOffice start builds its profile

for (const tool of TOOLS) {
  test(`O7 ${tool.id}: upload, run with defaults, download a valid ${tool.out.split(".")[1]}`, async ({ page }) => {
    await page.goto(`/tools/${tool.id}`);
    await expect(page.getByRole("heading", { level: 1, name: tool.title })).toBeVisible();
    await expect(page.locator("[data-group='office']").first()).toBeVisible();
    await page.getByTestId("file-input").setInputFiles(path.join(fixtures, tool.file));
    await expect(page.getByText(/^1 file/)).toBeVisible();
    await run(page).click();
    await expect(page.getByRole("heading", { name: /^Done/ })).toBeVisible({ timeout: 90_000 });
    if (tool.warn) {
      await expect(page.getByRole("list", { name: "Check these things" })).toContainText(tool.warn);
    }
    const { bytes, name } = await download(page);
    expect(name).toBe(tool.out);
    expect(bytes.subarray(0, tool.magic.length).toString()).toBe(tool.magic);
  });
}

test("O7 office group sits right after Convert in the sidebar, and PDF -> Office tools show the quality note", async ({ page }) => {
  await page.goto("/tools/pdf2word");
  await expect(page.getByRole("note")).toContainText("not pixel-perfect");
  const groups = await page.locator("nav [data-group]").evaluateAll((els) => [
    ...new Set(els.map((e) => e.getAttribute("data-group"))),
  ]);
  expect(groups.indexOf("office")).toBe(groups.indexOf("convert") + 1);
});

test("O7 a macro-enabled file is refused with a clear reason", async ({ page }) => {
  await page.goto("/tools/word2pdf");
  await page.getByTestId("file-input").setInputFiles({ name: "evil.docm", mimeType: "application/octet-stream", buffer: Buffer.from("PK") });
  await expect(page.getByRole("alert")).toContainText("not supported by this tool");
});
