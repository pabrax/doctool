import { grownPercent, savedPercent } from "./savings";

describe("grownPercent", () => {
  it("reports whole percentages of growth", () => {
    expect(grownPercent(4096, 6144)).toBe(50);
  });
  it("is null when not bigger, negligible, or unknown", () => {
    expect(grownPercent(100, 100)).toBeNull();
    expect(grownPercent(100, 50)).toBeNull();
    expect(grownPercent(100000, 100100)).toBeNull();
    expect(grownPercent(0, 10)).toBeNull();
  });
});

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
