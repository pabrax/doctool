import { expect, test, type Page } from "@playwright/test";

const run = (page: Page) => page.getByRole("button", { name: /^(Run|Ejecutar)$/ });

type Kind = "jpeg" | "png";

/** Real image bytes made by the browser's own canvas encoder (no Python, no extra dependency). */
async function makeImage(page: Page, kind: Kind, width: number, height: number, noise = 40): Promise<Buffer> {
  const b64 = await page.evaluate(
    async ({ kind, width, height, noise }) => {
      const c = document.createElement("canvas");
      c.width = width;
      c.height = height;
      const ctx = c.getContext("2d")!;
      const img = ctx.createImageData(width, height);
      let seed = 12345;
      for (let i = 0; i < img.data.length; i += 4) {
        seed = (seed * 1103515245 + 12345) & 0x7fffffff;
        const n = (seed >> 8) % noise;
        const p = i / 4;
        img.data[i] = ((p % width) / width) * 200 + n;
        img.data[i + 1] = (Math.floor(p / width) / height) * 200 + n;
        img.data[i + 2] = 90 + n;
        img.data[i + 3] = 255;
      }
      ctx.putImageData(img, 0, 0);
      const blob: Blob = await new Promise((res) => c.toBlob((b) => res(b!), `image/${kind}`, 0.97));
      const u8 = new Uint8Array(await blob.arrayBuffer());
      let s = "";
      for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode(...u8.subarray(i, i + 0x8000));
      return btoa(s);
    },
    { kind, width, height, noise },
  );
  return Buffer.from(b64, "base64");
}

const upload = (page: Page, name: string, buffer: Buffer, mimeType: string) =>
  page.getByTestId("file-input").setInputFiles([{ name, mimeType, buffer }]);

/** Click Download and return the downloaded bytes plus the suggested file name. */
async function download(page: Page): Promise<{ bytes: Buffer; name: string }> {
  const [dl] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("link", { name: /^(Download|Descargar)$/ }).click(),
  ]);
  const chunks: Buffer[] = [];
  for await (const c of (await dl.createReadStream())!) chunks.push(c as Buffer);
  return { bytes: Buffer.concat(chunks), name: dl.suggestedFilename() };
}

/** Magic-byte format plus the size the browser's decoder sees. */
async function inspect(page: Page, bytes: Buffer): Promise<{ format: string; w: number; h: number }> {
  const format = bytes.subarray(0, 3).equals(Buffer.from([0xff, 0xd8, 0xff]))
    ? "jpeg"
    : bytes.subarray(0, 4).equals(Buffer.from([0x89, 0x50, 0x4e, 0x47]))
      ? "png"
      : bytes.subarray(0, 4).toString() === "RIFF" && bytes.subarray(8, 12).toString() === "WEBP"
        ? "webp"
        : "unknown";
  const [w, h] = await page.evaluate(async (b64) => {
    const bin = atob(b64);
    const u8 = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
    const bmp = await createImageBitmap(new Blob([u8]));
    return [bmp.width, bmp.height];
  }, bytes.toString("base64"));
  return { format, w, h };
}

const TOOLS = [
  { id: "imageconvert", title: "Convert image", kind: "png" as Kind, size: [640, 480], expect: { format: "jpeg", w: 640, h: 480 } },
  { id: "imagecompress", title: "Compress image", kind: "jpeg" as Kind, size: [2800, 1400], expect: { format: "jpeg", w: 2560, h: 1280 } },
  { id: "imageresize", title: "Resize image", kind: "png" as Kind, size: [2400, 1200], expect: { format: "png", w: 1920, h: 960 } },
  { id: "imagecrop", title: "Crop image", kind: "jpeg" as Kind, size: [800, 600], expect: { format: "jpeg", w: 600, h: 600 } },
  { id: "imageclean", title: "Remove photo info", kind: "jpeg" as Kind, size: [500, 300], expect: { format: "jpeg", w: 500, h: 300 } },
];

