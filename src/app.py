import io
import html
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


# ─────────────────────────────────────────────────────────────
#  Styling
# ─────────────────────────────────────────────────────────────
def load_css():
    st.markdown("""
    <style>
      .block-container { padding-top: 2rem; max-width: 1250px; }
      #MainMenu, footer { visibility: hidden; }

      /* Hero banner */
      .hero {
        background: linear-gradient(120deg, #0b2e4f 0%, #14507e 55%, #1d6fa5 100%);
        border-radius: 16px; padding: 26px 32px; margin-bottom: 22px;
        box-shadow: 0 6px 24px rgba(0,0,0,.35);
      }
      .hero h1 { color:#fff; font-size:1.9rem; font-weight:800; margin:0; letter-spacing:-.5px; }
      .hero p  { color:#cfe3f3; margin:.35rem 0 0; font-size:1rem; }
      .hero .pill-row { margin-top:14px; }
      .hero .tag {
        display:inline-block; background:rgba(255,255,255,.14); color:#eaf4fc;
        border:1px solid rgba(255,255,255,.22); border-radius:999px;
        padding:4px 12px; font-size:.78rem; margin-right:8px; font-weight:600;
      }

      /* Section title */
      .sec { display:flex; align-items:center; gap:10px; margin:6px 0 14px; }
      .sec .ic { font-size:1.4rem; }
      .sec h2  { font-size:1.3rem; font-weight:700; margin:0; color:inherit; }

      /* Metric cards */
      .metric-row { display:flex; gap:14px; flex-wrap:wrap; margin:6px 0 18px; }
      .metric {
        flex:1; min-width:150px; background:rgba(255,255,255,.04);
        border:1px solid rgba(255,255,255,.10); border-left:5px solid #14507e;
        border-radius:12px; padding:16px 18px;
      }
      .metric .m-val { font-size:2rem; font-weight:800; line-height:1; }
      .metric .m-lab { font-size:.82rem; opacity:.75; margin-top:6px; text-transform:uppercase; letter-spacing:.4px; }
      .metric.good  { border-left-color:#2e7d32; } .metric.good  .m-val{ color:#4caf50; }
      .metric.bad   { border-left-color:#c62828; } .metric.bad   .m-val{ color:#ef5350; }
      .metric.warn  { border-left-color:#f9a825; } .metric.warn  .m-val{ color:#ffca28; }

      /* Status banner */
      .banner { border-radius:12px; padding:14px 18px; font-weight:600; margin:4px 0 16px; }
      .banner.ok   { background:rgba(46,125,50,.16);  border:1px solid #2e7d32; color:#7fd486; }
      .banner.err  { background:rgba(198,40,40,.16);   border:1px solid #c62828; color:#ff8a80; }
      .banner.info { background:rgba(20,80,126,.18);   border:1px solid #14507e; color:#9fcdee; }

      /* Report table */
      .tbl-wrap { overflow-x:auto; border-radius:12px; border:1px solid rgba(255,255,255,.10); }
      table.vtbl { width:100%; border-collapse:collapse; font-size:.9rem; }
      table.vtbl th {
        background:#0b2e4f; color:#eaf4fc; text-align:left; padding:11px 14px;
        font-weight:700; font-size:.82rem; text-transform:uppercase; letter-spacing:.3px;
        position:sticky; top:0;
      }
      table.vtbl td { padding:10px 14px; border-top:1px solid rgba(255,255,255,.07); vertical-align:middle; }
      table.vtbl tr:nth-child(even) td { background:rgba(255,255,255,.025); }
      .merch { font-weight:700; }
      .pill {
        display:inline-block; border-radius:999px; padding:3px 10px;
        font-size:.8rem; font-weight:600; line-height:1.35; white-space:normal;
      }
      .pill.pass { background:rgba(46,125,50,.22); color:#7fd486; border:1px solid #2e7d32; }
      .pill.fail { background:rgba(198,40,40,.20); color:#ff8a80; border:1px solid #c62828; }
      .pill.warn { background:rgba(249,168,37,.18); color:#ffca28; border:1px solid #f9a825; }

      .legend { font-size:.8rem; opacity:.8; margin:2px 0 10px; }
      .legend span { margin-right:14px; }
    </style>
    """, unsafe_allow_html=True)


