# Smartdeals Creative Validation Tool — Project Plan

---

## What Problem Are We Solving?

Every month, Bank ABC runs a merchant offers program called **Smartdeals**. Crayon Data provides the bank's marketing team with a list of merchant offers in an Excel file. The marketing team then designs campaign creatives (email PDFs and Instagram images) based on that Excel.

Before any campaign goes out, Crayon Data must manually check every creative to make sure:
- Merchant names are spelled correctly
- Discount values match the Excel
- Validity dates are correct
- Images are the ones Crayon provided
- The creative has a proper call-to-action (CTA) for the app

Currently this takes **45–60 minutes per cycle** and is done by a person opening files side by side. Mistakes cause incorrect offers to reach cardholders, requiring reruns and damaging the client relationship.

**We are building a tool that does this automatically in under 5 minutes.**

---

## What Will the Tool Do? (User Flow)

The person running validation will:

1. Open the tool in a web browser
2. Upload the monthly Excel file (the source of truth for all offers)
3. Upload the email campaign PDF
4. Upload the Instagram post images (or a single ZIP file with all of them)
5. Click **"Run Validation"**
6. Instantly get a report showing every merchant — what passed, what failed, and exactly what is wrong

---

## Checks the Tool Runs

### Email PDF — 6 Checks Per Merchant

| # | Check | What It Looks For |
|---|---|---|
| 1 | Merchant in Excel | Every merchant in the email must exist in this month's Excel |
| 2 | Discount match | The percentage or offer text must match the Excel |
| 3 | Date match | The offer end date must match the Excel exactly |
| 4 | Image from Crayon | The image used must be one Crayon provided, not sourced elsewhere |
| 5 | CTA present | The email must include a link/prompt to the Bank ABC app or Smartdeals |
| 6 | Missing merchants | Any Excel merchant missing from the email gets flagged |

### Instagram Images — 8 Checks Per Image

| # | Check | What It Looks For |
|---|---|---|
| 1 | Merchant identified | Image is matched to a merchant row in the Excel |
| 2 | Resolution | Must be at least 1080 × 1080 pixels (Instagram minimum) |
| 3 | Discount match | Discount in image matches the Excel |
| 4 | Date match | End date in image matches the Excel |
| 5 | Image from Crayon | Image content must be from Crayon-provided assets |
| 6 | Bank branding | "Bank ABC" or "Smartdeals" must be visible |
| 7 | CTA present | Must direct viewers to the app or Smartdeals |
| 8 | Unmatched files | Any image file with no matching Excel merchant gets flagged |

---

## Tech Stack

| Layer | Technology | Why We Chose It |
|---|---|---|
| Language | **Python 3.10+** | Best ecosystem for Excel, PDFs, images, and AI in one place |
| Web UI | **Streamlit** | Builds a browser app with minimal code — no separate frontend needed |
| Excel reading | **pandas + openpyxl** | Industry-standard Python libraries for reading Excel files |
| PDF processing | **PyMuPDF (fitz)** | Converts PDF pages to images and extracts embedded images — no extra software install needed |
| Image handling | **Pillow** | Checks resolution, reads image dimensions and formats |
| AI text extraction | **Anthropic Claude API** (Haiku model) | Reads text from designed PDFs and images the way a human would |
| URL verification | **requests** | Checks that Crayon CDN image URLs are still working |
| Env config | **python-dotenv** | Stores the API key securely outside the code |

> **Why Claude (AI) instead of traditional text reading?**
> Designed marketing PDFs and Instagram posts have text layered over graphics and backgrounds. Standard text-extraction tools fail on these because they can't understand the layout. Claude looks at the image visually — the same way a person does — and reliably pulls out merchant names, discounts, and dates regardless of the design.

---

## File & Folder Structure

```
cdproject/
│
├── app.py                  ← The web interface — what opens in the browser
├── requirements.txt        ← All the software packages the tool needs
├── .env.example            ← Template showing where to put the API key
│
└── src/                    ← The working engine of the tool
    ├── __init__.py         ← Tells Python this folder is a module (leave empty)
    ├── excel_parser.py     ← Reads the Excel and handles date formats
    ├── pdf_extractor.py    ← Converts PDF to images, sends to Claude, gets data
    ├── image_extractor.py  ← Sends Instagram images to Claude, checks resolution
    ├── validator.py        ← Runs all checks and collects results
    └── utils.py            ← Shared helpers: date parsing, name matching, etc.
```

