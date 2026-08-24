"""SCAMWatch frontend — scam detection interface."""

import streamlit as st
import httpx
import sys
import os

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from backend.config import get_settings

st.set_page_config(page_title="SCAMWatch — SENTINEL", page_icon="🔍", layout="wide")

settings = get_settings()
BACKEND_URL = settings.backend_url

st.title("🔍 SCAMWatch")
st.caption(
    "AI-powered scam detection. Paste any suspicious message or call transcript below."
)

with st.expander("How SCAMWatch Works", expanded=False):
    st.markdown("""
    **SCAMWatch** uses a 5-step AI pipeline to detect scams:

    1. **Rule-based Classification** — Fast pattern matching against 7 Indian scam types
    2. **LLM Deep Analysis** — Groq Llama 3.3 70B analyzes semantic meaning
    3. **Risk Scoring** — Multi-signal engine combining keywords, urgency, authority impersonation
    4. **Intelligence Storage** — High-risk patterns stored for cross-module correlation
    5. **Citizen Alert** — Structured alert with emergency contacts and reporting tools

    **Languages:** English, Hindi, Tamil, Bengali, Telugu
    """)

RISK_COLORS = {
    "LOW": ("🟢", "green", "#d4edda"),
    "MEDIUM": ("🟡", "orange", "#fff3cd"),
    "HIGH": ("🔴", "red", "#f8d7da"),
    "CRITICAL": ("🚨", "darkred", "#f5c6cb"),
}

SAMPLE_TEXTS = {
    "Digital Arrest Scam": """Sir, I am calling from CBI headquarters. Your Aadhaar number has been used 
to open 47 illegal bank accounts involved in money laundering. An arrest warrant has been issued 
in your name. You are under digital arrest. Do not disconnect the call or inform anyone. 
Our officer will contact you on video call. You must transfer Rs 5 lakh as security deposit 
to prove your innocence. This is Supreme Court order 2024.""",
    "Fake KYC SMS": """URGENT: Your SBI account KYC is expired. Your account will be blocked within 
24 hours. Click here to update KYC immediately: http://sbi-kyc-update.xyz/verify 
Enter your account details and OTP to restore access. Ignore this message at your own risk.""",
    "Fake Investment": """Hello! I am from WealthGrow Investment Group. Our members are earning 
40% monthly returns through our exclusive crypto arbitrage program. 
Only 5 slots remaining. Minimum investment Rs 10,000. WhatsApp investment group 
has made 500 members rich already. Guaranteed returns. Join today, limited time offer.""",
}

with st.sidebar:
    st.header("Settings")
    channel = st.selectbox(
        "Input Channel",
        ["unknown", "whatsapp", "sms", "call", "email", "social_media"],
        help="Where did you receive this message?",
    )
    language = st.selectbox(
        "Output Language",
        ["en", "hi", "ta", "bn", "te"],
        format_func=lambda x: {
            "en": "English",
            "hi": "Hindi",
            "ta": "Tamil",
            "bn": "Bengali",
            "te": "Telugu",
        }.get(x, x),
        help="Language for verdict and advisory text",
    )
    st.divider()
    st.header("Sample Scams")
    st.caption("Click to load a sample")
    for name in SAMPLE_TEXTS:
        if st.button(name, use_container_width=True):
            st.session_state["sample_text"] = SAMPLE_TEXTS[name]
    if "sample_text" not in st.session_state:
        st.session_state["sample_text"] = SAMPLE_TEXTS["Digital Arrest Scam"]

default_text = st.session_state.get("sample_text", "")

col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.subheader("Input")
    text_input = st.text_area(
        "Paste suspicious message or call transcript",
        value=default_text,
        height=250,
        placeholder="Paste WhatsApp message, SMS, email, or call transcript here...",
        label_visibility="collapsed",
    )
    st.caption(f"{len(text_input)} characters")

    with st.expander("Voice Scam Detection (Coming Soon)", expanded=False):
        st.markdown("""
        **Speech AI** module for voice-based scam detection:
        - Voice Spoofing Detection — Identify AI-generated voices
        - Call Pattern Analysis — Detect suspicious call flow sequences
        - Number Spoofing Detection — Identify caller ID manipulation
        **Status:** Architecture designed, model training in progress.
        """)

    analyze_clicked = st.button(
        "🔍 Analyze for Scam",
        type="primary",
        use_container_width=True,
        disabled=len(text_input) < 10,
    )

