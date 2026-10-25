import { savedPercent } from "./savings";

describe("savedPercent", () => {
  it("reports whole percentages", () => {
    expect(savedPercent(4096, 1024)).toBe(75);
  });
  it("never reports 0% or 100%", () => {
    expect(savedPercent(100000, 99800)).toBeNull();
    expect(savedPercent(100000, 1)).toBe(99);
  });
  it("is null when nothing was saved or the input is unknown", () => {
    expect(savedPercent(100, 100)).toBeNull();
    expect(savedPercent(100, 120)).toBeNull();
    expect(savedPercent(0, 0)).toBeNull();
  });
});
