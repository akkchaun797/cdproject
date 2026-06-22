import streamlit as st
import pandas as pd
import fitz
from validator import load_excel, validate_pdf_vs_excel, validate_image_resolution

# ── PDF parser ───────────────────────────────────────────────
def parse_pdf(file) -> list:
    doc = fitz.open(stream=file.read(), filetype="pdf")
    offers = []
    for page in doc:
        lines = [l.strip() for l in page.get_text().split('\n') if l.strip()]
        for i, line in enumerate(lines):
            if "Valid till:" not in line:
                continue
            valid_till = line.replace("Valid till:", "").strip()
            merchant = lines[i - 2] if i >= 2 else ""
            offer_text = lines[i - 1] if i >= 1 else ""
            offers.append({
                "merchant":   merchant,
                "offer_text": offer_text,
                "valid_till": valid_till
            })
    doc.close()
    return offers


# ── Page config ──────────────────────────────────────────────
st.set_page_config(page_title="BankABC Validation Tool", layout="wide")

st.title("🏦 BankABC Smart Offers — Validation Tool")
st.caption("Upload the monthly Excel and creative files to run validation checks.")
st.divider()

# ── Uploads ──────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("📊 Offer Excel")
    excel_file = st.file_uploader("Upload monthly Excel", type=["xlsx"])

with col2:
    st.subheader("📄 Email PDF Creative")
    pdf_file = st.file_uploader("Upload email PDF", type=["pdf"])

with col3:
    st.subheader("📸 Social Media Images")
    image_files = st.file_uploader("Upload Instagram images", type=["jpg", "jpeg", "png"],
                                    accept_multiple_files=True)

st.divider()

# ── Run Validation ───────────────────────────────────────────
if st.button("▶ Run Validation", type="primary"):

    if not excel_file:
        st.error("Please upload the Excel file first.")
    else:
        excel_df = load_excel(excel_file)

        # PDF Validation Report
        if pdf_file:
            st.subheader("📄 Email PDF Validation Report")
            pdf_offers = parse_pdf(pdf_file)
            results = validate_pdf_vs_excel(pdf_offers, excel_df)
            df_results = pd.DataFrame(results)
            st.dataframe(df_results, use_container_width=True)

            total = len(results)
            passed = sum(1 for r in results if "❌" not in str(list(r.values())))
            failed = total - passed

            c1, c2, c3 = st.columns(3)
            c1.metric("Total Merchants", total)
            c2.metric("Passed ✅", passed)
            c3.metric("Failed ❌", failed)

        st.divider()

        # Social Media Image Report
        if image_files:
            st.subheader("📸 Social Media Image Validation Report")
            img_results = []
            for img in image_files:
                res = validate_image_resolution(img)
                img_results.append({
                    "file":             img.name,
                    "resolution":       res["resolution"],
                    "resolution_check": res["check"]
                })
            st.dataframe(pd.DataFrame(img_results), use_container_width=True)

        if not pdf_file and not image_files:
            st.warning("Please upload a PDF or images to validate.")