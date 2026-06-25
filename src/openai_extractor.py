import openai
from dotenv import load_dotenv
import os
import json
import fitz
from PIL import Image
import io
import tempfile
import base64

load_dotenv()
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

PDF_PROMPT = """You are reading a bank marketing PDF creative (email campaign) that lists
MULTIPLE merchant offers. Carefully read the ENTIRE page and extract EVERY merchant
offer visible in English — do not stop after the first one.

Return ONLY valid JSON in exactly this shape:
{
  "merchants": [
    {"merchant": "<name>", "offer": "<the offer / discount text shown for this merchant>", "date": "<validity end date as YYYY-MM-DD>"}
  ],
  "cta": "<any footer call-to-action or Bank ABC / Smartdeals branding text, or empty string if none>"
}

Rules:
- Include one object per merchant tile. A typical creative has 8-12 merchants.
- The "offer" field is REQUIRED. Read the discount/offer line on each tile and copy
  the EXACT text that states the deal, e.g. "Up to 30% off", "15% off on food",
  "From AED 550 net/night", "Buy 1 Get 1 Free". Never leave "offer" empty if any
  discount, price, percentage, or deal wording is visible anywhere in the tile.
- If the discount is shown as a number/percentage badge (e.g. "30%"), include that value.
- Only English content. Convert any visible date to YYYY-MM-DD."""


def image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def extract_pdf_with_openai(pdf_file) -> dict:
    """
    Use GPT-4 Vision (JSON mode) to extract every merchant offer AND the footer CTA.
    Returns {"offers": [...], "cta_text": str, "raw": "<raw model output for debugging>"}.
    """
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    offers = []
    cta_text = ""
    raw_dump = []

    for page in doc:
        pix = page.get_pixmap(dpi=200)
        img_bytes = pix.tobytes("png")
        temp_path = os.path.join(tempfile.gettempdir(), "pdf_page.png")
        with open(temp_path, "wb") as f:
            f.write(img_bytes)

        image_b64 = image_to_base64(temp_path)

        response = client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": PDF_PROMPT},
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/png;base64,{image_b64}", "detail": "high"}},
                ],
            }],
            max_tokens=2000,
        )

        content = response.choices[0].message.content
        raw_dump.append(content)

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            continue

        for m in data.get("merchants", []):
            name = str(m.get("merchant", "")).strip()
            if not name:
                continue
            offers.append({
                "merchant":   name,
                "offer_text": str(m.get("offer", "")).strip(),
                "valid_till": str(m.get("date", "")).strip(),
            })
        if data.get("cta"):
            cta_text += " " + str(data["cta"]).strip()

    doc.close()
    return {"offers": offers, "cta_text": cta_text.strip(), "raw": "\n---\n".join(raw_dump)}


def extract_offers_from_pdf_with_openai(pdf_file) -> list:
    """Backwards-compatible wrapper — returns offers list only."""
    return extract_pdf_with_openai(pdf_file)["offers"]


def extract_text_from_image_with_openai(image_file) -> str:
    """Use GPT-4 Vision to extract text from social media images."""
    img = Image.open(image_file)
    temp_path = os.path.join(tempfile.gettempdir(), "social_img.png")
    img.save(temp_path)

    image_b64 = image_to_base64(temp_path)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "This is a Bank ABC 'Smartdeals' marketing Instagram post. "
                        "Extract ALL visible English text, INCLUDING brand names and logos "
                        "even if they are stylised graphics — in particular always report the "
                        "'smartdeals' logo, any 'Bank ABC' / 'ADIB' branding, and any "
                        "call-to-action or app reference if present. Also include the merchant "
                        "name, the discount/offer text, and any validity date. "
                        "Return everything as one plain lowercase string."
                    )
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_b64}"}
                }
            ]
        }],
        max_tokens=500
    )

    return response.choices[0].message.content.lower()