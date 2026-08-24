"""WhatsApp Shield — Simulated WhatsApp bot for scam detection.

Citizens paste suspicious messages into a WhatsApp-style chat interface.
The bot responds instantly with risk assessment, emergency contacts,
and reporting guidance. Addresses 'Citizen Fraud Shield (Multi-channel)'
requirement from the hackathon brief.
"""

import streamlit as st
import httpx
import sys
import os

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

st.set_page_config(
    page_title="WhatsApp Shield — SENTINEL", page_icon="💬", layout="wide"
)

API_BASE = "http://localhost:8000"

# ── STYLES ───────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}

.whatsapp-bg {
    background: #0b141a;
    min-height: 500px;
    border-radius: 12px;
    padding: 20px;
    position: relative;
}

.chat-bubble-user {
    background: #005c4b;
    color: white;
    padding: 10px 14px;
    border-radius: 8px 8px 0 8px;
    max-width: 70%;
    margin-left: auto;
    margin-bottom: 8px;
    font-size: 0.9rem;
    line-height: 1.4;
}

.chat-bubble-bot {
    background: #1f2c34;
    color: #e5e7eb;
    padding: 10px 14px;
    border-radius: 8px 8px 8px 0;
    max-width: 70%;
    margin-right: auto;
    margin-bottom: 8px;
    font-size: 0.9rem;
    line-height: 1.4;
}

.chat-time {
    font-size: 0.65rem;
    color: #8696a0;
    text-align: right;
    margin-top: -4px;
    margin-bottom: 8px;
}