def section(icon, title):
    st.markdown(f'<div class="sec"><span class="ic">{icon}</span><h2>{html.escape(title)}</h2></div>',
                unsafe_allow_html=True)


def metrics_row(cards):
    st.markdown('<div class="metric-row">' + "".join(cards) + '</div>', unsafe_allow_html=True)


def metric_card(label, value, kind="neutral"):
    return (f'<div class="metric {kind}"><div class="m-val">{value}</div>'
            f'<div class="m-lab">{html.escape(label)}</div></div>')


def _pill(value):
    v = str(value)
    esc = html.escape(v)
    if "✅" in v:
        return f'<span class="pill pass">{esc}</span>'
    if "❌" in v:
        return f'<span class="pill fail">{esc}</span>'
    if "⚠️" in v:
        return f'<span class="pill warn">{esc}</span>'
    return f'<span class="merch">{esc}</span>'


def render_table(df: pd.DataFrame):
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in df.columns)
    body = ""
    for _, row in df.iterrows():
        cells = "".join(f"<td>{_pill(row[c])}</td>" for c in df.columns)
        body += f"<tr>{cells}</tr>"
    st.markdown(
        f'<div class="tbl-wrap"><table class="vtbl"><thead><tr>{head}</tr></thead>'
        f'<tbody>{body}</tbody></table></div>', unsafe_allow_html=True)
    st.markdown('<div class="legend"><span>🟢 Pass</span><span>🔴 Fail</span>'
                '<span>🟡 Needs review</span></div>', unsafe_allow_html=True)


