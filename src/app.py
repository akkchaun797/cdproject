import io
import zipfile
import pandas as pd
import streamlit as st
from PIL import Image

from validator import (
    load_excel,
    validate_email_pdf,
    validate_social_image,
)
from openai_extractor import (
    extract_pdf_with_openai,
    extract_text_from_image_with_openai,
)
from report_export import build_excel_report

IMG_EXTS = (".jpg", ".jpeg", ".png")


# ── Helpers ──────────────────────────────────────────────────
def collect_images(uploaded_files):
    """Yield (filename, file-like) from individual images AND zip archives."""
    images = []
    for f in uploaded_files or []:
        name = f.name.lower()
        if name.endswith(".zip"):
            with zipfile.ZipFile(f) as zf:
                for member in zf.namelist():
                    if member.lower().endswith(IMG_EXTS) and not member.startswith("__MACOSX"):
                        data = zf.read(member)
                        images.append((member.split("/")[-1], io.BytesIO(data)))
        elif name.endswith(IMG_EXTS):
            images.append((f.name, f))
    return images


def style_table(df: pd.DataFrame):
    def colour(v):
        v = str(v)
        if "✅" in v:
            return "background-color:#C6EFCE"
        if "❌" in v:
            return "background-color:#FFC7CE"
        if "⚠️" in v:
            return "background-color:#FFEB9C"
        return ""
    styler = df.style
    # pandas >= 2.1 renamed Styler.applymap -> Styler.map
    return (styler.map(colour) if hasattr(styler, "map") else styler.applymap(colour))


# ── Page config ──────────────────────────────────────────────
st.set_page_config(page_title="BankABC Validation Tool", layout="wide")
st.title("🏦 BankABC Smartdeals — Creative Validation Tool")
st.caption("Upload the monthly Excel and creative files to validate email and social media campaigns.")
st.divider()

# ── Uploads ──────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
with col1:
    st.subheader("📊 Offer Excel")
    excel_file = st.file_uploader("Monthly Excel (source of truth)", type=["xlsx"])
with col2:
    st.subheader("📄 Email PDF Creative")
    pdf_file = st.file_uploader("Email campaign PDF", type=["pdf"])
with col3:
    st.subheader("📸 Social Media Images")
    image_files = st.file_uploader(
        "Instagram images or a .zip", type=["jpg", "jpeg", "png", "zip"],
        accept_multiple_files=True,
    )

st.divider()

# ── Run Validation ───────────────────────────────────────────
if st.button("▶ Run Validation", type="primary"):
    if not excel_file:
        st.error("Please upload the Excel file first.")
        st.stop()
    if not pdf_file and not image_files:
        st.warning("Upload an email PDF and/or social media images to validate.")
        st.stop()

    excel_df = load_excel(excel_file)
    email_df = email_extras = social_df = None

    # ===== REPORT 1 — EMAIL PDF =====
    if pdf_file:
        st.header("📄 Report 1 — Email Campaign (PDF)")
        with st.spinner("Extracting offers from PDF with GPT-4 Vision…"):
            extracted = extract_pdf_with_openai(pdf_file)
        if len(extracted["offers"]) < 2:
            st.warning(f"Only {len(extracted['offers'])} merchant(s) were extracted from the PDF. "
                       "Open the debug panel below to see the raw model output.")
        with st.expander("🔍 Debug — raw GPT extraction"):
            st.write(f"Offers parsed: **{len(extracted['offers'])}**")
            st.json(extracted["offers"])
            st.code(extracted.get("raw", ""), language="json")
        result = validate_email_pdf(extracted["offers"], excel_df, extracted["cta_text"])
        email_df = pd.DataFrame(result["rows"])
        email_extras = {"cta": result["cta"], "missing": result["missing"]}

        passed = sum(1 for _, r in email_df.iterrows() if "❌" not in " ".join(map(str, r.values)))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Merchants in creative", len(email_df))
        c2.metric("Passed ✅", passed)
        c3.metric("Failed ❌", len(email_df) - passed)
        c4.metric("Missing from creative", len(result["missing"]))

        st.dataframe(style_table(email_df), use_container_width=True)
        st.markdown(f"**CTA / branding:** {result['cta']}")
        if result["missing"]:
            st.warning("Merchants in Excel but **not** in the creative: " + ", ".join(result["missing"]))
        else:
            st.success("All Excel merchants appear in the creative.")
        st.divider()

    # ===== REPORT 2 — SOCIAL MEDIA =====
    images = collect_images(image_files)
    if images:
        st.header("📸 Report 2 — Social Media Campaign (Images)")
        rows = []
        prog = st.progress(0.0, text="Validating images…")
        for i, (name, fh) in enumerate(images, 1):
            try:
                fh.seek(0)
                w, h = Image.open(fh).size
                fh.seek(0)
                text = extract_text_from_image_with_openai(fh)
            except Exception as e:
                text, w, h = f"(error: {e})", 0, 0
            rows.append(validate_social_image(name, w, h, text, excel_df))
            prog.progress(i / len(images), text=f"Validated {i}/{len(images)} images")
        prog.empty()

        social_df = pd.DataFrame(rows)
        passed = sum(1 for _, r in social_df.iterrows() if "❌" not in " ".join(map(str, r.values)))
        c1, c2, c3 = st.columns(3)
        c1.metric("Images checked", len(social_df))
        c2.metric("Passed ✅", passed)
        c3.metric("Failed ❌", len(social_df) - passed)
        st.dataframe(style_table(social_df), use_container_width=True)
        st.divider()

    # ===== EXPORT =====
    st.header("⬇ Export Report")
    xlsx = build_excel_report(email_df, email_extras, social_df)
    st.download_button(
        "Download full report (Excel)",
        data=xlsx,
        file_name="bankabc_validation_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )
