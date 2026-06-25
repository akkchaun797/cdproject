import re  # noqa
import pandas as pd
from datetime import datetime, date, timedelta
from difflib import SequenceMatcher

PASS = "✅ Pass"


# ─────────────────────────────────────────────────────────────
#  Normalisation helpers
# ─────────────────────────────────────────────────────────────
def normalise_date(val):
    """Real dates, Excel serial integers OR string dates → YYYY-MM-DD."""
    # empty / missing cells (NaN, NaT, None)
    try:
        if val is None or pd.isna(val):
            return ""
    except (TypeError, ValueError):
        pass
    # real date / datetime / pandas Timestamp (Timestamp subclasses datetime)
    if isinstance(val, (datetime, date)):
        return val.strftime("%Y-%m-%d")
    if hasattr(val, "strftime"):  # defensive: any other date-like object
        return val.strftime("%Y-%m-%d")
    if isinstance(val, (int, float)):
        return (datetime(1899, 12, 30) + timedelta(days=int(val))).strftime("%Y-%m-%d")
    if isinstance(val, str):
        s = val.strip()
        # unify separators so 30\04\2026, 30.04.2026, 30/04/2026 all work
        s_norm = re.sub(r"[\\/.]", "-", s)
        s_clean = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", s_norm).replace(",", "")
        for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d-%b-%Y", "%d-%B-%Y",
                    "%b-%d-%Y", "%B-%d-%Y", "%d %B %Y", "%d %b %Y",
                    "%B %d %Y", "%b %d %Y"):
            try:
                return datetime.strptime(s_clean.strip(), fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
    return str(val)


def date_in_text(excel_iso: str, text: str) -> bool:
    """True if the Excel end-date (YYYY-MM-DD) appears in `text` in ANY common format."""
    text = str(text)
    if excel_iso.lower() in text.lower():
        return True
    # numeric dates: 30/04/2026, 30-04-2026, 2026-04-30, 30.04.2026, 30\04\2026
    for m in re.findall(r"\d{1,4}[\\/.\-]\d{1,2}[\\/.\-]\d{1,4}", text):
        if normalise_date(m) == excel_iso:
            return True
    # textual dates: 30 April 2026 / April 30, 2026 / 30 Apr 2026
    for m in re.findall(r"[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]{3,9}\s+[0-9]{4}", text):
        if normalise_date(m) == excel_iso:
            return True
    for m in re.findall(r"[A-Za-z]{3,9}\s+[0-9]{1,2}(?:st|nd|rd|th)?,?\s+[0-9]{4}", text):
        if normalise_date(m) == excel_iso:
            return True
    return False


def normalise_name(s) -> str:
    """Lowercase, strip punctuation, collapse whitespace — for fuzzy matching."""
    s = str(s).lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def normalise_quotes(s: str) -> str:
    """Unify typographic apostrophes/quotes and odd spaces to plain ASCII."""
    s = str(s)
    for ch in ("’", "‘", "‛", "ʼ", "´", "`"):  # curly/odd apostrophes
        s = s.replace(ch, "'")
    for ch in ("“", "”"):  # curly double quotes
        s = s.replace(ch, '"')
    return s.replace(" ", " ")  # non-breaking space


def same_spelling(a: str, b: str) -> bool:
    """Exact spelling match, but tolerant of quote style, case and whitespace."""
    def n(x):
        return re.sub(r"\s+", " ", normalise_quotes(x)).strip().lower()
    return n(a) == n(b)


def fuzzy_ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, normalise_name(a), normalise_name(b)).ratio()


def best_excel_match(name: str, excel_df: pd.DataFrame):
    """Return (row, ratio) for the Excel merchant most similar to `name`."""
    best_row, best_score = None, 0.0
    for _, row in excel_df.iterrows():
        score = fuzzy_ratio(name, row["offer_merchant_name"])
        if score > best_score:
            best_row, best_score = row, score
    return best_row, best_score


# ─────────────────────────────────────────────────────────────
#  Discount / offer matching
# ─────────────────────────────────────────────────────────────
def _percentages(text: str) -> set:
    return set(re.findall(r"(\d+)\s*%", str(text).lower()))


def _numbers(text: str) -> set:
    """All numbers, currency-agnostic (AED 550 and 550 both -> '550')."""
    return set(re.findall(r"\d+", str(text).lower().replace(",", "")))


