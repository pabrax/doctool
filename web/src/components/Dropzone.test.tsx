import { fireEvent, render, screen } from "@testing-library/react";
import "@/i18n";
import { Dropzone } from "./Dropzone";

const pick = (file: File) => fireEvent.change(screen.getByTestId("file-input"), { target: { files: [file] } });

describe("Dropzone rejection message", () => {
  it("image tools say the file is not a readable picture", () => {
    render(<Dropzone accepts="image" onFiles={() => undefined} />);
    pick(new File(["x"], "doc.pdf", { type: "application/pdf" }));
    expect(screen.getByRole("alert")).toHaveTextContent("This file is not a picture we can read. Try JPG, PNG or WebP. (1)");
  });

  it("PDF tools keep the document wording", () => {
    render(<Dropzone accepts="pdf" onFiles={() => undefined} />);
    pick(new File(["x"], "p.png", { type: "image/png" }));
    expect(screen.getByRole("alert")).toHaveTextContent("The file is damaged or not a valid document. (1)");
  });
});
