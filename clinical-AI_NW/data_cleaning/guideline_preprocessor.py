"""
WHO Guideline Preprocessing Pipeline for Medical RAG Systems
=============================================================
Transforms raw PDF-extracted TXT files into clean, semantically chunked JSONL
optimized for high-precision retrieval-augmented generation.

Modules:
  1. Document configuration & metadata inference
  2. Global noise removal (boilerplate, legal, references)
  3. Page-level cleanup (headers, footers, page numbers)
  4. Text normalization (line breaks, hyphenation, bullets, unicode)
  5. Table handling (flattened table detection & prose conversion)
  6. Citation cleanup
  7. Abbreviation extraction
  8. Semantic chunking (section-based, 400-700 token target)
  9. Metadata enrichment
  10. Quality assurance & deduplication
  11. JSONL output

Usage:
    python data_cleaning/guideline_preprocessor.py
"""

import hashlib
import json
import os
import re
import unicodedata
import uuid
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# 1. DOCUMENT CONFIGURATION & METADATA INFERENCE
# ---------------------------------------------------------------------------

# Each guideline file mapped to its metadata
DOCUMENT_CONFIGS = {
    "covid19_guidelines.txt": {
        "document_name": "Infection prevention and control in the context of COVID-19",
        "disease": "COVID-19",
        "guideline_type": "IPC",
        "target_population": "health-care workers, general public",
        "publication_year": "2023",
    },
    "dengue_guidelines.txt": {
        "document_name": "WHO guidelines for clinical management of arboviral diseases: dengue, chikungunya, Zika and yellow fever",
        "disease": "Dengue",
        "guideline_type": "clinical",
        "target_population": "adults, children",
        "publication_year": "2025",
    },
    "malaria_guidelines.txt": {
        "document_name": "WHO guidelines for malaria",
        "disease": "Malaria",
        "guideline_type": "treatment",
        "target_population": "adults, children, pregnant women, PLHIV",
        "publication_year": "2025",
    },
    "tuberculosis_guidelines.txt": {
        "document_name": "WHO consolidated guidelines on tuberculosis - Module 1: Prevention",
        "disease": "Tuberculosis",
        "guideline_type": "prevention",
        "target_population": "adults, children, PLHIV, household contacts",
        "publication_year": "2020",
    },
    
    "bloodstream_infections.txt": {
        "document_name": "WHO guidelines on bloodstream infections and intravascular catheter-related infections",
        "disease": "Bloodstream infection",
        "guideline_type": "IPC",
        "target_population": "hospitalized patients, ICU patients, health-care workers",
        "publication_year": "2019"
    },

}

# Fallback config for unrecognized files
DEFAULT_CONFIG = {
    "document_name": "Unknown WHO guideline",
    "disease": "Unknown",
    "guideline_type": "clinical",
    "target_population": "general",
    "publication_year": "unknown",
}

# Token target for chunking (approximate words; 1 token ~= 0.75 words)
MIN_CHUNK_TOKENS = 400
MAX_CHUNK_TOKENS = 700
# Approximate word-to-token ratio
WORDS_PER_TOKEN = 0.75


# -----------------------------------------------------------
# Guidelines that are already finalized and should NOT be regenerated
# -----------------------------------------------------------
SKIP_FILES = {
    "covid19_guidelines.txt",
    "malaria_guidelines.txt",
}


# ---------------------------------------------------------------------------
# 2. GLOBAL NOISE REMOVAL
# ---------------------------------------------------------------------------

# Regex patterns for blocks that must be deleted entirely
BOILERPLATE_PATTERNS = [
    # Copyright and license blocks
    r"©\s*World Health Organization.*?(?=\n[A-Z1-9]|\n\n[A-Z])",
    r"Some rights reserved\..*?(?:3\.0 IGO|damages arising from its use)[\.\s]*",
    r"Under the terms of this licen[cs]e.*?(?:authentic edition|binding and authentic edition)[\"\".]?\s*",
    r"Any mediation relating to disputes.*?(?:mediation rules|mediation/rules/?\)?)[\.\s]*",
    r"Suggested citation\..*?(?:IGO|3\.0 IGO)[\.\s]*",
    r"Cataloguing-in-Publication.*?(?:iris\.who\.int/?|http://apps\.who\.int/iris)[\.\s]*",
    r"Sales, rights and licensing\..*?(?:who\.int/copyright|/licensing)[\.\s]*",
    r"Third-party materials\..*?(?:rests solely with the user)[\.\s]*",
    r"General disclaimers\..*?(?:damages arising from its use)[\.\s]*",
    r"The mention of specific companies.*?(?:initial capital letters)[\.\s]*",
    r"All reasonable precautions.*?(?:damages arising from its use)[\.\s]*",
    # ISBN lines
    r"ISBN\s*[\d\-]+\s*\([^)]*\)\s*",
    # Contact blocks
    r"Contact\s*\n.*?(?:@who\.int|who\.int)\s*",
    # Sponsors / Funding
    r"Sponsors?/Funding\s*\n.*?(?:\.\s*\n|\n\n)",
    # Disclaimer headers
    r"Disclaimer\s*\n",
    # Design credit lines
    r"Design(?:\s*by|\s*:).*?\n",
]