with col2:
    st.subheader("Analysis Result")
    data = st.session_state.get("last_analysis")

    if analyze_clicked and text_input:
        # Prevent double-click by disabling button after first click
        st.session_state["analyzing"] = True
        with st.spinner("Running SENTINEL intelligence pipeline..."):
            try:
                response = httpx.post(
                    f"{BACKEND_URL}/api/scamwatch/analyze",
                    json={"text": text_input, "channel": channel, "language": language},
                    timeout=60.0,
                )
                if response.status_code == 200:
                    data = response.json()
                    st.session_state["last_analysis"] = data
                    st.session_state["analyzing"] = False
                else:
                    st.error(f"Backend error: {response.status_code}")
                    st.session_state["analyzing"] = False
            except httpx.ConnectError:
                st.error(
                    "Cannot connect to SENTINEL backend. Ensure backend is running on port 8000."
                )
                st.session_state["analyzing"] = False
            except httpx.TimeoutException:
                st.error("Analysis timed out. Please try again with shorter text.")
                st.session_state["analyzing"] = False
            except Exception as e:
                st.error(f"Analysis failed: {str(e)}")
                st.session_state["analyzing"] = False

    if data:
        # ── RISK BADGE (prominent) ───────────────────────────────────────────
        risk_level = data["risk_level"]
        emoji, color, bg = RISK_COLORS.get(risk_level, ("⚪", "gray", "#f8f9fa"))
        st.markdown(
            f"""
        <div style="background:{bg}; padding:20px; border-radius:10px; border-left:6px solid {color}; margin-bottom:16px;">
            <h2 style="margin:0; color:#1a1a1a;">{emoji} {risk_level} RISK</h2>
            <p style="margin:4px 0 0; font-size:14px; color:#333333;">Risk Score: {data["risk_score"]:.2f} / 1.00</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

        if data.get("scam_type"):
            st.info(
                f"**Scam Type Detected:** {data['scam_type'].replace('_', ' ').title()}"
            )

        st.markdown(f"**Verdict:** {data['verdict']}")
        st.markdown(f"**Recommended Action:** {data['recommended_action']}")

        if data.get("translated_verdict") and data.get("target_language") != "en":
            lang_names = {"hi": "Hindi", "ta": "Tamil", "bn": "Bengali", "te": "Telugu"}
            lang_name = lang_names.get(data["target_language"], data["target_language"])
            st.info(f"**Translated ({lang_name}):** {data['translated_verdict']}")

        if data.get("similar_patterns_found", 0) > 0:
            st.warning(
                f"{data['similar_patterns_found']} similar scam patterns found in intelligence database"
            )

        # ── CITIZEN ALERT (prominent, right after verdict) ────────────────────
        st.markdown("---")
        st.subheader("🚨 Citizen Alert")

        if st.button(
            "📤 Generate Citizen Alert",
            type="primary",
            use_container_width=True,
            key="gen_alert",
        ):
            with st.spinner("Generating citizen alert..."):
                try:
                    alert_resp = httpx.post(
                        f"{BACKEND_URL}/api/scamwatch/alert/{data['analysis_id']}",
                        timeout=15.0,
                    )
                    if alert_resp.status_code == 200:
                        st.session_state["citizen_alert"] = alert_resp.json()
                        st.session_state["alert_analysis_id"] = data["analysis_id"]
                    else:
                        st.error(f"Alert failed: {alert_resp.status_code}")
                except Exception as e:
                    st.error(f"Alert error: {e}")

        alert = st.session_state.get("citizen_alert")
        alert_aid = st.session_state.get("alert_analysis_id")

        if alert and alert_aid == data["analysis_id"]:
            # ── VERDICT BANNER ────────────────────────────────────────────────
            alert_rl = alert.get("risk_level", "MEDIUM")
            a_emoji, a_color, a_bg = RISK_COLORS.get(
                alert_rl, ("⚪", "gray", "#f8f9fa")
            )
            display_verdict = alert.get("translated_verdict") or alert.get(
                "one_line_verdict", ""
            )
            display_actions = alert.get("translated_actions") or alert.get(
                "recommended_actions", []
            )

            st.markdown(
                f"""
            <div style="background:{a_bg}; padding:20px; border-radius:10px; border-left:6px solid {a_color}; margin:12px 0;">
                <div style="font-size:0.7rem; color:#555555; text-transform:uppercase; letter-spacing:2px;">VERDICT</div>
                <div style="font-size:1.3rem; font-weight:bold; color:#1a1a1a;">{a_emoji} {display_verdict}</div>
            </div>
            """,
                unsafe_allow_html=True,
            )

            # ── QUICK ACTIONS (prominent, side by side) ───────────────────────
            st.markdown("**Recommended Actions:**")
            for action in display_actions[:3]:
                st.checkbox(action, key=f"action_{hash(action)}", disabled=True)

            # ── REPORTING BUTTONS (very prominent) ────────────────────────────
            st.markdown("---")
            st.markdown("### 📋 Take Action Now")

            col_report, col_block = st.columns(2)

            with col_report:
                st.markdown(
                    """
                <div style="background:#1a472a; padding:20px; border-radius:10px; text-align:center; margin-bottom:8px;">
                    <div style="font-size:2rem;">📝</div>
                    <div style="color:white; font-weight:bold; font-size:1.1rem; margin:8px 0;">File Complaint</div>
                    <div style="color:#a7f3d0; font-size:0.85rem;">Report to NCRB Cyber Crime Portal</div>
                </div>
                """,
                    unsafe_allow_html=True,
                )
                st.markdown("[Open cybercrime.gov.in](https://cybercrime.gov.in)")
                st.caption("Paste the report summary below when filing your complaint.")

            with col_block:
                st.markdown(
                    """
                <div style="background:#1a3a5c; padding:20px; border-radius:10px; text-align:center; margin-bottom:8px;">
                    <div style="font-size:2rem;">📱</div>
                    <div style="color:white; font-weight:bold; font-size:1.1rem; margin:8px 0;">Block Scammer</div>
                    <div style="color:#93c5fd; font-size:0.85rem;">Report to Sanchar Saathi / TRAI</div>
                </div>
                """,
                    unsafe_allow_html=True,
                )
                st.markdown("[Open sancharsaathi.gov.in](https://sancharsaathi.gov.in)")
                st.caption("Use Chakshu portal to report fraud calls/SMS.")

            # ── RISK INDICATORS (collapsed, less prominent) ────────────────────
            if data.get("indicators"):
                with st.expander("Risk Indicators (Details)", expanded=False):
                    for ind in data["indicators"]:
                        ind_emoji, ind_color, ind_bg = RISK_COLORS.get(
                            ind["severity"], ("⚪", "gray", "#f8f9fa")
                        )
                        st.markdown(
                            f"""
                        <div style="background:{ind_bg}; padding:8px; border-radius:6px; margin-bottom:6px;">
                            <strong style="color:#1a1a1a;">{ind_emoji} {ind["indicator"]}</strong> <span style="color:#1a1a1a;">— {ind["severity"]}</span><br>
                            <small style="color:#333333;">{ind["explanation"]}</small>
                        </div>
                        """,
                            unsafe_allow_html=True,
                        )

            st.caption(f"Analysis ID: {data['analysis_id']}")
    else:
        st.markdown(
            """
        <div style="background:#f8f9fa; padding:40px; border-radius:8px; text-align:center; color:#6c757d;">
            <h3>Awaiting Input</h3>
            <p>Paste a suspicious message on the left and click Analyze</p>
            <p>Or load a sample from the sidebar</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

st.divider()
st.caption(
    "SENTINEL SCAMWatch — ET AI Hackathon 2.0 | No government agency conducts digital arrests."
)
