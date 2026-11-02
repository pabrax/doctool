import { GROUPS, hasToolIcon, isKnownGroup, toolIcon } from "./toolIcons";
import { GROUP_ORDER } from "./useTools";
import en from "@/i18n/en";
import es from "@/i18n/es";

// Mirrors the tool registry (api/doctool/tools); e2e/identity.spec.ts checks the live /api/v1/tools list.
const REGISTERED = {
  merge: "organize", split: "organize", rotate: "organize", organize: "organize",
  compress: "optimize", imagepdf: "convert", pdfimage: "convert",
  metadata: "edit", watermark: "edit", pagenumber: "edit", protect: "security", unlock: "security",
  imageconvert: "images", imagecompress: "images", imageresize: "images", imagecrop: "images", imageclean: "images",
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

  it.each(Object.entries(REGISTERED))("%s has title and description in en and es", (id) => {
    for (const dict of [en, es]) {
      const entry = (dict.tools as Record<string, { title: string; description: string } | undefined>)[id];
      expect(entry?.title).toBeTruthy();
      expect(entry?.description).toBeTruthy();
    }
  });

  it("has a group label in both languages for every group", () => {
    for (const g of GROUPS) {
      expect((en.groups as Record<string, string>)[g]).toBeTruthy();
      expect((es.groups as Record<string, string>)[g]).toBeTruthy();
    }
  });

  it("places images last in the group order", () => {
    expect(GROUP_ORDER[GROUP_ORDER.length - 1]).toBe("images");
    expect(GROUPS[GROUPS.length - 1]).toBe("images");
  });

  it("falls back to a generic icon for unknown tools", () => {
    expect(hasToolIcon("future-ocr")).toBe(false);
    expect(toolIcon("future-ocr")).toBeTruthy();
  });

  it("keeps the nav group order in sync with the color groups", () => {
    expect([...GROUP_ORDER].sort()).toEqual([...GROUPS].sort());
  });
});
