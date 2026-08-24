"""CURRENCYGuard frontend — currency authentication interface."""

import streamlit as st
import httpx
import sys
import os

# Add project root to Python path for backend imports
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

st.set_page_config(page_title="CURRENCYGuard — SENTINEL", page_icon="💵", layout="wide")

BACKEND_URL = "http://localhost:8000"

VERDICT_CONFIG = {
    "GENUINE": ("✅", "#d4edda", "#155724", "Note appears authentic"),
    "SUSPECT": ("⚠️", "#fff3cd", "#856404", "Note requires further verification"),
    "COUNTERFEIT": ("🚫", "#f8d7da", "#721c24", "Note flagged as likely counterfeit"),
    "INCONCLUSIVE": ("❓", "#e2e3e5", "#383d41", "Insufficient data for determination"),
}

st.title("💵 CURRENCYGuard")
st.caption(
    "AI-powered Indian currency authentication. Upload a note image for instant verification."
)

# How It Works section
with st.expander("How CURRENCYGuard Works", expanded=False):
    st.markdown("""
    **CURRENCYGuard** uses computer vision to authenticate Indian currency notes:

    1. **Image Quality Gate** — Rejects blurry, dark, or low-resolution images
    2. **Play Money Detection** — Identifies play notes, monopoly money, and obvious fakes
    3. **Aspect Ratio Check** — Verifies dimensions match RBI standards per denomination
    4. **Color Distribution** — Analyzes HSV saturation patterns for genuine ink
    5. **Security Thread** — Detects the windowed security thread ~1/3 from left edge
    6. **Serial Number Zone** — Checks edge density in text regions
    7. **Watermark Region** — Verifies Gandhi portrait area intensity variation
    8. **Print Sharpness** — Laplacian variance for genuine vs photocopy detection

    **Supported Denominations:** ₹50, ₹100, ₹200, ₹500, ₹2000

    **Verdicts:** GENUINE, SUSPECT, COUNTERFEIT, INCONCLUSIVE
    """)

# Deepfake Detection placeholder
with st.expander("Deepfake Detection (Coming Soon)", expanded=False):
    st.markdown("""
    **Deepfake Detection** module for identifying manipulated currency images:

    - **Image Authenticity Analysis** — Detect digitally altered or合成 currency images
    - **Metadata Forensics** — Analyze EXIF data for signs of manipulation
    - **Neural Network Detection** — CNN-based classifier for deepfake currency images
    - **UV Feature Simulation** — Simulate UV light analysis for security features

    This module addresses the growing threat of AI-generated counterfeit currency images
    used in online fraud and digital payment scams.

    **Status:** Architecture designed, model training in progress.
    """)

with st.sidebar:
    st.header("⚙️ Settings")
    denomination = st.selectbox(
        "Denomination (optional)",
        ["unknown", "50", "100", "200", "500", "2000"],
        help="Select denomination or let AI detect automatically",
    )
    st.divider()
    st.info("""**How to get best results:**
- Photograph note on flat, dark surface
- Ensure good lighting
- Capture entire note in frame
- Avoid shadows and glare
- Use at least 1MP camera""")
    st.divider()
    st.caption("Supported: ₹50, ₹100, ₹200, ₹500, ₹2000")

col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.subheader("📤 Upload Note Image")
    uploaded_file = st.file_uploader(
        "Upload currency note image",
        type=["jpg", "jpeg", "png"],
        help="JPG or PNG, max 10MB",
        label_visibility="collapsed",
    )

    if uploaded_file:
        st.image(uploaded_file, caption="Uploaded note", use_column_width=True)
        st.caption(f"File: {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")

    analyze_clicked = st.button(
        "🔍 Authenticate Note",
        type="primary",
        use_container_width=True,
        disabled=uploaded_file is None,
    )

with col2:
    st.subheader("📊 Authentication Result")

    if analyze_clicked and uploaded_file:
        with st.spinner("Running SENTINEL vision pipeline..."):
            try:
                uploaded_file.seek(0)
                response = httpx.post(
                    f"{BACKEND_URL}/api/currencyguard/analyze",
                    files={
                        "file": (
                            uploaded_file.name,
                            uploaded_file.read(),
                            uploaded_file.type,
                        )
                    },
                    data={"denomination": denomination},
                    timeout=60.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    verdict = data["verdict"]
                    emoji, bg, text_color, subtitle = VERDICT_CONFIG.get(
                        verdict, ("❓", "#e2e3e5", "#383d41", "")
                    )

                    st.markdown(
                        f"""
                    <div style="background:{bg}; padding:20px; border-radius:10px; margin-bottom:16px;">
                        <h2 style="margin:0; color:{text_color};">{emoji} {verdict}</h2>
                        <p style="margin:4px 0; color:{text_color};">{subtitle}</p>
                        <p style="margin:4px 0; color:{text_color}; font-size:13px;">
                            Confidence: {data["confidence"]:.1%} | 
                            Denomination: ₹{data.get("denomination", "Unknown")} |
                            ID: {data["analysis_id"]}
                        </p>
                    </div>
                    """,
                        unsafe_allow_html=True,
                    )

                    st.markdown(f"**AI Reasoning:** {data['ai_reasoning']}")
                    if data.get("risk_summary") and data["risk_summary"] != "NONE":
                        st.warning(f"⚠️ Key Concern: {data['risk_summary']}")

                    st.subheader("🔬 Security Feature Checks")
                    for check in data.get("feature_checks", []):
                        passed = check["passed"]
                        icon = "✅" if passed else "❌"
                        conf = check["confidence"]
                        with st.expander(
                            f"{icon} {check['feature_name']} — {conf:.1%} confidence",
                            expanded=not passed,
                        ):
                            st.write(check["details"])

                    if data.get("report_available"):
                        st.divider()
                        report_resp = httpx.get(
                            f"{BACKEND_URL}/api/currencyguard/report/{data['analysis_id']}",
                            timeout=30.0,
                        )
                        if report_resp.status_code == 200:
                            st.download_button(
                                label="📄 Download Authenticity Report (PDF)",
                                data=report_resp.content,
                                file_name=f"SENTINEL_Currency_{data['analysis_id']}.pdf",
                                mime="application/pdf",
                                use_container_width=True,
                            )

                else:
                    st.error(f"Backend error: {response.status_code} — {response.text}")

            except httpx.ConnectError:
                st.error(
                    "Cannot connect to SENTINEL backend. Ensure backend is running on port 8000."
                )
            except httpx.TimeoutException:
                st.error(
                    "Analysis timed out. The image may be too large or complex. Try a smaller image."
                )
            except Exception as e:
                st.error(f"Analysis failed: {str(e)}")
    else:
        st.markdown(
            """
        <div style="background:#f8f9fa; padding:40px; border-radius:8px; 
                    text-align:center; color:#6c757d;">
            <h3>Awaiting Upload</h3>
            <p>Upload a currency note image on the left</p>
            <p>Supports ₹50 · ₹100 · ₹200 · ₹500 · ₹2000</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

st.divider()
st.caption(
    "🛡️ SENTINEL CURRENCYGuard — ET AI Hackathon 2.0 | "
    "For preliminary screening only. Not legal evidence."
)
