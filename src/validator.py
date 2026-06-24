import re  # noqa
import pandas as pd
from datetime import datetime, timedelta
from difflib import SequenceMatcher

PASS = "✅ Pass"


# ─────────────────────────────────────────────────────────────
#  Normalisation helpers
# ─────────────────────────────────────────────────────────────
def normalise_date(val):
    """Excel serial integers OR string dates → YYYY-MM-DD."""
    if isinstance(val, (int, float)):
        return (datetime(1899, 12, 30) + timedelta(days=int(val))).strftime("%Y-%m-%d")
    if isinstance(val, str):
        s = val.strip()
        for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
    return str(val)


def normalise_name(s) -> str:
    """Lowercase, strip punctuation, collapse whitespace — for fuzzy matching."""
    s = str(s).lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


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
def discount_signature(text: str) -> set:
    """Extract comparable discount tokens: percentages, money amounts, integers."""
    t = str(text).lower().replace(",", "")
    tokens = set()
    tokens |= {p.replace(" ", "") for p in re.findall(r"\d+\s*%", t)}          # 20%
    tokens |= {m.replace(" ", "") for m in re.findall(r"(?:\$|aed)\s*\d+", t)}  # $50 / aed550
    bare = re.findall(r"(?<![%$\d])\b\d+\b", t)                                # plain integers
    tokens |= {f"#{n}" for n in bare}
    return tokens


def discount_match(creative_text: str, excel_title: str) -> bool:
    """Numeric-token equality first; fall back to fuzzy text similarity."""
    c_sig, e_sig = discount_signature(creative_text), discount_signature(excel_title)
    if e_sig:
        return e_sig.issubset(c_sig)
    return fuzzy_ratio(creative_text, excel_title) >= 0.6


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

        # Check 2 — spelling (exact, case-insensitive)
        if creative_name.lower() == excel_name.lower():
            spelling = PASS
        elif score >= 0.6:
            spelling = f"❌ Fail (creative: '{creative_name}' vs Excel: '{excel_name}')"
        else:
            spelling = f"⚠️ Review ('{creative_name}' vs '{excel_name}')"

        # Check 3 — discount match
        excel_title = row.get("Offer Title", "")
        disc = PASS if discount_match(offer_text, excel_title) \
            else f"❌ Fail (creative: '{offer_text}' vs Excel: '{excel_title}')"

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

    # Check 3 — discount
    base["3. Discount"] = PASS if discount_match(text, row.get("Offer Title", "")) \
        else f"❌ Fail (Excel: '{row.get('Offer Title', '')}')"

    # Check 4 — validity date
    base["4. Validity date"] = PASS if row["offer_valid_to"].lower() in text \
        else f"❌ Not found (Excel: {row['offer_valid_to']})"

    # Check 5 — spelling (merchant name must appear correctly in image text)
    base["5. Spelling"] = PASS if normalise_name(excel_name) in normalise_name(text) \
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