---

## Step-by-Step Build Plan

---

### Step 1 — Set Up the Project Environment

**What to do:**
1. Make sure Python 3.10 or higher is installed on your computer
2. Inside the `cdproject` folder, create a file called `requirements.txt` with these contents:
   ```
   streamlit
   pandas
   openpyxl
   anthropic
   pymupdf
   Pillow
   requests
   python-dotenv
   ```
3. Open a terminal in the `cdproject` folder and run:
   ```
   pip install -r requirements.txt
   ```
4. Create a file called `.env` in the `cdproject` folder and add your Anthropic API key:
   ```
   ANTHROPIC_API_KEY=your-key-here
   ```
5. Create the `src/` folder and an empty file inside it called `__init__.py`

**How to verify:** Run `python -c "import streamlit, anthropic, fitz, pandas"` — if no errors appear, the setup worked.

---

### Step 2 — Build the Excel Reader (`src/excel_parser.py`)

**What this file does:**
Reads the monthly Excel file and turns it into a clean list of merchants with all their details.

**Key things to handle:**
- The Excel has columns like `offer_merchant_name`, `Offer Title`, `offer_valid_from`, `offer_valid_to`, `Logo`, `Banner`, `Merchant Image`, `Offer image`
- Dates come in two formats:
  - Human-readable string: `"25-03-2026"`
  - Excel serial number: `46142` (a number Excel uses internally for dates)
- The code must convert both into a standard Python date before comparing

**Functions to write:**
- `parse_excel(file)` → reads the file, returns a list of merchant dictionaries
- `parse_date(value)` → converts any date format (string or serial number) to a Python date

**How to verify:** Load the April 2026 Excel and print the list of merchants — you should see 9 merchants with clean names and properly formatted dates.

---

### Step 3 — Build the PDF Extractor (`src/pdf_extractor.py`)

**What this file does:**
Takes the email PDF, converts each page into a PNG image, sends it to Claude, and gets back a structured list of what merchants appear — with their discount and validity date.

**Key things to handle:**
- Use PyMuPDF to render each PDF page as a high-resolution PNG (150 DPI is enough)
- Send those PNG images to Claude using the Anthropic API
- Give Claude a clear prompt asking it to extract: merchant name, discount text, offer end date, and whether a CTA is present
- Claude returns JSON — parse that JSON into a Python dictionary

**Functions to write:**
- `pdf_to_page_images(pdf_bytes)` → converts PDF pages to list of PNG bytes
- `extract_pdf_embedded_images(pdf_bytes)` → pulls out all images embedded inside the PDF (used for image-asset check)
- `extract_from_pdf(pdf_bytes, api_key)` → main function — runs the full Claude extraction

**The Claude prompt should ask for output in this format:**
```json
{
  "merchants": [
    { "merchant_name": "Fairmont Dubai", "discount": "From AED 550/night", "valid_to": "30 Apr 2026" }
  ],
  "overall_cta": true
}
```

**How to verify:** Run on the April 2026 PDF — Claude should return all 9 merchants with correct names, discounts, and dates.

---

### Step 4 — Build the Image Extractor (`src/image_extractor.py`)

**What this file does:**
Takes each Instagram post image, checks its resolution, then sends it to Claude to extract the merchant name, discount, date, and whether branding/CTA are visible.

**Key things to handle:**
- Use Pillow to open the image and read its width and height in pixels
- Flag any image where the smallest dimension is below 1080px
- Send the image to Claude as a base64-encoded string
- Parse Claude's response back into a Python dictionary

**Functions to write:**
- `get_image_resolution(image_bytes)` → returns (width, height) as numbers
- `extract_from_image(image_bytes, filename, api_key)` → sends image to Claude, returns extracted data

**The Claude prompt should ask for:**
```json
{
  "merchant_name": "NexAuto",
  "discount": "Up to 30% off",
  "valid_to": "31 Dec 2026",
  "has_bank_branding": true,
  "has_cta": true
}
```

**How to verify:** Run on one Instagram post image — the merchant name, discount, and date returned by Claude should match the Excel.

---

### Step 5 — Build the Validator (`src/validator.py`)

**What this file does:**
This is the core logic. It takes the data from Steps 2, 3, and 4 and runs all the checks, producing a pass/fail result for each merchant on each check.

**Functions to write:**