# Section-level blocks to remove entirely
SECTION_REMOVAL_PATTERNS = [
    # Acknowledgements section (entire block)
    r"\n(?:Acknowledgement?s|ACKNOWLEDGEMENT?S)\s*\n.*?(?=\n(?:\d+[\.\s]|[A-Z][a-z]+\s+summary|Executive|Introduction|Recommendations|Background))",
    # References / Bibliography (end-of-document)
    r"\nReferences?\s*\n(?:\s*\d+\..*?\n)*",
    # Annexes (entire trailing block)
    r"\n(?:Annex(?:es)?|Appendix|ANNEX)\s+\d+.*?(?=\n\d+\.\s|\Z)",
    # Contributors and interests
    r"\n(?:\d+\.?\s*)?Contributors?\s+and\s+interests?\s*\n.*?(?=\n\d+\.\s|\Z)",
    # Declarations of interest
    r"\nDeclarations?\s+of\s+Interest\s*\n.*?(?=\n\d+\.\s|\Z)",
    # Web annex references
    r"\nOnline\s+annex(?:es)?\s*\n.*?(?=\n\n)",
    # Supplementary tables at end
    r"\nSupplementary\s+Table\s*\n.*?(?=\n\n|\Z)",
]

# Table of contents patterns
TOC_PATTERNS = [
    # Dotted leader lines: "Section name ......... 42"
    r"^.*?\.{4,}\s*\d+\s*$",
    # Section with page ref separated by dots
    r"^[\d\.]+\s+[A-Z].*?\.{3,}\s*\d+\s*$",
    # "Contents" header
    r"^\s*(?:Table of\s+)?Contents?\s*$",
    # "Tables" / "Figures" list headers
    r"^\s*(?:Tables|Figures|List of (?:Tables|Figures))\s*$",
]

# Patterns for "list of figures/tables" entries
LIST_OF_TABLES_FIGURES_PATTERN = re.compile(
    r"^(?:Table|Figure)\s+[\d\-\.]+.*?\.{3,}\s*\d+\s*$", re.MULTILINE
)


def remove_boilerplate(text: str) -> str:
    """Remove copyright, license, disclaimer, and legal boilerplate."""
    for pattern in BOILERPLATE_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.DOTALL | re.IGNORECASE)
    return text



def remove_section_blocks(text: str) -> str:
    safe_sections = ["recommendation", "management", "treatment"]

    for pattern in SECTION_REMOVAL_PATTERNS:
        matches = list(re.finditer(pattern, text, re.DOTALL | re.IGNORECASE))
        for match in matches:
            block = match.group(0).lower()
            if any(key in block for key in safe_sections):
                continue  # do NOT remove
            text = text.replace(match.group(0), "\n")
    return text



def remove_toc(text: str) -> str:
    """Remove table of contents and list of tables/figures entries."""
    lines = text.split("\n")
    cleaned = []
    in_toc_block = False

    for line in lines:
        stripped = line.strip()
        # Detect TOC header
        if re.match(r"^\s*(?:Table of\s+)?Contents?\s*$", stripped, re.IGNORECASE):
            in_toc_block = True
            continue
        if re.match(r"^\s*(?:Tables|Figures|List of (?:Tables|Figures))\s*$", stripped, re.IGNORECASE):
            in_toc_block = True
            continue
        # If in TOC block, skip dotted leader lines
        if in_toc_block:
            if re.match(r"^.*?\.{3,}\s*\d+\s*$", stripped):
                continue
            # Also skip numbered section refs without dots if in TOC
            if re.match(r"^[\d\.]+\s+\S", stripped) and len(stripped) < 200:
                # Check if it looks like a TOC entry (short line)
                if len(stripped) < 150:
                    continue
            # Exit TOC block on substantial content
            if len(stripped) > 5 and not re.match(r"^\s*[ivxlc]+\s*$", stripped, re.IGNORECASE):
                in_toc_block = False
        # Remove standalone dotted leader lines outside TOC
        if re.match(r"^.*?\.{4,}\s*\d+\s*$", stripped):
            continue
        # Remove list-of-tables/figures entries
        if LIST_OF_TABLES_FIGURES_PATTERN.match(stripped):
            continue
        cleaned.append(line)

    return "\n".join(cleaned)


