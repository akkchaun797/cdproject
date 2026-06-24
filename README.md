# BankABC Smartdeals — Creative Validation Tool

A Streamlit tool that validates monthly marketing creatives (email PDF + social
media images) against the source offer Excel, and produces a clear pass/fail
report for a non-technical reviewer. It cuts manual validation from ~45–60 min
to under 5 min.

## What it checks

**Email campaign (PDF)** — 6 checks per merchant:
1. Merchant present in the Excel
2. Merchant name spelling matches the Excel exactly
3. Discount / offer value matches the Excel `Offer Title`
4. Validity date matches `offer_valid_to`
5. An image asset URL is supplied in the Excel
6. Merchants in the Excel but missing from the creative (flagged separately)
   plus a document-level CTA / Bank ABC branding check.

**Social media campaign (images)** — checks per image:
1. Merchant identified and present in Excel (via filename or image text)
2. Resolution meets Instagram minimum (1080×1080 square, 1080×1350 portrait)
3. Discount matches the Excel
4. Validity date matches the Excel
5. Merchant name spelled correctly in the post
6. Bank ABC branding present
7. Smartdeals / app CTA present
8. Unmatched image files flagged for investigation

## How to run

```bat
cd cdproject
venv\Scripts\activate
python -m streamlit run src/app.py
```

Create a `.env` file in the project root with your key:

```
OPENAI_API_KEY=sk-...
```

## Dependencies

```
pip install streamlit pandas openpyxl pymupdf pillow openai python-dotenv
```

## How to use

1. Upload the monthly **Excel** (source of truth).
2. Upload the **email PDF** and/or **social media images**. Images can be
   uploaded individually or as a single **.zip** archive.
3. Click **Run Validation**.
4. Review the two separate reports, then **Download full report (Excel)** —
   a colour-coded workbook with one sheet per campaign type.

## Reading the output

- ✅ **Pass** (green) — check passed.
- ❌ **Fail** (red) — mismatch; cell shows both the creative and Excel value.
- ⚠️ **Review / N/A** (amber) — needs a human look (e.g. unmatched file).

The metrics row above each table summarises total / passed / failed at a glance.

## Extraction approach

Data is extracted with **GPT-4 Vision (gpt-4o)** rather than rule-based PDF/OCR
parsing, because marketing creatives use designed, graphical, and bilingual
layouts where raw text extraction is unreliable. A rule-based parser
(`pdf_parser.py`) is retained as a backup. See the research document for the
full LLM-vs-library comparison and rationale.

## Files

| File | Purpose |
|------|---------|
| `src/app.py` | Streamlit UI, ZIP handling, two reports, Excel export |
| `src/validator.py` | All validation checks + date/name/discount matching |
| `src/openai_extractor.py` | GPT-4 Vision extraction (PDF offers + CTA, image text) |
| `src/report_export.py` | Colour-coded Excel report builder |
| `src/pdf_parser.py` | Rule-based PDF parser (backup) |
| `src/main.py` | Standalone Excel date-normalisation demo |

## Limitations & assumptions

- The "image matches Crayon-provided asset" check is implemented as an
  *asset-URL-present* check, not pixel comparison — visual asset matching is
  out of scope for this version.
- Only English content is validated (Arabic is out of scope).
- Discount matching compares numeric tokens (%, $, AED, counts) and falls back
  to fuzzy text similarity for purely descriptive offers.
- GPT-4 Vision extraction depends on creative legibility; very stylised text may
  need manual review.
- The sample `april_2026_offers.xlsx` / `.pdf` in this repo are mock data and
  their dates are not mutually consistent, so the demo will show date fails.
  Regenerate the PDF from the Excel (or use the real April data) for a clean pass.