`validate_email_pdf(excel_merchants, pdf_data, pdf_embedded_images)`
- Loops through every merchant Claude found in the PDF
- Finds the matching Excel row (using fuzzy name matching)
- Runs checks 1–5 for that merchant
- At the end, compares the Excel list against the PDF list to find check 6 (missing merchants)
- Returns a results object

`validate_social_images(excel_merchants, images_data)`
- Loops through each Instagram image's extracted data
- Finds the matching Excel row
- Runs checks 1–8
- Returns a results object

**Shared helper needed (`src/utils.py`):**
- `names_match(a, b)` — fuzzy string comparison so "Fairmont – Dubai" matches "Fairmont Dubai"
- `discounts_match(excel_text, creative_text)` — extracts percentages from both and compares numbers
- `dates_match(excel_date, creative_date_string)` — parses the creative date string and compares to Excel date
- `download_image(url)` — downloads a CDN image for comparison, returns None if it fails

**Image asset check approach:**
1. Download all CDN images from the Excel's image URL columns
2. Extract all images embedded in the PDF using PyMuPDF
3. For each merchant, check if at least one of their CDN images appears in the PDF (by comparing MD5 file hashes)
4. If hashes can't be matched (e.g. due to re-compression), mark as "needs manual review" — do not auto-fail

**How to verify:** Run on the April 2026 sample — all 9 merchants should show all checks as PASS.

---

### Step 6 — Build the Web Interface (`app.py`)

**What this file does:**
This is the browser-facing part. It provides the file upload widgets, triggers the validation, and displays the report.

**Layout:**
```
┌────────────────────────────────────────────────┐
│  Sidebar                                       │
│  - API key input (if not in .env)              │
│  - About section                               │
├────────────────────────────────────────────────┤
│  Main area                                     │
│  [Upload Excel]  [Upload PDF]  [Upload Images] │
│                                                │
│  [ Run Validation ]                            │
│                                                │
│  ── Email Results ─────────────────────────── │
│  Summary: 9 checked | 9 passed | 0 failed      │
│  ✅ Fairmont Dubai  (expand for details)        │
│  ✅ NexAuto         (expand for details)        │
│  ❌ Dollar Car Rental                           │
│     Discount: Excel 10% | Creative shows 20%   │
│                                                │
│  ── Social Media Results ──────────────────── │
│  (same format)                                 │
│                                                │
│  [ Download Report as HTML ]                   │
└────────────────────────────────────────────────┘
```

**Key UI behaviours:**
- Excel upload is required before anything else can run
- PDF and image uploads are both optional (can validate just one campaign type at a time)
- A progress spinner shows while Claude is processing
- Results use colour-coded badges: ✅ PASS, ❌ FAIL, ⚠️ REVIEW
- Each merchant row is expandable to show per-check detail
- A "Download Report" button exports the results as a self-contained HTML file

**How to verify:** Open `http://localhost:8501`, upload all three file types from the April 2026 sample, click Run, and confirm the report looks correct.

---

### Step 7 — Test With Seeded Errors

**What to do:**
Take a copy of the April 2026 Excel and deliberately introduce errors:
- Change one discount from 15% to 25%
- Change one validity date by one day
- Remove one merchant name

Run the tool and confirm it flags exactly those three issues and nothing else.

---

### Step 8 — Write the README

**What the README must include:**
- What the tool does (one paragraph)
- How to install it (pip install command)
- How to set up the API key
- How to start it (streamlit run app.py)
- How to interpret the report (what ✅ ❌ ⚠️ each mean)
- Known limitations

---

## What the Final Report Looks Like

```
── Email Campaign Validation ─────────────────────────────────
  9 merchants checked │ 8 passed │ 1 failed │ 0 missing

  ✅ Fairmont Dubai
  ✅ Millennium Hotels & Resorts
  ✅ NexAuto
  ✅ Pressman's
  ✅ Kimura-ya Japanese Restaurant
  ✅ Erth Abu Dhabi
  ✅ Sevilla - Al Raha Beach Resort & Spa
  ✅ Kanto Wagyu
  ❌ Dollar Car Rental
       Discount check    ❌   Excel: "Up to 10% off" | Creative shows "20% off"
       Date check        ✅
       In Excel          ✅
       CTA present       ✅
       Image from Crayon ⚠️   Verify manually

── Social Media Validation ────────────────────────────────────
  9 images checked │ 9 passed │ 0 failed
  ...