for (const [i, tool] of TOOLS.entries()) {
  test(`E1 ${tool.id}: open, upload, run with defaults, download decodes as expected`, async ({ page }) => {
    await page.goto(i % 2 === 0 ? "/" : `/tools/${tool.id}`);
    if (i % 2 === 0) {
      // from the home launcher (main area), not the sidebar
      await page.locator("#main").getByRole("link", { name: new RegExp(tool.title) }).first().click();
    }
    await expect(page).toHaveURL(new RegExp(`/tools/${tool.id}$`));
    await expect(page.getByRole("heading", { level: 1, name: tool.title })).toBeVisible();
    const src = await makeImage(page, tool.kind, tool.size[0], tool.size[1]);
    await upload(page, `pic.${tool.kind === "jpeg" ? "jpg" : "png"}`, src, `image/${tool.kind}`);
    await expect(page.getByText(/^1 file/)).toBeVisible();
    await run(page).click();
    await expect(page.getByRole("heading", { name: "Done" })).toBeVisible();
    const { bytes, name } = await download(page);
    const got = await inspect(page, bytes);
    expect(got).toEqual(tool.expect);
    expect(name).toMatch(/\.(jpg|png)$/);
  });
}

test("E2 imageconvert default Run produces a JPEG named .jpg", async ({ page }) => {
  await page.goto("/tools/imageconvert");
  await expect(page.getByLabel("Format")).toHaveValue("jpg");
  await upload(page, "shot.png", await makeImage(page, "png", 320, 200), "image/png");
  await run(page).click();
  await expect(page.getByRole("heading", { name: "Done" })).toBeVisible();
  await expect(page.getByText("shot.jpg", { exact: true })).toBeVisible();
  const { bytes, name } = await download(page);
  expect(name).toBe("shot.jpg");
  expect((await inspect(page, bytes)).format).toBe("jpeg");
});

for (const lang of ["en", "es"] as const) {
  test.describe(`E3 before/after size line (${lang})`, () => {
    test.beforeEach(async ({ context }) => {
      await context.addInitScript((l) => localStorage.setItem("doctool.lang", l), lang);
    });
    const T = lang === "en"
      ? { smaller: /^\d+% smaller: .+ → .+/, larger: /^\d+% larger: .+ → .+\. This is normal when converting to PNG\./, done: "Done" }
      : { smaller: /^\d+ % más pequeño: .+ → .+/, larger: /^\d+ % más grande: .+ → .+\. Es normal al convertir a PNG\./, done: "Listo" };

    test("imagecompress shows 'smaller'", async ({ page }) => {
      await page.goto("/tools/imagecompress");
      await upload(page, "big.jpg", await makeImage(page, "jpeg", 1600, 1000), "image/jpeg");
      await run(page).click();
      await expect(page.getByRole("heading", { name: T.done })).toBeVisible();
      await expect(page.getByText(T.smaller)).toBeVisible();
    });

    test("imageconvert JPG to PNG shows 'larger'", async ({ page }) => {
      await page.goto("/tools/imageconvert");
      await upload(page, "photo.jpg", await makeImage(page, "jpeg", 800, 600), "image/jpeg");
      await page.getByLabel(lang === "en" ? "Format" : "Formato").selectOption({ label: "PNG" });
      await run(page).click();
      await expect(page.getByRole("heading", { name: T.done })).toBeVisible();
      await expect(page.getByText(T.larger)).toBeVisible();
    });
  });
}

