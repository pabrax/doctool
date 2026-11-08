import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const css = readFileSync(resolve(__dirname, "../index.css"), "utf8");

// Light block = from ":root {" to the dark media query; dark blocks follow.
const lightEnd = css.indexOf("@media (prefers-color-scheme: dark)");
const mediaEnd = css.indexOf(':root[data-theme="dark"] {');
const themeEnd = css.indexOf("/* A subtree marked");
const light = css.slice(0, lightEnd);
const media = css.slice(lightEnd, mediaEnd);
const themed = css.slice(mediaEnd, themeEnd);

const LIGHT = { "": "#c2257f", "-fg": "#ffffff", "-ink": "#b01f72", "-soft": "#fce7f3" };
const DARK = { "": "#f07cc0", "-fg": "#14161c", "-ink": "#f07cc0", "-soft": "#3a1830" };

describe("images group colour tokens", () => {
  it.each(Object.entries(LIGHT))("light --images%s", (k, v) => {
    expect(light).toContain(`--images${k}: ${v};`);
  });
  it.each(Object.entries(DARK))("dark (prefers-color-scheme) --images%s", (k, v) => {
    expect(media).toContain(`--images${k}: ${v};`);
  });
  it.each(Object.entries(DARK))("dark (data-theme) --images%s", (k, v) => {
    expect(themed).toContain(`--images${k}: ${v};`);
  });
  it("is in the data-group selector list and has its own rule", () => {
    expect(css).toMatch(/\[data-group="security"\],\s*\[data-group="images"\],/);
    expect(css).toMatch(/\[data-group="images"\] \{ --group: var\(--images\); --group-fg: var\(--images-fg\); --group-ink: var\(--images-ink\); --group-soft: var\(--images-soft\); \}/);
  });
});

const OFFICE_LIGHT = { "": "#0e7490", "-fg": "#ffffff", "-ink": "#0e7490", "-soft": "#dff3f8" };
const OFFICE_DARK = { "": "#5fd0e8", "-fg": "#14161c", "-ink": "#5fd0e8", "-soft": "#12313a" };

describe("office group colour tokens (ADR D2b)", () => {
  it.each(Object.entries(OFFICE_LIGHT))("light --office%s", (k, v) => {
    expect(light).toContain(`--office${k}: ${v};`);
  });
  it.each(Object.entries(OFFICE_DARK))("dark (prefers-color-scheme) --office%s", (k, v) => {
    expect(media).toContain(`--office${k}: ${v};`);
  });
  it.each(Object.entries(OFFICE_DARK))("dark (data-theme) --office%s", (k, v) => {
    expect(themed).toContain(`--office${k}: ${v};`);
  });
  it("is in the data-group selector list and has its own rule", () => {
    expect(css).toMatch(/\[data-group="images"\],\s*\[data-group="office"\]\s*\{/);
    expect(css).toMatch(/\[data-group="office"\] \{ --group: var\(--office\); --group-fg: var\(--office-fg\); --group-ink: var\(--office-ink\); --group-soft: var\(--office-soft\); \}/);
  });
});
