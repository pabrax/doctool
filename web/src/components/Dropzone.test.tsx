import { act, fireEvent, render, screen } from "@testing-library/react";
import i18n from "@/i18n";
import { Dropzone } from "./Dropzone";

const pick = (file: File) => fireEvent.change(screen.getByTestId("file-input"), { target: { files: [file] } });

describe("Dropzone rejection message", () => {
  it("image tools say the file is not a readable picture", () => {
    render(<Dropzone accepts="image" onFiles={() => undefined} />);
    pick(new File(["x"], "doc.pdf", { type: "application/pdf" }));
    expect(screen.getByRole("alert")).toHaveTextContent("This file is not a picture we can read. Try JPG, PNG or WebP. (1)");
  });

  it("PDF tools name the file and say it is not a PDF (office QA1 O4)", () => {
    render(<Dropzone accepts="pdf" onFiles={() => undefined} />);
    pick(new File(["x"], "letter.docx"));
    expect(screen.getByRole("alert")).toHaveTextContent("letter.docx: not a PDF. This tool needs a PDF file.");
  });
});

describe("Dropzone copy", () => {
  afterEach(() => i18n.changeLanguage("en"));
  it("tools of the images group list only still formats, in both languages", async () => {
    render(<Dropzone accepts="image" group="images" onFiles={() => undefined} />);
    expect(screen.getByText("Images: JPG, PNG, WebP (still pictures only)")).toBeInTheDocument();
    await act(() => i18n.changeLanguage("es"));
    expect(screen.getByText("Imágenes: JPG, PNG, WebP (solo imágenes fijas)")).toBeInTheDocument();
  });
  it("imagepdf (another group) keeps its text", () => {
    render(<Dropzone accepts="image" group="convert" onFiles={() => undefined} />);
    expect(screen.getByText("Images (JPG, PNG, WEBP, GIF, BMP)")).toBeInTheDocument();
  });
});

describe("Dropzone for office tools", () => {
  const exts = ["docx", "odt"];
  const take = vi.fn();
  beforeEach(() => take.mockClear());

  it("takes only the listed extensions, case-insensitively", () => {
    render(<Dropzone accepts="office" extensions={exts} onFiles={take} />);
    pick(new File(["x"], "Report.DOCX"));
    expect(take).toHaveBeenCalledTimes(1);
    pick(new File(["x"], "sheet.xlsx"));
    expect(take).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("alert")).toHaveTextContent("sheet.xlsx: this tool does not take this type of file. It takes DOCX, ODT.");
  });

  it("never accepts macro-enabled files and says why (office QA1 O3)", () => {
    render(<Dropzone accepts="office" extensions={exts} onFiles={take} />);
    pick(new File(["x"], "evil.docm"));
    expect(take).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "evil.docm: files with macros are not accepted. Save a copy without macros (for example .docx) and add it again.",
    );
  });

  it("lists the formats and limits the native picker", () => {
    render(<Dropzone accepts="office" extensions={exts} onFiles={take} />);
    expect(screen.getByText("Documents: DOCX, ODT")).toBeInTheDocument();
    expect(screen.getByTestId("file-input")).toHaveAttribute("accept", ".docx,.odt");
  });

  it("is inert when disabled", () => {
    render(<Dropzone accepts="office" extensions={exts} disabled onFiles={take} />);
    expect(screen.getByRole("button", { name: "Select files" })).toBeDisabled();
    fireEvent.drop(screen.getByText("Drop files here or click to select").closest("div")!, {
      dataTransfer: { files: [new File(["x"], "a.docx")] },
    });
    expect(take).not.toHaveBeenCalled();
  });
});