# ---------------------------------------------------------------------------
# 3. PAGE-LEVEL CLEANUP
# ---------------------------------------------------------------------------

# Repeated header/footer patterns from PDF extraction
PAGE_NOISE_PATTERNS = [
    # "X of Y" page numbers
    r"^\s*\d+\s+of\s+\d+\s*$",
    # Roman numeral page numbers on their own line
    r"^\s*[ivxlc]+\s*$",
    # Standalone arabic page numbers
    r"^\s*\d{1,3}\s*$",
    # "Page X" patterns
    r"^\s*Page\s+\d+\s*$",
    # Repeated document title as header (long titles across documents)
    r"^WHO guidelines for malaria\s*-\s*\d+\s+\w+\s+\d{4}\s*-\s*World Health Organization \(WHO\)\s*$",
    r"^Infection prevention and control in the context of.*?WHO\)?\s*$",
    r"^WHO consolidated guidelines on tuberculosis:?\s*(?:tuberculosis preventive treatment)?\s*$",
    r"^WHO guidelines for clinical management of arboviral diseases.*?$",
    # Image placeholders
    r"!\[\]\[image\w*\]",
    r"!\[\]\(.*?\)",
    # Decorative separators
    r"^[\s\-=_*]{5,}$",
    # URL-only lines
    r"^\s*https?://\S+\s*$",
    # "Sections" artifact from PDF
    r"^\s*Sections\s*$",
]


def clean_page_artifacts(text: str) -> str:
    """Remove page numbers, repeated headers, image placeholders, separators."""
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        skip = False
        for pattern in PAGE_NOISE_PATTERNS:
            if re.match(pattern, stripped, re.IGNORECASE):
                skip = True
                break
        if not skip:
            cleaned.append(line)
    return "\n".join(cleaned)


# ---------------------------------------------------------------------------
# 4. TEXT NORMALIZATION
# ---------------------------------------------------------------------------

def fix_hyphenation(text: str) -> str:
    """Repair words broken by PDF line wrapping (e.g., 'transmis-\\nsion' -> 'transmission')."""
    # Pattern: word fragment + hyphen + newline + continuation (lowercase)
    text = re.sub(r"(\w+)-\s*\n\s*([a-z])", r"\1\2", text)
    return text


def normalize_line_breaks(text: str) -> str:
    """Fix broken lines within paragraphs while preserving intentional breaks."""
    lines = text.split("\n")
    merged = []
    buffer = ""

    for line in lines:
        stripped = line.strip()
        # Empty line = paragraph break
        if not stripped:
            if buffer:
                merged.append(buffer)
                buffer = ""
            merged.append("")
            continue
        # Section header: starts with number+dot or is short uppercase
        if re.match(r"^\d+(\.\d+)*\s+[A-Z]", stripped) and len(stripped) < 150:
            if buffer:
                merged.append(buffer)
                buffer = ""
            merged.append(stripped)
            continue
        # Bullet points / list items
        if re.match(r"^[\-•●○▪▸►]\s", stripped) or re.match(r"^\(?[a-z]\)\s", stripped):
            if buffer:
                merged.append(buffer)
                buffer = ""
            buffer = stripped
            continue
        # If previous buffer ends mid-sentence (no terminal punctuation, lowercase start)
        if buffer and not re.search(r"[.;:!?]\s*$", buffer) and stripped[0].islower():
            buffer += " " + stripped
        else:
            if buffer:
                merged.append(buffer)
            buffer = stripped

    if buffer:
        merged.append(buffer)

    return "\n".join(merged)


