import { GROUPS, hasToolIcon, isKnownGroup, toolIcon } from "./toolIcons";
import { GROUP_ORDER } from "./useTools";

// Mirrors the tool registry (api/doctool/tools); e2e/identity.spec.ts checks the live /api/v1/tools list.
const REGISTERED = {
  merge: "organize", split: "organize", rotate: "organize", organize: "organize",
  compress: "optimize", imagepdf: "convert", pdfimage: "convert",
  metadata: "edit", watermark: "edit", pagenumber: "edit", protect: "security", unlock: "security",
};

describe("tool icons and groups", () => {
  it.each(Object.entries(REGISTERED))("%s has its own icon and a known group (%s)", (id, group) => {
    expect(hasToolIcon(id)).toBe(true);
    expect(isKnownGroup(group)).toBe(true);
  });

  it("gives every registered tool a distinct icon", () => {
    const icons = Object.keys(REGISTERED).map((id) => toolIcon(id));
    expect(new Set(icons).size).toBe(icons.length);
  });

  it("falls back to a generic icon for unknown tools", () => {
    expect(hasToolIcon("future-ocr")).toBe(false);
    expect(toolIcon("future-ocr")).toBeTruthy();
  });

  it("keeps the nav group order in sync with the color groups", () => {
    expect([...GROUP_ORDER].sort()).toEqual([...GROUPS].sort());
  });
});
