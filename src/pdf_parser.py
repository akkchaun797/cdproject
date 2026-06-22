import fitz  # PyMuPDF

def extract_offers_from_pdf(filepath: str) -> list:
    """
    Opens a PDF using PyMuPDF and extracts offer text
    and validity date from each merchant tile line.
    """
    offers = []

    doc = fitz.open(filepath)

    for page in doc:
        text = page.get_text()
        if not text:
            continue

        for line in text.split('\n'):
            if "Valid till:" not in line:
                continue

            # Split on "Valid till:" to separate offer text and date
            parts = line.split("Valid till:")
            offer_text = parts[0].strip()
            valid_till = parts[1].strip() if len(parts) > 1 else ""

            offers.append({
                "offer_text": offer_text,
                "valid_till": valid_till
            })

    doc.close()
    return offers


def print_offers(offers: list):
    """Prints extracted offers in a readable format."""
    print(f"\nTotal offers found: {len(offers)}\n")
    for i, offer in enumerate(offers, 1):
        print(f"Offer {i}:")
        print(f"  Text       : {offer['offer_text']}")
        print(f"  Valid Till : {offer['valid_till']}")
        print()


if __name__ == "__main__":
    results = extract_offers_from_pdf("cdproject/april_2026_offers.pdf")
    print_offers(results)
    