def normalize_bullets(text: str) -> str:
    """Normalize all bullet point characters to a single format (-)."""
    # Replace various bullet characters
    text = re.sub(r"^[\s]*[•●○▪▸►◆◇→‣⁃]\s*", "- ", text, flags=re.MULTILINE)
    # Normalize existing bullets with inconsistent spacing
    text = re.sub(r"^[\s]*[-–—]\s+", "- ", text, flags=re.MULTILINE)
    return text


def collapse_blank_lines(text: str) -> str:
    """Collapse multiple blank lines into a single blank line."""
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def normalize_unicode(text: str) -> str:
    """Normalize Unicode characters and whitespace."""
    # NFKC normalization: decomposes compatibility characters
    text = unicodedata.normalize("NFKC", text)
    # Replace non-breaking spaces, zero-width chars, etc.
    text = text.replace("\u00a0", " ")
    text = text.replace("\u200b", "")
    text = text.replace("\u200c", "")
    text = text.replace("\u200d", "")
    text = text.replace("\ufeff", "")
    # Normalize quotes
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    # Normalize dashes
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    # Remove control characters (except newline, tab)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # Collapse multiple spaces within a line
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text


def remove_ocr_artifacts(text: str) -> str:
    """Remove OCR artifacts like ',{.\\ World Health', 't*' etc."""
    # Remove common OCR garbage patterns
    text = re.sub(r",\{\.\\", "", text)
    text = re.sub(r"t[•*]+[^\w\s]*", "", text)
    text = re.sub(r"-\d+\)\s*<\d+--", "", text)
    # Remove isolated non-alphanumeric garbage sequences
    text = re.sub(r"^[^\w\s]{3,}$", "", text, flags=re.MULTILINE)
    return text


# ---------------------------------------------------------------------------
# 5. TABLE HANDLING
# ---------------------------------------------------------------------------

def detect_and_convert_tables(text: str) -> str:
    """
    Detect flattened tables and convert to readable prose.
    Preserves numerical values, dosages, thresholds, and recommendation strengths.
    """
    lines = text.split("\n")
    result = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Detect table-like patterns: lines with multiple pipe/tab separators
        if "|" in line and line.count("|") >= 2:
            table_lines = [line]
            i += 1
            while i < len(lines) and ("|" in lines[i] or re.match(r"^[\s\-|]+$", lines[i])):
                if not re.match(r"^[\s\-|]+$", lines[i]):  # skip separator rows
                    table_lines.append(lines[i])
                i += 1
            # Convert table to prose
            result.append(_table_to_prose(table_lines))
            continue

        # Detect recommendation/dosing tables: "Table X-Y." followed by columnar data
        if re.match(r"^Table\s+[\d\-\.]+\.", line):
            table_header = line
            table_content = []
            i += 1
            # Collect lines that look tabular (short lines, many numbers/units)
            while i < len(lines) and lines[i].strip():
                table_content.append(lines[i])
                i += 1
            # Preserve as structured text block
            if table_content:
                prose = f"{table_header}\n" + "\n".join(table_content)
                result.append(prose)
            else:
                result.append(table_header)
            continue

        result.append(line)
        i += 1

    return "\n".join(result)


def _table_to_prose(table_lines: list[str]) -> str:
    """Convert pipe-separated table rows into readable prose sentences."""
    if not table_lines:
        return ""
    rows = []
    for line in table_lines:
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if cells:
            rows.append(cells)
    if not rows:
        return ""
    # Use first row as headers
    headers = rows[0] if rows else []
    prose_parts = []
    for row in rows[1:]:
        parts = []
        for j, cell in enumerate(row):
            header = headers[j] if j < len(headers) else f"Column {j+1}"
            parts.append(f"{header}: {cell}")
        prose_parts.append("; ".join(parts))
    return "\n".join(prose_parts)


# ---------------------------------------------------------------------------
# 6. CITATION CLEANUP
# ---------------------------------------------------------------------------

def remove_citations(text: str) -> str:
    """Remove numeric inline citations like [1], [2,3], (34), (1-5)."""
    # Bracketed numeric citations: [1], [2,3], [1-5], [12, 14, 16]
    text = re.sub(r"\[\s*\d+(?:\s*[,\-–]\s*\d+)*\s*\]", "", text)
    # Parenthetical numeric citations: (1), (2,3), (12-15) - only if clearly citations
    # Be careful not to remove dosage numbers like (500 mg)
    text = re.sub(r"\(\s*\d{1,3}(?:\s*[,\-–]\s*\d{1,3})*\s*\)", "", text)
    # Superscript-style: remove trailing numbers that look like footnotes
    text = re.sub(r"(?<=\w)\d{1,2}(?=[\s,\.])", "", text)
    # Clean up double spaces left behind
    text = re.sub(r"  +", " ", text)
    return text