.risk-badge-chat {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: bold;
    margin: 4px 0;
}
.risk-CRITICAL { background: #8B0000; color: white; }
.risk-HIGH     { background: #B84900; color: white; }
.risk-MEDIUM   { background: #8B7000; color: white; }
.risk-LOW      { background: #1B5E20; color: white; }
</style>
""",
    unsafe_allow_html=True,
)

# ── HEADER ───────────────────────────────────────────────────────────────────
st.markdown(
    """
<div style="background:linear-gradient(135deg,#060B14 0%,#0d1b2a 60%,#060B14 100%);
            border:1px solid #00aaff22;border-radius:12px;padding:24px 28px;margin-bottom:20px;">
    <h1 style="color:#ffffff;margin:0;font-size:1.8rem;letter-spacing:2px;font-weight:900">
        WhatsApp Shield
    </h1>
    <p style="color:#00aaff;margin:4px 0 0;font-size:0.9rem;letter-spacing:1px">
        AI-powered scam detection via simulated WhatsApp bot
    </p>
    <p style="color:#6b7280;margin:4px 0 0;font-size:0.75rem">
        Addresses 'Citizen Fraud Shield (Multi-channel)' requirement
    </p>
</div>
""",
    unsafe_allow_html=True,
)

# ── HOW IT WORKS ─────────────────────────────────────────────────────────────
with st.expander("How WhatsApp Shield Works", expanded=False):
    st.markdown("""
    **WhatsApp Shield** simulates a WhatsApp bot that citizens can interact with:

    1. **Paste Suspicious Message** — Copy the suspicious WhatsApp message, SMS, or email
    2. **Get Instant Verdict** — AI analyzes the message and returns risk assessment
    3. **Receive Actionable Advice** — Specific steps to protect yourself
    4. **Report to Authorities** — Links to cybercrime.gov.in and sancharsaathi.gov.in

    **This is a demo simulation.** In production, this would be a WhatsApp Business API bot
    accessible via a phone number, integrated with the SCAMWatch backend.
    """)

# ── SAMPLE MESSAGES ──────────────────────────────────────────────────────────
SAMPLE_MESSAGES = {
    "Digital Arrest": "Sir, I am calling from CBI headquarters. Your Aadhaar number has been used to open 47 illegal bank accounts. An arrest warrant has been issued. Do not disconnect or tell anyone. Transfer Rs 5 lakh as security deposit immediately.",
    "Fake KYC": "URGENT: Your SBI account KYC is expired. Your account will be blocked within 24 hours. Click here: http://sbi-kyc-update.xyz/verify Enter your account details and OTP.",
    "Fake Investment": "Hello! I am from WealthGrow Investment Group. Our members are earning 40% monthly returns. Only 5 slots remaining. Minimum investment Rs 10,000. Guaranteed returns. Join today!",
    "Lottery Scam": "Congratulations! You have won Rs 25 lakh in KBC Lucky Draw. To claim your prize, pay processing fee of Rs 5,000 to account 1234567890. This offer expires in 2 hours.",
}

# ── CHAT INTERFACE ───────────────────────────────────────────────────────────
st.markdown("### Chat")

# Initialize chat history
if "chat_messages" not in st.session_state:
    st.session_state["chat_messages"] = [
        {
            "role": "bot",
            "text": "Hello! I am SENTINEL Shield Bot. Paste any suspicious message and I will analyze it for scams. Stay safe!",
            "time": "Now",
        }
    ]

# Display chat history
chat_container = st.container()
with chat_container:
    for msg in st.session_state["chat_messages"]:
        if msg["role"] == "user":
            st.markdown(
                f"""
            <div style="display:flex;justify-content:flex-end;margin-bottom:4px;">
                <div class="chat-bubble-user">{msg["text"]}</div>
            </div>
            <div class="chat-time">{msg.get("time", "")}</div>
            """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""
            <div style="display:flex;justify-content:flex-start;margin-bottom:4px;">
                <div class="chat-bubble-bot">{msg["text"]}</div>
            </div>
            <div class="chat-time">{msg.get("time", "")}</div>
            """,
                unsafe_allow_html=True,
            )

# ── INPUT AREA ───────────────────────────────────────────────────────────────
st.markdown("---")

# Sample message buttons
st.markdown("**Try a sample scam message:**")
sample_cols = st.columns(4)
for i, (name, msg) in enumerate(SAMPLE_MESSAGES.items()):
    with sample_cols[i]:
        if st.button(name, use_container_width=True, key=f"sample_{i}"):
            st.session_state["chat_input"] = msg

# Text input
user_input = st.text_input(
    "Type or paste a suspicious message:",
    value="",
    placeholder="Paste a suspicious WhatsApp message, SMS, or email here...",
    key="chat_input",
)

col_send, col_clear = st.columns([3, 1])
with col_send:
    send_clicked = st.button("Send Message", type="primary", use_container_width=True)
with col_clear:
    if st.button("Clear Chat", use_container_width=True):
        st.session_state["chat_messages"] = [
            {
                "role": "bot",
                "text": "Chat cleared. Paste a new suspicious message to analyze.",
                "time": "Now",
            }
        ]
        st.rerun()

# ── PROCESS MESSAGE ──────────────────────────────────────────────────────────
if send_clicked and user_input:
    # Add user message to chat
    st.session_state["chat_messages"].append(
        {"role": "user", "text": user_input, "time": "Now"}
    )

    # Analyze via SCAMWatch API
    with st.spinner("Analyzing message..."):
        try:
            response = httpx.post(
                f"{API_BASE}/api/scamwatch/analyze",
                json={"text": user_input, "channel": "whatsapp", "language": "en"},
                timeout=60.0,
            )

            if response.status_code == 200:
                data = response.json()
                risk_level = data["risk_level"]
                scam_type = data.get("scam_type", "unknown").replace("_", " ").title()

                # Build bot response
                if risk_level in ["CRITICAL", "HIGH"]:
                    bot_response = f"🚨 **SCAM DETECTED** — {risk_level} RISK\n\n"
                    bot_response += f"**Type:** {scam_type}\n"
                    bot_response += f"**Risk Score:** {data['risk_score']:.0%}\n\n"
                    bot_response += f"**Verdict:** {data['verdict']}\n\n"
                    bot_response += "**What to do:**\n"
                    bot_response += "1. Do NOT transfer any money\n"
                    bot_response += "2. Do NOT share OTP or PIN\n"
                    bot_response += "3. Block the sender immediately\n"
                    bot_response += "4. Report to Cyber Crime: 1930\n"
                    bot_response += "5. File complaint: cybercrime.gov.in\n\n"
                    bot_response += "⚠️ No government agency conducts arrests via video call or asks for money transfer."
                elif risk_level == "MEDIUM":
                    bot_response = f"⚠️ **SUSPICIOUS** — {risk_level} RISK\n\n"
                    bot_response += f"**Type:** {scam_type}\n"
                    bot_response += f"**Risk Score:** {data['risk_score']:.0%}\n\n"
                    bot_response += f"**Verdict:** {data['verdict']}\n\n"
                    bot_response += "**Recommendation:** Exercise caution. Verify independently before taking any action."
                else:
                    bot_response = "✅ **LOW RISK**\n\n"
                    bot_response += f"**Verdict:** {data['verdict']}\n\n"
                    bot_response += "This message appears to be low risk, but always verify independently."

                # Add bot response to chat
                st.session_state["chat_messages"].append(
                    {"role": "bot", "text": bot_response, "time": "Now"}
                )

            else:
                st.session_state["chat_messages"].append(
                    {
                        "role": "bot",
                        "text": "Sorry, I couldn't analyze this message. Please try again.",
                        "time": "Now",
                    }
                )

        except httpx.ConnectError:
            st.session_state["chat_messages"].append(
                {
                    "role": "bot",
                    "text": "Cannot connect to SENTINEL backend. Ensure backend is running on port 8000.",
                    "time": "Now",
                }
            )
        except Exception as e:
            st.session_state["chat_messages"].append(
                {
                    "role": "bot",
                    "text": f"Error analyzing message: {str(e)}",
                    "time": "Now",
                }
            )

    st.rerun()

# ── FOOTER ───────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "This is a demo simulation of WhatsApp Shield. In production, this would be a WhatsApp Business API bot accessible via a phone number."
)
st.caption("SENTINEL — AI for Digital Public Safety | ET AI Hackathon 2.0")