def discount_match(creative_text: str, excel_title: str):
    """
    3-state discount comparison:
      True  -> values match
      False -> values clearly conflict (e.g. 20% vs 15%)
      None  -> cannot be determined from the creative (blank / unreadable) → review
    Currency symbols are ignored, so 'AED 550' matches '550 net/night'.
    """
    c = str(creative_text).strip().lower()
    e = str(excel_title).strip().lower()
    if not c:
        return None  # nothing extracted from the creative → needs manual review

    c_pct, e_pct = _percentages(c), _percentages(e)
    c_num, e_num = _numbers(c), _numbers(e)

    # Excel offer is percentage-based (most common: "Up to 30% off")
    if e_pct:
        if c_pct:
            return e_pct == c_pct                # both show a % → must be equal
        if e_pct & c_num:
            return True                          # % value present without the sign
        return None                              # creative shows no comparable value
    # Excel offer is amount-based ("From AED 550", "$50")
    if e_num:
        if c_num:
            return e_num.issubset(c_num)
        return None
    # purely descriptive offer ("Buy 1 Get 1", "Free dessert")
    return fuzzy_ratio(c, e) >= 0.5


# ─────────────────────────────────────────────────────────────
#  Excel loading
# ─────────────────────────────────────────────────────────────
def load_excel(file) -> pd.DataFrame:
    df = pd.read_excel(file)
    df["offer_valid_to"] = df["offer_valid_to"].apply(normalise_date)
    df["offer_merchant_name"] = df["offer_merchant_name"].astype(str).str.strip()
    return df


def _image_url_present(row) -> bool:
    """True if any image-asset column for this row holds a URL."""
    candidates = ["image URLs", "Logo", "Banner", "Merchant Image", "Offer image"]
    for col in candidates:
        if col in row.index:
            val = row.get(col, "")
            if pd.notna(val) and str(val).strip().lower().startswith("http"):
                return True
    return False


def _cta_in_text(text: str) -> bool:
    t = str(text).lower().replace(" ", "")
    return any(k in t for k in ["smartdeals", "bankabc", "mobileapp", "bankabcapp"])


def _branding_in_text(text: str) -> bool:
    t = str(text).lower().replace(" ", "")
    return ("bankabc" in t) or ("smartdeals" in t)