# ---------------------------------------------------------------------------
# 7. ABBREVIATION EXTRACTION
# ---------------------------------------------------------------------------

def extract_abbreviations(text: str) -> dict[str, str]:
    """
    Extract abbreviation definitions from the text.
    Returns a dict mapping abbreviation -> definition.
    """
    abbreviations = {}

    # Pattern 1: "ABBR - definition" or "ABBR: definition" in abbreviation sections
    abbr_section = re.search(
        r"(?:Abbreviations?\s*(?:&|and)?\s*(?:acronyms?)?|List of abbreviations)\s*\n(.*?)(?=\n(?:\d+\.\s|[A-Z][a-z]+\s+summary|Executive|Introduction|Recommendations))",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if abbr_section:
        section_text = abbr_section.group(1)
        for match in re.finditer(
            r"^([A-Z][A-Z0-9/\-]{1,15})\s+(.+?)$", section_text, re.MULTILINE
        ):
            abbr = match.group(1).strip()
            definition = match.group(2).strip()
            if len(definition) > 3:
                abbreviations[abbr] = definition

    # Pattern 2: "full name (ABBR)" inline definitions
    for match in re.finditer(r"([A-Z][a-z]+(?:\s+[a-z]+)*(?:\s+[A-Z][a-z]+)*)\s*\(([A-Z]{2,8})\)", text):
        definition = match.group(1).strip()
        abbr = match.group(2).strip()
        if abbr not in abbreviations and len(definition) > 3:
            abbreviations[abbr] = definition

    return abbreviations


def deduplicate_abbreviation_expansions(text: str, abbreviations: dict[str, str]) -> str:
    """
    After the first occurrence of 'Full Name (ABBR)', replace subsequent
    occurrences of 'Full Name (ABBR)' with just 'ABBR'.
    Keeps one canonical definition per document.
    """
    for abbr, definition in abbreviations.items():
        # Escape for regex
        escaped_def = re.escape(definition)
        escaped_abbr = re.escape(abbr)
        pattern = rf"({escaped_def}\s*\({escaped_abbr}\))"
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        # Keep first definition, replace subsequent with just the abbreviation
        for match in matches[1:]:
            text = text[: match.start()] + abbr + text[match.end() :]
    return text


# ---------------------------------------------------------------------------
# 8. SEMANTIC CHUNKING
# ---------------------------------------------------------------------------

# Section header patterns (hierarchical)
SECTION_HEADER_PATTERNS = [
    # Numbered headers: "4.2.1 Section title"
    re.compile(r"^(\d+(?:\.\d+)*)\s+(.+)$"),
    # Unnumbered headers: short lines in title case or all caps
    re.compile(r"^([A-Z][A-Za-z\s,\-:]+)$"),
]

# Recommendation block markers
RECOMMENDATION_MARKERS = [
    "strong recommendation",
    "conditional recommendation",
    "practice statement",
    "good practice statement",
    "recommendation:",
    "the panel recommends",
    "the panel suggests",
    "who recommends",
]


def estimate_tokens(text: str) -> int:
    """Estimate token count from word count (1 token ~= 0.75 words)."""
    words = len(text.split())
    return int(words / WORDS_PER_TOKEN)


def is_section_header(line: str) -> bool:
    """Check if a line is a section header."""
    stripped = line.strip()
    if not stripped or len(stripped) > 200:
        return False
    # Numbered section header
    if re.match(r"^\d+(?:\.\d+)*\s+[A-Z]", stripped):
        return True
    # Short uppercase or title-case line (likely header)
    
    CLINICAL_HEADERS = [
        "recommendation",
        "management",
        "treatment",
        "case management",
        "clinical care",
        "patient management"
    ]

    if any(h in stripped.lower() for h in CLINICAL_HEADERS):
        return True

    if len(stripped) < 100 and stripped[0].isupper():
        words = stripped.split()
        if len(words) <= 12 and not stripped.endswith("."):
            caps = sum(1 for w in words if w[0].isupper() or w in ("and", "or", "of", "in", "for", "the", "to", "a", "an", "with"))
            if caps >= len(words) * 0.6:
                return True
    return False


def split_into_sections(text: str) -> list[dict]:
    """
    Split text into sections based on headers.
    Returns list of {title: str, content: str, level: int}.
    """
    lines = text.split("\n")
    sections = []
    current_title = "Introduction"
    current_level = 0
    current_lines = []

    for line in lines:
        stripped = line.strip()
        if is_section_header(stripped):
            # Save previous section
            if current_lines:
                content = "\n".join(current_lines).strip()
                if content:
                    sections.append({
                        "title": current_title,
                        "content": content,
                        "level": current_level,
                    })
            # Determine level from numbering
            level_match = re.match(r"^(\d+(?:\.\d+)*)", stripped)
            if level_match:
                current_level = level_match.group(1).count(".") + 1
                current_title = stripped
            else:
                current_level = 0
                current_title = stripped
            current_lines = []
        else:
            current_lines.append(line)

    # Final section
    if current_lines:
        content = "\n".join(current_lines).strip()
        if content:
            sections.append({
                "title": current_title,
                "content": content,
                "level": current_level,
            })

    return sections


def chunk_section(section: dict, min_tokens: int = MIN_CHUNK_TOKENS,
                  max_tokens: int = MAX_CHUNK_TOKENS) -> list[dict]:
    """
    Split a section into chunks targeting 400-700 tokens.
    Never splits in the middle of a recommendation or guideline rule.
    """
    content = section["content"]
    title = section["title"]

    # If section is small enough, return as single chunk
    if estimate_tokens(content) <= max_tokens:
        return [{"title": title, "content": content}]

    # Split by paragraphs (double newline)
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]

    chunks = []
    current_chunk_parts = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = estimate_tokens(para)

        # Check if paragraph is part of a recommendation block (never split these)
        is_recommendation = any(
            marker in para.lower() for marker in RECOMMENDATION_MARKERS
        )

        # If adding this paragraph would exceed max and we have content, finalize
        if current_tokens + para_tokens > max_tokens and current_chunk_parts:
            # Don't split if current chunk is too small and this is a recommendation
            if current_tokens >= min_tokens or is_recommendation:
                chunks.append({
                    "title": title,
                    "content": "\n\n".join(current_chunk_parts),
                })
                current_chunk_parts = []
                current_tokens = 0

        # If a single paragraph exceeds max, split by sentences
        if para_tokens > max_tokens and not is_recommendation:
            if current_chunk_parts:
                chunks.append({
                    "title": title,
                    "content": "\n\n".join(current_chunk_parts),
                })
                current_chunk_parts = []
                current_tokens = 0
            # Split large paragraph by sentences
            sentence_chunks = _split_by_sentences(para, min_tokens, max_tokens)
            for sc in sentence_chunks:
                chunks.append({"title": title, "content": sc})
        else:
            current_chunk_parts.append(para)
            current_tokens += para_tokens

    # Final chunk
    if current_chunk_parts:
        chunks.append({
            "title": title,
            "content": "\n\n".join(current_chunk_parts),
        })

    return chunks


