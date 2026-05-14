from pathlib import Path
from PyPDF2 import PdfReader

# ------------------------------------------------------
# CONFIG
# ------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_PDF = BASE_DIR / "data" / "guidelines" / "bloodstream_infections.pdf"
OUTPUT_TXT = BASE_DIR / "data" / "guidelines" / "bloodstream_infections_guidelines.txt"

# ------------------------------------------------------
# PDF → TXT CONVERSION
# ------------------------------------------------------

def pdf_to_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    pages_text = []

    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text()
            if text:
                pages_text.append(text)
        except Exception as e:
            print(f"⚠️ Skipping page {i + 1}: {e}")

    # Join pages with clear separation
    return "\n\n".join(pages_text)


def normalize_raw_pdf_text(text: str) -> str:
    """
    Light normalization ONLY.
    Heavy cleaning is done later by your guideline_preprocessor.
    """
    # Normalize newlines
    text = text.replace("\r", "\n")

    # Remove excessive spaces
    text = "\n".join(line.rstrip() for line in text.splitlines())

    # Collapse excessive blank lines
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")

    return text.strip()


# ------------------------------------------------------
# MAIN
# ------------------------------------------------------

if __name__ == "__main__":
    if not INPUT_PDF.exists():
        raise FileNotFoundError(f"PDF not found: {INPUT_PDF}")

    print("📄 Reading PDF...")
    raw_text = pdf_to_text(INPUT_PDF)

    print("🧹 Normalizing text...")
    cleaned_text = normalize_raw_pdf_text(raw_text)

    OUTPUT_TXT.write_text(cleaned_text, encoding="utf-8")

    print("✅ PDF → TXT conversion complete")
    print(f"✅ Output file: {OUTPUT_TXT}")
    print(f"✅ Characters written: {len(cleaned_text)}")
