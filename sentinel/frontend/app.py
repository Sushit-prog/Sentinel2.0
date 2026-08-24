"""SENTINEL investigation client.

A thin read/write client over the API. Deliberately minimal: the product
is the backend; this exists to demonstrate the investigation workflow
(submit -> verdict with evidence -> citizen alert -> audit trail).
"""

import json
import os

import httpx
import streamlit as st

API_BASE = os.environ.get("SENTINEL_API", "http://localhost:8000")

st.set_page_config(page_title="SENTINEL", page_icon="🛡️", layout="wide")
st.title("SENTINEL — Evidence-Grounded Fraud Intelligence")


def api(method: str, path: str, **kwargs):
    return httpx.request(method, f"{API_BASE}{path}", timeout=120.0, **kwargs)


with st.sidebar:
    st.header("New analysis")
    text = st.text_area(
        "Suspicious message",
        height=160,
        placeholder="Paste the SMS / WhatsApp / call transcript...",
    )
    channel = st.selectbox("Channel", ["sms", "whatsapp", "call", "email", "unknown"])
    language = st.selectbox("Language", ["en", "hi", "ta", "bn", "te"])
    analyze = st.button("Analyze", type="primary", use_container_width=True)

if analyze:
    if len(text.strip()) < 5:
        st.error("Message too short.")
    else:
        with st.spinner("Running evidence-grounded pipeline..."):
            resp = api(
                "POST",
                "/api/scamwatch/analyze",
                json={"text": text, "channel": channel, "language": language},
            )
        if resp.status_code != 200:
            st.error(f"API error {resp.status_code}: {resp.json()}")
        else:
            r = resp.json()
            st.session_state["last"] = r

if "last" in st.session_state:
    r = st.session_state["last"]
    color = {
        "CRITICAL": "#8b0000",
        "HIGH": "#b34700",
        "MEDIUM": "#9a7d00",
        "LOW": "#1f6f3f",
    }.get(r["risk_level"], "#444")
    st.markdown(
        f"### Verdict  \n"
        f"<span style='background:{color};color:white;padding:4px 12px;"
        f"border-radius:6px;font-weight:600'>{r['risk_level']}</span> "
        f"&nbsp; score `{r['risk_score']:.2f}` · confidence `{r['confidence']:.2f}`"
        f"{' · <b>DEGRADED (rules-only)</b>' if r['degraded'] else ''}",
        unsafe_allow_html=True,
    )
    if r.get("scam_type"):
        st.markdown(f"**Scam family:** `{r['scam_type']}`")

    left, right = st.columns([3, 2])
    with left:
        st.subheader("Model reasoning")
        st.info(r["verdict_reasoning"])
        st.subheader("Cited evidence")
        for i, ev in enumerate(r["evidence"], start=1):
            sim = (
                f" · sim {ev['similarity']:.2f}"
                if ev.get("similarity") is not None
                else ""
            )
            st.markdown(f"**[{i}] {ev['source']}**{sim}\n> {ev['excerpt']}")
        if not r["evidence"]:
            st.caption("No external evidence cited for this verdict.")
        v = r["verification"]
        st.subheader("Verification")
        st.write(
            f"samples `{v['samples']}` · agreement `{v['agreement_ratio']}` "
            f"· needs review `{v['needs_review']}` ({v['method']})"
        )
    with right:
        st.subheader("Prescreen routing")
        pre = r["prescreen"]
        st.write(
            f"route `{pre['route']}` · rule score `{pre['rule_score']:.2f}`\n\n"
            f"signals: keywords `{len(pre['signals']['keyword_hits'])}`, "
            f"urgency `{len(pre['signals']['urgency_hits'])}`, "
            f"otp `{pre['signals']['requests_otp']}`, money `{pre['signals']['requests_money']}`"
        )
        st.subheader("Audit trail")
        st.write(
            f"case `{r['case_id']}` · latency `{r['latency_ms']} ms` "
            f"· est. cost `${r['total_cost_usd']:.6f}`"
        )
        for u in r["usage"]:
            st.caption(
                f"{u['stage']}: {u['model']} — {u['prompt_tokens']}+{u['completion_tokens']} tok, "
                f"{u['latency_ms']} ms, ${u['est_cost_usd']:.6f}"
            )
        if st.button("Generate citizen alert", use_container_width=True):
            alert = api("POST", f"/api/scamwatch/alert/{r['case_id']}")
            if alert.status_code == 200:
                a = alert.json()
                st.success(a["one_line_verdict"])
                for action in a["recommended_actions"]:
                    st.markdown(f"- {action}")
                st.caption(" | ".join(c["contact"] for c in a["emergency_contacts"]))
            else:
                st.error("alert generation failed")

st.divider()
col1, col2 = st.columns(2)
with col1:
    st.subheader("Live intelligence (real events)")
    stats = api("GET", "/api/analytics/stats").json()
    c1, c2, c3 = st.columns(3)
    c1.metric("Events (24h)", stats.get("events_last_24h", 0))
    c2.metric("High risk", stats.get("high_risk_count", 0))
    c3.metric("Total cases", stats.get("total_cases", 0))
    recent = api("GET", "/api/analytics/recent?limit=5").json()
    for e in recent.get("events", []):
        st.caption(
            f"`{e['occurred_at'][:16]}` **{e['module']}** [{e['risk_level']}] "
            f"{e['summary'][:90]}"
        )
with col2:
    st.subheader("Cross-module correlations")
    corr = api("GET", "/api/analytics/correlations").json().get("correlations", [])
    if corr:
        for c in corr:
            st.markdown(
                f"- `{c['type']}` **{c['value']}** seen in {c['modules_seen']} modules"
            )
    else:
        st.caption("No entity has appeared in multiple modules yet.")