test("E4 the 'images' group is in the sidebar and Ctrl+K 'photo' finds the image tools", async ({ page }) => {
  await page.goto("/");
  const nav = page.getByRole("navigation", { name: "Tools" });
  const group = nav.locator('div[data-group="images"]');
  await expect(group.getByRole("heading", { name: "Images" })).toBeVisible();
  for (const t of TOOLS) await expect(group.getByRole("link", { name: t.title })).toBeVisible();

  await page.keyboard.press("Control+k");
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await dialog.getByRole("combobox").fill("photo");
  for (const t of TOOLS) await expect(dialog.getByRole("option", { name: new RegExp(t.title) })).toBeVisible();
  await expect(dialog.getByRole("option", { name: /Merge PDF/ })).toHaveCount(0);
});

test("E5 imagecrop box mode with empty width/height names Width/Height, not the generic text", async ({ page }) => {
  await page.goto("/tools/imagecrop");
  await upload(page, "pic.jpg", await makeImage(page, "jpeg", 400, 300), "image/jpeg");
  await page.getByLabel("Mode").selectOption({ label: "Exact box in pixels" });
  await expect(page.getByLabel("Width (px)")).toHaveValue("");
  await run(page).click();
  const alert = page.getByRole("alert");
  await expect(alert).toBeVisible();
  await expect(alert).toContainText(/Width|Height/);
  await expect(alert).not.toContainText("Some options are not valid");
  await expect(page.getByRole("heading", { name: "Done" })).toHaveCount(0);
});

test("E6 a non-image second file: error names it, user removes it and runs again", async ({ page }) => {
  await page.goto("/tools/imageclean");
  const good = await makeImage(page, "jpeg", 300, 200);
  await page.getByTestId("file-input").setInputFiles([
    { name: "good.jpg", mimeType: "image/jpeg", buffer: good },
    // passes the client-side extension filter, fails server-side decoding
    { name: "notes.png", mimeType: "image/png", buffer: Buffer.from("this is plain text, not a picture") },
  ]);
  await expect(page.getByText(/^2 files/)).toBeVisible();
  await run(page).click();
  const alert = page.getByRole("alert");
  await expect(alert).toContainText("notes.png");
  await expect(alert).not.toContainText("Something went wrong");
  await expect(page.getByRole("heading", { name: "Done" })).toHaveCount(0);
  // both files stay listed
  const list = page.getByRole("list", { name: "Files" });
  await expect(list.getByText("good.jpg")).toBeVisible();
  await page.getByRole("button", { name: "Remove: notes.png" }).click();
  await expect(list.getByText("notes.png")).toHaveCount(0);
  await run(page).click();
  await expect(page.getByRole("heading", { name: "Done" })).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
  const { bytes } = await download(page);
  expect(await inspect(page, bytes)).toEqual({ format: "jpeg", w: 300, h: 200 });
});

test("E7 a double click on Run creates exactly one task", async ({ page }) => {
  const creates: string[] = [];
  page.on("request", (r) => {
    if (r.method() === "POST" && /\/api\/v1\/tasks\/?$/.test(new URL(r.url()).pathname)) creates.push(r.url());
  });
  await page.goto("/tools/imageconvert");
  await upload(page, "pic.png", await makeImage(page, "png", 1200, 900), "image/png");
  await run(page).dblclick();
  await expect(page.getByRole("heading", { name: "Done" })).toBeVisible();
  await page.waitForTimeout(500);
  expect(creates).toHaveLength(1);
});

test("E8 resize: choosing Percentage hides width/height, going back shows them", async ({ page }) => {
  await page.goto("/tools/imageresize");
  await expect(page.getByLabel("Width (px)")).toBeVisible();
  await expect(page.getByLabel("Height (px)")).toBeVisible();
  await expect(page.getByLabel("Percentage")).toHaveCount(0);
  await page.getByLabel("Mode").selectOption({ label: "Percentage" });
  await expect(page.getByLabel("Width (px)")).toHaveCount(0);
  await expect(page.getByLabel("Height (px)")).toHaveCount(0);
  await expect(page.getByLabel("Percentage")).toBeVisible();
  await page.getByLabel("Mode").selectOption({ label: "Exact size" });
  await expect(page.getByLabel("Width (px)")).toBeVisible();
});