def _name_in_image(excel_name: str, text: str) -> bool:
    """
    True if the merchant name appears in the image text. Tolerant of shortened
    forms and '&' vs 'and' (e.g. Excel 'Millennium Hotels & Resorts' matches a
    post that says 'Millennium Hotels'). Passes when most significant name
    words are present.
    """
    en = normalise_name(excel_name)          # '&' already stripped -> words only
    tx = normalise_name(text)
    if en and en in tx:
        return True
    words = [w for w in en.split() if len(w) >= 4] or en.split()
    if not words:
        return False
    hits = sum(1 for w in words if w in tx)
    # at least half of the significant words must appear (min 1)
    return hits >= max(1, (len(words) + 1) // 2)


# ─────────────────────────────────────────────────────────────
#  EMAIL PDF validation — 6 checks
# ─────────────────────────────────────────────────────────────
def validate_email_pdf(pdf_offers: list, excel_df: pd.DataFrame, cta_text: str = "") -> dict:
    """
    Returns {"rows": [...], "missing": [...], "cta": str}
    Checks 1-5 run per merchant; check 6 (missing merchants) returned separately.
    """
    rows = []
    matched_excel = set()

    for offer in pdf_offers:
        creative_name = str(offer.get("merchant", "")).strip()
        offer_text = str(offer.get("offer_text", "")).strip()
        valid_till = normalise_date(offer.get("valid_till", "").strip())

        row, score = best_excel_match(creative_name, excel_df)

        # Check 1 — merchant present in Excel
        if row is None or score < 0.6:
            rows.append({
                "Merchant (creative)": creative_name or offer_text,
                "1. In Excel": "❌ Not found",
                "2. Spelling": "⚠️ N/A",
                "3. Discount": "⚠️ N/A",
                "4. Validity date": "⚠️ N/A",
                "5. Image asset": "⚠️ N/A",
            })
            continue

        excel_name = row["offer_merchant_name"]
        matched_excel.add(excel_name)

        # Check 2 — spelling (exact, but tolerant of quote style & whitespace)
        if same_spelling(creative_name, excel_name):
            spelling = PASS
        elif score >= 0.6:
            spelling = f"❌ Fail (creative: '{creative_name}' vs Excel: '{excel_name}')"
        else:
            spelling = f"⚠️ Review ('{creative_name}' vs '{excel_name}')"

        # Check 3 — discount match (3-state)
        excel_title = row.get("Offer Title", "")
        m = discount_match(offer_text, excel_title)
        if m is True:
            disc = PASS
        elif m is None:
            disc = f"⚠️ Review (creative discount not read; Excel: '{excel_title}')"
        else:
            disc = f"❌ Fail (creative: '{offer_text}' vs Excel: '{excel_title}')"

        # Check 4 — validity date
        excel_date = row["offer_valid_to"]
        date_chk = PASS if excel_date == valid_till \
            else f"❌ Fail (Excel: {excel_date}, creative: {valid_till})"

        # Check 5 — image asset present in Excel
        img_chk = PASS if _image_url_present(row) else "❌ Missing in Excel"

        rows.append({
            "Merchant (creative)": excel_name,
            "1. In Excel": PASS,
            "2. Spelling": spelling,
            "3. Discount": disc,
            "4. Validity date": date_chk,
            "5. Image asset": img_chk,
        })

    # Check 6 — merchants in Excel but NOT in creative
    missing = [n for n in excel_df["offer_merchant_name"] if n not in matched_excel]

    # Check 5/CTA — document-level call-to-action
    cta = PASS if _cta_in_text(cta_text) else "❌ No CTA / branding found in PDF"

    return {"rows": rows, "missing": missing, "cta": cta}


# ─────────────────────────────────────────────────────────────
#  SOCIAL MEDIA image validation — 8 checks
# ─────────────────────────────────────────────────────────────
def validate_social_image(filename: str, width: int, height: int,
                          extracted_text: str, excel_df: pd.DataFrame) -> dict:
    """All 8 social-media checks for a single image."""
    text = str(extracted_text).lower()
    stem = re.sub(r"\.(jpg|jpeg|png)$", "", filename, flags=re.I)

    # Match by filename first, then by extracted content
    row, score = best_excel_match(stem, excel_df)
    content_row, content_score = best_excel_match(text, excel_df)
    if content_score > score:
        row, score = content_row, content_score

    base = {"File": filename, "Resolution": f"{width}x{height}"}

    # Check 8 — unmatched file
    if row is None or score < 0.5:
        base.update({
            "1. Merchant in Excel": "❌ Unmatched — investigate",
            "2. Resolution": _res_check(width, height),
            "3. Discount": "⚠️ N/A",
            "4. Validity date": "⚠️ N/A",
            "5. Spelling": "⚠️ N/A",
            "6. Branding": "✅ BankABC" if _branding_in_text(text) else "❌ Missing",
            "7. CTA": "✅ Smartdeals" if _cta_in_text(text) else "❌ Missing",
        })
        return base

    excel_name = row["offer_merchant_name"]

    # Check 1 — merchant identified & present
    base["1. Merchant in Excel"] = f"✅ {excel_name}"

    # Check 2 — resolution
    base["2. Resolution"] = _res_check(width, height)

    # Check 3 — discount (3-state)
    _excel_title = row.get("Offer Title", "")
    _m = discount_match(text, _excel_title)
    if _m is True:
        base["3. Discount"] = PASS
    elif _m is None:
        base["3. Discount"] = f"⚠️ Review (discount not read; Excel: '{_excel_title}')"
    else:
        base["3. Discount"] = f"❌ Fail (Excel: '{_excel_title}')"

    # Check 4 — validity date
    base["4. Validity date"] = PASS if date_in_text(row["offer_valid_to"], text) \
        else f"❌ Not found (Excel: {row['offer_valid_to']})"

    # Check 5 — spelling (merchant name appears correctly in image text)
    base["5. Spelling"] = PASS if _name_in_image(excel_name, text) \
        else f"⚠️ '{excel_name}' not clearly found in image text"

    # Check 6 — Bank branding
    base["6. Branding"] = "✅ BankABC" if _branding_in_text(text) else "❌ No BankABC branding"

    # Check 7 — CTA
    base["7. CTA"] = "✅ Smartdeals" if _cta_in_text(text) else "❌ No Smartdeals / app CTA"

    return base


def _res_check(width: int, height: int) -> str:
    """Instagram minimum: 1080x1080 square, or portrait 1080x1350."""
    if width >= 1080 and height >= 1080:
        return PASS
    if width >= 1080 and height >= 1350:  # portrait
        return PASS
    return f"❌ Fail (min 1080×1080, got {width}×{height})"


# ─────────────────────────────────────────────────────────────
#  Backwards-compatible wrappers (used by older code paths)
# ─────────────────────────────────────────────────────────────
def validate_pdf_vs_excel(pdf_offers: list, excel_df: pd.DataFrame) -> list:
    return validate_email_pdf(pdf_offers, excel_df)["rows"]


def validate_image_resolution(image, excel_df=None) -> dict:
    from PIL import Image
    from openai_extractor import extract_text_from_image_with_openai
    img = Image.open(image)
    width, height = img.size
    image.seek(0)
    text = extract_text_from_image_with_openai(image) if excel_df is not None else ""
    name = getattr(image, "name", "image.jpg")
    if excel_df is None:
        return {"resolution": f"{width}x{height}", "resolution_check": _res_check(width, height)}
    return validate_social_image(name, width, height, text, excel_df)