def status_banner(failed, total, ok_msg, err_msg):
    if total == 0:
        return
    if failed == 0:
        st.markdown(f'<div class="banner ok">✅ {html.escape(ok_msg)}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="banner err">⚠️ {html.escape(err_msg)}</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
#  Helpers (logic)
# ─────────────────────────────────────────────────────────────
def collect_images(uploaded_files):
    images = []
    for f in uploaded_files or []:
        name = f.name.lower()
        if name.endswith(".zip"):
            with zipfile.ZipFile(f) as zf:
                for member in zf.namelist():
                    if member.lower().endswith(IMG_EXTS) and not member.startswith("__MACOSX"):
                        images.append((member.split("/")[-1], io.BytesIO(zf.read(member))))
        elif name.endswith(IMG_EXTS):
            images.append((f.name, f))
    return images


def row_passed(row):
    return "❌" not in " ".join(map(str, row.values))


# ─────────────────────────────────────────────────────────────
#  Page
# ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="BankABC Validation Tool", page_icon="🏦", layout="wide")
load_css()

st.markdown("""
<div class="hero">
  <h1>🏦 BankABC Smartdeals — Creative Validation Tool</h1>
  <p>Validate monthly email & social-media creatives against the source offer Excel in under 5 minutes.</p>
  <div class="pill-row">
    <span class="tag">Email PDF</span>
    <span class="tag">Social Media</span>
    <span class="tag">GPT-4 Vision</span>
    <span class="tag">Pass / Fail report</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Sidebar: instructions + legend ───────────────────────────
with st.sidebar:
    st.markdown("### How to use")
    st.markdown(
        "1. Upload the **monthly Excel** (source of truth).\n"
        "2. Upload the **email PDF** and/or **social images** (individual files or a `.zip`).\n"
        "3. Click **Run Validation**.\n"
        "4. Review both reports and **download** the Excel summary."
    )
    st.divider()
    st.markdown("### Legend")
    st.markdown("🟢 **Pass** — check matched\n\n🔴 **Fail** — mismatch found\n\n🟡 **Review** — needs a human look")

# ── Uploads ──────────────────────────────────────────────────
section("📥", "1 · Upload files")
col1, col2, col3 = st.columns(3)
with col1:
    with st.container(border=True):
        st.markdown("**📊 Offer Excel**")
        st.caption("Monthly source of truth (.xlsx)")
        excel_file = st.file_uploader("Excel", type=["xlsx"], label_visibility="collapsed")
with col2:
    with st.container(border=True):
        st.markdown("**📄 Email PDF Creative**")
        st.caption("All merchants on one PDF")
        pdf_file = st.file_uploader("PDF", type=["pdf"], label_visibility="collapsed")
with col3:
    with st.container(border=True):
        st.markdown("**📸 Social Media Images**")
        st.caption("JPG / PNG per merchant, or a .zip")
        image_files = st.file_uploader("Images", type=["jpg", "jpeg", "png", "zip"],
                                       accept_multiple_files=True, label_visibility="collapsed")

st.write("")
run = st.button("▶  Run Validation", type="primary", use_container_width=True)

# ── Run ──────────────────────────────────────────────────────
if run:
    if not excel_file:
        st.error("Please upload the Excel file first.")
        st.stop()
    if not pdf_file and not image_files:
        st.warning("Upload an email PDF and/or social media images to validate.")
        st.stop()

    excel_df = load_excel(excel_file)
    email_df = email_extras = social_df = None
    st.divider()

    # ===== REPORT 1 — EMAIL PDF =====
    if pdf_file:
        section("📄", "Report 1 — Email Campaign (PDF)")
        with st.spinner("Reading the PDF with GPT-4 Vision…"):
            extracted = extract_pdf_with_openai(pdf_file)

        if len(extracted["offers"]) < 2:
            st.markdown(
                f'<div class="banner info">ℹ️ Only {len(extracted["offers"])} merchant(s) were '
                "extracted — if you expected more, check you uploaded the multi-merchant email PDF "
                "(not a single-merchant creative). See the debug panel below.</div>",
                unsafe_allow_html=True)
        with st.expander("🔍 Debug — raw GPT extraction"):
            st.write(f"Offers parsed: **{len(extracted['offers'])}**")
            st.json(extracted["offers"])
            st.code(extracted.get("raw", ""), language="json")

        result = validate_email_pdf(extracted["offers"], excel_df, extracted["cta_text"])
        email_df = pd.DataFrame(result["rows"])
        email_extras = {"cta": result["cta"], "missing": result["missing"]}

        passed = sum(1 for _, r in email_df.iterrows() if row_passed(r))
        failed = len(email_df) - passed
        cta_ok = "✅" in result["cta"]

        metrics_row([
            metric_card("Merchants in creative", len(email_df)),
            metric_card("Passed", passed, "good"),
            metric_card("Failed", failed, "bad" if failed else "neutral"),
            metric_card("Missing from creative", len(result["missing"]),
                        "warn" if result["missing"] else "neutral"),
        ])
        status_banner(failed, len(email_df),
                      "All extracted merchants passed every check.",
                      f"{failed} merchant(s) failed one or more checks — see red cells below.")
        render_table(email_df)

        cta_cls = "ok" if cta_ok else "err"
        st.markdown(f'<div class="banner {cta_cls}">CTA / branding: {html.escape(result["cta"])}</div>',
                    unsafe_allow_html=True)
        if result["missing"]:
            st.markdown('<div class="banner warn" style="background:rgba(249,168,37,.16);'
                        'border:1px solid #f9a825;color:#ffca28;">Merchants in Excel but not in the '
                        'creative: ' + html.escape(", ".join(result["missing"])) + '</div>',
                        unsafe_allow_html=True)
        st.divider()

    # ===== REPORT 2 — SOCIAL MEDIA =====
    images = collect_images(image_files)
    if images:
        section("📸", "Report 2 — Social Media Campaign (Images)")
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
        passed = sum(1 for _, r in social_df.iterrows() if row_passed(r))
        failed = len(social_df) - passed
        metrics_row([
            metric_card("Images checked", len(social_df)),
            metric_card("Passed", passed, "good"),
            metric_card("Failed", failed, "bad" if failed else "neutral"),
        ])
        status_banner(failed, len(social_df),
                      "All images passed every check.",
                      f"{failed} image(s) need attention — see red cells below.")
        render_table(social_df)
        st.divider()

    # ===== EXPORT =====
    section("⬇️", "Export")
    xlsx = build_excel_report(email_df, email_extras, social_df)
    st.download_button(
        "Download full report (Excel)",
        data=xlsx,
        file_name="bankabc_validation_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True,
    )