def _split_by_sentences(text: str, min_tokens: int, max_tokens: int) -> list[str]:
    """Split text by sentences, respecting token limits."""
    # Sentence boundary detection (simplified but effective for guidelines)
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
    chunks = []
    current = []
    current_tokens = 0

    for sent in sentences:
        sent_tokens = estimate_tokens(sent)
        if current_tokens + sent_tokens > max_tokens and current:
            chunks.append(" ".join(current))
            current = []
            current_tokens = 0
        current.append(sent)
        current_tokens += sent_tokens

    if current:
        chunks.append(" ".join(current))

    return chunks


# ---------------------------------------------------------------------------
# 9. METADATA ENRICHMENT
# ---------------------------------------------------------------------------

def infer_target_population(text: str, default: str) -> str:
    """Infer target population from chunk content."""
    text_lower = text.lower()
    populations = []
    if any(w in text_lower for w in ["neonate", "newborn", "neonatal"]):
        populations.append("neonates")
    if any(w in text_lower for w in ["child", "children", "paediatric", "pediatric", "infant"]):
        populations.append("children")
    if any(w in text_lower for w in ["pregnan", "maternal", "lactating"]):
        populations.append("pregnant women")
    if any(w in text_lower for w in ["plhiv", "hiv-positive", "hiv positive", "co-infected with hiv"]):
        populations.append("PLHIV")
    if any(w in text_lower for w in ["health-care worker", "healthcare worker", "hcw"]):
        populations.append("health-care workers")
    if any(w in text_lower for w in ["adult", "adults"]):
        populations.append("adults")
    if any(w in text_lower for w in ["elderly", "older adult"]):
        populations.append("elderly")

    return ", ".join(populations) if populations else default


def build_chunk_id(document_name: str, section_title: str, chunk_index: int) -> str:
    """Generate a unique, deterministic chunk ID."""
    raw = f"{document_name}|{section_title}|{chunk_index}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def enrich_chunk(chunk: dict, config: dict, chunk_index: int) -> dict:
    """Add structured metadata to a chunk."""
    content = chunk["content"]
    section_title = chunk["title"]

    metadata = {
        "source": "WHO",
        "document_name": config["document_name"],
        "disease": config["disease"],
        "guideline_type": config["guideline_type"],
        "section_title": section_title,
        "target_population": infer_target_population(content, config["target_population"]),
        "publication_year": config["publication_year"],
    }

    chunk_id = build_chunk_id(config["document_name"], section_title, chunk_index)

    return {
        "id": chunk_id,
        "metadata": metadata,
        "content": content,
    }


# ---------------------------------------------------------------------------
# 10. DATA QUALITY SAFEGUARDS
# ---------------------------------------------------------------------------

def deduplicate_chunks(chunks: list[dict]) -> list[dict]:
    """Remove exact and near-duplicate chunks based on content hash."""
    seen_hashes = set()
    unique_chunks = []
    for chunk in chunks:
        # Use content hash for exact dedup
        content_hash = hashlib.md5(chunk["content"].strip().lower().encode()).hexdigest()
        if content_hash not in seen_hashes:
            seen_hashes.add(content_hash)
            unique_chunks.append(chunk)
    return unique_chunks


def ensure_sentence_boundaries(text: str) -> str:
    """Ensure chunk does not start or end mid-sentence."""
    text = text.strip()
    if not text:
        return text

    # Trim leading fragment (no capital letter start, no bullet, no number)
    if text and not text[0].isupper() and not re.match(r"^[\d\-•]", text):
        # Find first sentence start
        match = re.search(r"[.!?]\s+([A-Z])", text)
        if match:
            text = text[match.start() + 2:]

    # Trim trailing fragment (no terminal punctuation)
    if text and not re.search(r"[.!?:]\s*$", text):
        # Find last sentence end
        last_end = max(
            text.rfind(". "), text.rfind("? "), text.rfind("! "),
            text.rfind(".\n"), text.rfind("."), text.rfind(":")
        )
        if last_end > len(text) * 0.5:  # Only trim if we keep most of the content
            text = text[: last_end + 1]

    return text.strip()


def validate_chunk(chunk: dict) -> bool:
    """Validate that a chunk meets quality requirements."""
    content = chunk["content"]
    # Minimum length check
    if len(content.strip()) < 50:
        return False
    # Check it's not pure noise
    alpha_ratio = sum(1 for c in content if c.isalpha()) / max(len(content), 1)
    if alpha_ratio < 0.4:
        return False
    # Ensure it contains actual words
    words = content.split()
    if len(words) < 10:
        return False
    return True


# ---------------------------------------------------------------------------
# 11. MAIN PIPELINE
# ---------------------------------------------------------------------------

