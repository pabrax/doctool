import { nextSteps } from "./nextSteps";
import { mergeTool, rotateTool } from "@/test/utils";

const tool = (id: string, accepts: "pdf" | "image" = "pdf") => ({ ...rotateTool, id, accepts });

describe("nextSteps", () => {
  const all = [mergeTool, rotateTool, tool("compress"), tool("organize"), tool("pagenumber"), tool("imagepdf", "image")];

  it("suggests existing PDF tools in priority order, never the tool just used", () => {
    expect(nextSteps("merge", all).map((x) => x.id)).toEqual(["organize", "compress", "pagenumber"]);
    expect(nextSteps("rotate", all).map((x) => x.id)).toEqual(["organize", "compress", "merge"]);
  });

  it("skips tools that are not installed and falls back for unknown tools", () => {
    expect(nextSteps("split", [tool("compress")]).map((x) => x.id)).toEqual(["compress"]);
    expect(nextSteps("future", all).map((x) => x.id)).toEqual(["compress", "organize", "merge"]);
  });

  it("never suggests image-only tools", () => {
    expect(nextSteps("x", [tool("imagepdf", "image")])).toEqual([]);
  });
});
