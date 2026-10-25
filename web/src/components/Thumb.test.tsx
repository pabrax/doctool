import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Thumb } from "./Thumb";

describe("Thumb", () => {
  it("never writes a new src to the img before its turn in the queue", async () => {
    const { container, rerender } = render(<Thumb src="/a.png" />);
    await waitFor(() => expect(container.querySelector("img")).toHaveAttribute("src", "/a.png"));
    rerender(<Thumb src="/b.png" />);
    // synchronously after the change: the new URL must not be on the element yet
    expect(container.querySelector("img")).not.toHaveAttribute("src");
    await waitFor(() => expect(container.querySelector("img")).toHaveAttribute("src", "/b.png"));
  });

  it("swaps a failed image for a quiet placeholder", async () => {
    const { container } = render(<Thumb src="/missing.png" className="x" />);
    const img = await waitFor(() => {
      const el = container.querySelector("img");
      expect(el).toHaveAttribute("src");
      return el!;
    });
    fireEvent.error(img);
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("[data-thumb='failed']")).toHaveClass("x");
    expect(screen.queryByRole("img")).toBeNull();
    // not blank: a glyph tells a sighted user this is "unavailable", not "still loading"
    expect(container.querySelector("[data-thumb='failed'] svg")).not.toBeNull();
  });

  it("retries a failed thumbnail once after a delay, then gives up", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const { container } = render(<Thumb src="/flaky.png" />);
      const first = await waitFor(() => {
        const el = container.querySelector("img");
        expect(el).toHaveAttribute("src");
        return el!;
      });
      fireEvent.error(first);
      expect(container.querySelector("[data-thumb='failed']")).not.toBeNull();
      await act(async () => {
        await vi.advanceTimersByTimeAsync(4100);
      });
      const second = await waitFor(() => {
        const el = container.querySelector("img");
        expect(el).toHaveAttribute("src", "/flaky.png");
        return el!;
      });
      fireEvent.error(second);
      await act(async () => {
        await vi.advanceTimersByTimeAsync(10000);
      });
      expect(container.querySelector("img")).toBeNull();
      expect(container.querySelector("[data-thumb='failed']")).not.toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("keeps style, accessible name and fallback size when an image fails", async () => {
    const { container } = render(
      <Thumb src="/m.png" alt="Page 1" className="c" fallbackClassName="aspect-[3/4]" style={{ transform: "rotate(90deg)" }} />,
    );
    const img = await waitFor(() => {
      const el = container.querySelector("img");
      expect(el).toHaveAttribute("src");
      return el!;
    });
    fireEvent.error(img);
    const ph = screen.getByRole("img", { name: "Page 1" });
    expect(ph).toHaveClass("c", "aspect-[3/4]");
    expect(ph).toHaveStyle({ transform: "rotate(90deg)" });
  });
});