def preprocess_guideline(filepath: str, config: dict) -> list[dict]:
    """
    Full preprocessing pipeline for a single guideline TXT file.
    Returns list of enriched chunks ready for JSONL output.
    """
    print(f"  [1/10] Reading: {filepath}")
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    # Step 2: Global noise removal
    print("  [2/10] Removing boilerplate...")
    text = remove_boilerplate(text)
    text = remove_section_blocks(text)
    text = remove_toc(text)

    # Step 3: Page-level cleanup
    print("  [3/10] Cleaning page artifacts...")
    text = clean_page_artifacts(text)
    text = remove_ocr_artifacts(text)

    # Step 4: Text normalization
    print("  [4/10] Normalizing text...")
    text = normalize_unicode(text)
    text = fix_hyphenation(text)
    text = normalize_line_breaks(text)
    text = normalize_bullets(text)
    text = collapse_blank_lines(text)

    # Step 5: Table handling
    print("  [5/10] Processing tables...")
    text = detect_and_convert_tables(text)

    # Step 6: Citation removal
    print("  [6/10] Cleaning citations...")
    text = remove_citations(text)

    # Step 7: Abbreviation extraction & dedup
    print("  [7/10] Processing abbreviations...")
    abbreviations = extract_abbreviations(text)
    text = deduplicate_abbreviation_expansions(text, abbreviations)

    # Step 8: Semantic chunking
    print("  [8/10] Semantic chunking...")
    sections = split_into_sections(text)
    all_chunks = []
    for section in sections:
        chunks = chunk_section(section)
        all_chunks.extend(chunks)

    # Step 9: Metadata enrichment
    print("  [9/10] Enriching metadata...")
    enriched = []
    for i, chunk in enumerate(all_chunks):
        # Ensure sentence boundaries
        chunk["content"] = ensure_sentence_boundaries(chunk["content"])
        # Enrich with metadata
        enriched_chunk = enrich_chunk(chunk, config, i)
        enriched.append(enriched_chunk)

    # Step 10: Quality safeguards
    print("  [10/10] Quality checks & deduplication...")
    enriched = [c for c in enriched if validate_chunk(c)]
    enriched = deduplicate_chunks(enriched)

    print(f"  -> Produced {len(enriched)} chunks from {os.path.basename(filepath)}")
    return enriched


def write_jsonl(chunks: list[dict], output_path: str) -> None:
    """Write chunks to a JSONL file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
    print(f"  -> Written to: {output_path}")


def run_pipeline():
    """Run the full preprocessing pipeline across all guideline documents."""
    base_dir = Path(__file__).resolve().parents[1]
    guidelines_dir = base_dir / "data" / "guidelines"
    output_dir = base_dir / "data" / "processed"

    print("=" * 60)
    print("WHO Guideline RAG Preprocessing Pipeline")
    print("=" * 60)

    # Collect all TXT files in guidelines directory
    txt_files = sorted(guidelines_dir.glob("*.txt"))
    if not txt_files:
        print(f"ERROR: No .txt files found in {guidelines_dir}")
        return

    print(f"\nFound {len(txt_files)} guideline files:")
    for f in txt_files:
        print(f"  - {f.name}")
    print()

    total_chunks = 0
    for txt_file in txt_files:
        fname = txt_file.name

        
        if fname in SKIP_FILES:
                print(f"Skipping (already finalized): {fname}")
                continue


        # Skip already-cleaned files to avoid double processing
        if "_clean" in fname:
            print(f"Skipping (already cleaned): {fname}")
            continue

        config = DOCUMENT_CONFIGS.get(fname, DEFAULT_CONFIG.copy())
        # Auto-detect disease from filename if not configured
        if config.get("disease") == "Unknown":
            config = _infer_config_from_filename(fname, config)

        print(f"\nProcessing: {fname}")
        print("-" * 40)
        chunks = preprocess_guideline(str(txt_file), config)

        # Output JSONL
        output_name = txt_file.stem + "_chunks.jsonl"
        output_path = str(output_dir / output_name)
        write_jsonl(chunks, output_path)
        total_chunks += len(chunks)

    print(f"\n{'=' * 60}")
    print(f"Pipeline complete. Total chunks produced: {total_chunks}")
    print(f"Output directory: {output_dir}")
    print(f"{'=' * 60}")


def _infer_config_from_filename(fname: str, config: dict) -> dict:
    """Infer document metadata from filename when no explicit config exists."""
    fname_lower = fname.lower()
    if "covid" in fname_lower:
        config["disease"] = "COVID-19"
        config["guideline_type"] = "clinical"
    elif "malaria" in fname_lower:
        config["disease"] = "Malaria"
        config["guideline_type"] = "treatment"
    elif "dengue" in fname_lower or "arboviral" in fname_lower:
        config["disease"] = "Dengue"
        config["guideline_type"] = "clinical"
    elif "tuberc" in fname_lower or "tb" in fname_lower:
        config["disease"] = "Tuberculosis"
        config["guideline_type"] = "prevention"
    elif "bloodstream" in fname_lower or "catheter" in fname_lower:
        config["disease"] = "Bloodstream infection"
        config["guideline_type"] = "IPC"
    config["document_name"] = fname.replace("_", " ").replace(".txt", "")
    return config


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run_pipeline()
