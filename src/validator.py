import pandas as pd
from datetime import datetime, timedelta


def normalise_date(val):
    if isinstance(val, (int, float)):
        return (datetime(1899, 12, 30) + timedelta(days=int(val))).strftime("%Y-%m-%d")
    if isinstance(val, str):
        for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(val.strip(), fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
    return str(val)


def load_excel(file) -> pd.DataFrame:
    df = pd.read_excel(file)
    df["offer_valid_to"] = df["offer_valid_to"].apply(normalise_date)
    df["offer_merchant_name"] = df["offer_merchant_name"].str.strip().str.lower()
    return df


def validate_pdf_vs_excel(pdf_offers: list, excel_df: pd.DataFrame) -> list:
    results = []

    for offer in pdf_offers:
        offer_text = offer["offer_text"].strip()
        valid_till = offer["valid_till"].strip()

        # Try to match merchant name from Excel in the offer text
        matched_row = None
        matched_name = ""
        for _, row in excel_df.iterrows():
            if row["offer_merchant_name"] in offer["merchant"].lower():
                matched_row = row
                matched_name = row["offer_merchant_name"]
                break

        if matched_row is None:
            results.append({
                "merchant":       offer_text,
                "in_excel":       "❌ Not found",
                "date_match":     "⚠️ N/A",
                "image_url":      "⚠️ N/A",
            })
            continue

        # Date check
        excel_date = matched_row["offer_valid_to"]
        date_match = "✅ Pass" if excel_date == valid_till else f"❌ Fail (Excel: {excel_date}, PDF: {valid_till})"

        # Image URL check
        image_url = matched_row.get("image URLs", "")
        image_check = "✅ Pass" if pd.notna(image_url) and str(image_url).startswith("http") else "❌ Missing"

        results.append({
            "merchant":   matched_name.title(),
            "in_excel":   "✅ Pass",
            "date_match": date_match,
            "image_url":  image_check,
        })

    return results


def validate_image_resolution(image, excel_df=None) -> dict:
    import pytesseract
    from PIL import Image

    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    img = Image.open(image)
    width, height = img.size
    image.seek(0)

    min_size = 1080
    resolution_check = "✅ Pass" if width >= min_size and height >= min_size else f"❌ Fail (minimum {min_size}x{min_size})"

    extracted_text = pytesseract.image_to_string(img).lower()

    merchant_check = "⚠️ N/A"
    date_check = "⚠️ N/A"

    if excel_df is not None:
        merchant_check = "❌ Not found"
        for _, row in excel_df.iterrows():
            if row["offer_merchant_name"] in extracted_text:
                merchant_check = f"✅ Found: {row['offer_merchant_name'].title()}"
                break

        date_check = "❌ Not found"
        for _, row in excel_df.iterrows():
            if row["offer_valid_to"] in extracted_text:
                date_check = f"✅ Found: {row['offer_valid_to']}"
                break

    return {
        "resolution": f"{width}x{height}",
        "resolution_check": resolution_check,
        "merchant_check": merchant_check,
        "date_check": date_check
    }