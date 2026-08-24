import streamlit as st
import requests
import sys
import os

# Add project root to Python path so all pages can import backend modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="SENTINEL — Digital Public Safety Intelligence",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── GLOBAL STYLES ─────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}

.sentinel-card {
    background: #111827;
    border: 1px solid #1f2937;
    border-radius: 10px;
    padding: 20px 22px;
    margin-bottom: 12px;
    transition: border-color 0.2s;
}
.sentinel-card:hover { border-color: #00aaff44; }

.stat-number {
    font-size: 2.4rem;
    font-weight: 800;
    line-height: 1.1;
    margin: 4px 0;
}
.stat-label {
    font-size: 0.75rem;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 1.5px;
}

.status-pill {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: bold;
    letter-spacing: 0.5px;
}
.status-operational { background: #14532d44; color: #4ade80; border: 1px solid #166534; }
.status-degraded    { background: #78350f44; color: #fbbf24; border: 1px solid #92400e; }
.status-offline     { background: #7f1d1d44; color: #f87171; border: 1px solid #991b1b; }

.feed-item {
    border-left: 3px solid #1f2937;
    padding: 8px 14px;
    margin: 6px 0;
    background: #0d1117;
    border-radius: 0 6px 6px 0;
    font-size: 0.82rem;
}
.feed-item-SCAM     { border-left-color: #ef4444; }
.feed-item-CURRENCY { border-left-color: #f59e0b; }
.feed-item-FRAUD    { border-left-color: #8b5cf6; }

.correlation-badge {
    background: #1e1b4b;
    border: 1px solid #4338ca;
    border-radius: 8px;
    padding: 12px 16px;
    margin: 6px 0;
    font-size: 0.83rem;
}

.module-nav-card {
    background: linear-gradient(135deg, #111827, #1f2937);
    border: 1px solid #374151;
    border-radius: 12px;
    padding: 22px;
    text-align: center;
    margin: 6px;
    transition: all 0.2s;
}
.module-nav-card:hover {
    border-color: #00aaff;
    transform: translateY(-2px);
}
</style>
""",
    unsafe_allow_html=True,
)


# ── HEADER ─────────────────────────────────────────────────────────────────────
st.markdown(
    """
<div style="background:linear-gradient(135deg,#060B14 0%,#0d1b2a 60%,#060B14 100%);
            border:1px solid #00aaff22;border-radius:12px;padding:28px 32px;margin-bottom:24px;">
    <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px">
        <div>
            <h1 style="color:#ffffff;margin:0;font-size:2.2rem;letter-spacing:3px;font-weight:900">
                SENTINEL
            </h1>
            <p style="color:#00aaff;margin:4px 0 2px;font-size:1rem;letter-spacing:1px">
                Digital Public Safety Intelligence Platform
            </p>
            <p style="color:#4b5563;margin:0;font-size:0.78rem">
                ET AI Hackathon 2.0 &middot; AI for Digital Public Safety
            </p>
        </div>
        <div style="text-align:right">
            <div style="color:#4b5563;font-size:0.7rem;text-transform:uppercase;letter-spacing:1px">Modules</div>
            <div style="font-size:1.1rem;margin-top:4px">
                <span title="SCAMWatch">SCAM</span>&nbsp;
                <span title="CURRENCYGuard">CURRENCY</span>&nbsp;
                <span title="FRAUDGraph">FRAUD</span>
            </div>
        </div>
    </div>
</div>
""",
    unsafe_allow_html=True,
)


# ── LIVE DATA FETCH ────────────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def fetch_stats():
    try:
        r = requests.get(f"{API_BASE}/api/intelligence/stats", timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {
        "total_events": 0,
        "scamwatch_events": 0,
        "currencyguard_events": 0,
        "fraudgraph_events": 0,
        "high_risk_count": 0,
        "critical_risk_count": 0,
        "last_updated": "--",
    }


@st.cache_data(ttl=30)
def fetch_recent(limit=12):
    try:
        r = requests.get(f"{API_BASE}/api/intelligence/recent?limit={limit}", timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return []


@st.cache_data(ttl=60)
def fetch_correlations():
    try:
        r = requests.get(f"{API_BASE}/api/intelligence/correlations?limit=5", timeout=8)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return []


@st.cache_data(ttl=15)
def fetch_health():
    try:
        r = requests.get(f"{API_BASE}/api/intelligence/health", timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {
        "overall": "offline",
        "modules": {
            "SCAMWatch": {"status": "offline"},
            "CURRENCYGuard": {"status": "offline"},
            "FRAUDGraph": {"status": "offline"},
            "ChromaDB": {"status": "offline"},
        },
    }


@st.cache_data(ttl=30)
def fetch_timeline():
    try:
        r = requests.get(f"{API_BASE}/api/intelligence/timeline", timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {
        "total_today": 0,
        "critical_today": 0,
        "high_today": 0,
        "highest_risk_type": "LOW",
        "buckets": [],
    }


stats = fetch_stats()
health = fetch_health()
recent_events = fetch_recent()
correlations = fetch_correlations()
timeline = fetch_timeline()


# ── MODULE STATUS ROW ──────────────────────────────────────────────────────────
st.markdown("### System Status")
status_cols = st.columns(4)
module_icons = {
    "SCAMWatch": "SCAM",
    "CURRENCYGuard": "CURRENCY",
    "FRAUDGraph": "FRAUD",
    "ChromaDB": "DB",
}
module_descs = {
    "SCAMWatch": "Scam Detection",
    "CURRENCYGuard": "Currency Auth",
    "FRAUDGraph": "Fraud Networks",
    "ChromaDB": "Intelligence Store",
}

for i, (mod_name, mod_info) in enumerate(health.get("modules", {}).items()):
    status = mod_info.get("status", "offline")
    css_class = f"status-{status}"
    icon = module_icons.get(mod_name, "MOD")
    desc = module_descs.get(mod_name, "")
    with status_cols[i % 4]:
        st.markdown(
            f"""
        <div class="sentinel-card" style="text-align:center;padding:16px">
            <div style="font-size:1.8rem">{icon}</div>
            <div style="color:#e5e7eb;font-weight:600;margin:6px 0 4px">{mod_name}</div>
            <div style="color:#6b7280;font-size:0.72rem;margin-bottom:8px">{desc}</div>
            <span class="status-pill {css_class}">{status.upper()}</span>
        </div>
        """,
            unsafe_allow_html=True,
        )

st.markdown("---")


# ── LIVE THREAT MONITOR ───────────────────────────────────────────────────────
st.markdown("### Live Threat Monitor")

# Threat counter
total_today = timeline.get("total_today", 0)
critical_today = timeline.get("critical_today", 0)
high_today = timeline.get("high_today", 0)

col_counter, col_chart = st.columns([1, 2])

with col_counter:
    if total_today > 0:
        counter_color = (
            "#dc2626"
            if critical_today > 0
            else "#f97316"
            if high_today > 0
            else "#00aaff"
        )
        st.markdown(
            f"""
        <div class="sentinel-card" style="text-align:center;padding:24px">
            <div class="stat-label">Threats Detected Today</div>
            <div class="stat-number" style="color:{counter_color}">{total_today}</div>
            {"<div style='color:#dc2626;font-size:0.8rem;font-weight:bold'>CRITICAL: " + str(critical_today) + "</div>" if critical_today > 0 else ""}
            {"<div style='color:#f97316;font-size:0.8rem'>HIGH: " + str(high_today) + "</div>" if high_today > 0 else ""}
        </div>
        """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
        <div class="sentinel-card" style="text-align:center;padding:24px">
            <div class="stat-label">Threats Detected Today</div>
            <div class="stat-number" style="color:#374151">0</div>
            <div style="color:#6b7280;font-size:0.75rem">No threats detected yet</div>
        </div>
        """,
            unsafe_allow_html=True,
        )

with col_chart:
    buckets = timeline.get("buckets", [])
    if buckets:
        # Filter to only hours with activity for cleaner chart
        active_buckets = [b for b in buckets if b.get("total", 0) > 0]
        if active_buckets:
            chart_data = {
                "Hour": [b["hour"] for b in active_buckets],
                "CRITICAL": [b.get("CRITICAL", 0) for b in active_buckets],
                "HIGH": [b.get("HIGH", 0) for b in active_buckets],
                "MEDIUM": [b.get("MEDIUM", 0) for b in active_buckets],
                "LOW": [b.get("LOW", 0) for b in active_buckets],
            }
            st.bar_chart(
                chart_data, x="Hour", color=["#dc2626", "#f97316", "#f59e0b", "#4ade80"]
            )
        else:
            st.info("No threat activity in time buckets yet.")
    else:
        st.info("Timeline data loading...")

st.markdown("---")


# ── LIVE STATS ROW ────────────────────────────────────────────────────────────
st.markdown("### Intelligence Summary")

stat_cols = st.columns(6)
stat_defs = [
    ("total_events", "Total Events", "#00aaff"),
    ("scamwatch_events", "Scam Alerts", "#ef4444"),
    ("currencyguard_events", "Currency Checks", "#f59e0b"),
    ("fraudgraph_events", "Fraud Networks", "#8b5cf6"),
    ("high_risk_count", "High Risk", "#f97316"),
    ("critical_risk_count", "Critical", "#dc2626"),
]

for i, (key, label, color) in enumerate(stat_defs):
    value = stats.get(key, 0)
    with stat_cols[i]:
        st.markdown(
            f"""
        <div class="sentinel-card" style="text-align:center">
            <div class="stat-label">{label}</div>
            <div class="stat-number" style="color:{color}">{value}</div>
        </div>
        """,
            unsafe_allow_html=True,
        )

# Event distribution bar
total = max(stats.get("total_events", 1), 1)
scam_pct = round(stats.get("scamwatch_events", 0) / total * 100)
curr_pct = round(stats.get("currencyguard_events", 0) / total * 100)
fraud_pct = round(stats.get("fraudgraph_events", 0) / total * 100)
remain_pct = max(100 - scam_pct - curr_pct - fraud_pct, 0)

st.markdown(
    f"""
<div style="margin:8px 0 4px">
    <div style="font-size:0.7rem;color:#6b7280;margin-bottom:6px;letter-spacing:1px">EVENT DISTRIBUTION</div>
    <div style="height:8px;border-radius:4px;overflow:hidden;display:flex;background:#1f2937">
        <div style="width:{scam_pct}%;background:#ef4444" title="SCAMWatch {scam_pct}%"></div>
        <div style="width:{curr_pct}%;background:#f59e0b" title="CURRENCYGuard {curr_pct}%"></div>
        <div style="width:{fraud_pct}%;background:#8b5cf6" title="FRAUDGraph {fraud_pct}%"></div>
        <div style="width:{remain_pct}%;background:#374151"></div>
    </div>
    <div style="display:flex;gap:16px;margin-top:5px;font-size:0.68rem;color:#6b7280">
        <span><span style="color:#ef4444">■</span> SCAMWatch</span>
        <span><span style="color:#f59e0b">■</span> CURRENCYGuard</span>
        <span><span style="color:#8b5cf6">■</span> FRAUDGraph</span>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown(
    f"<div style='text-align:right;color:#374151;font-size:0.68rem'>Last updated: {stats.get('last_updated', '--')}</div>",
    unsafe_allow_html=True,
)
st.markdown("---")


# ── TWO COLUMN LOWER SECTION ──────────────────────────────────────────────────
col_feed, col_intel = st.columns([3, 2])


# ── LEFT: LIVE ACTIVITY FEED ──────────────────────────────────────────────────
with col_feed:
    col_title, col_refresh = st.columns([3, 1])
    with col_title:
        st.markdown("### Live Intelligence Feed")
    with col_refresh:
        if st.button("Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    if recent_events:
        risk_color_map = {
            "CRITICAL": "#dc2626",
            "HIGH": "#f97316",
            "MEDIUM": "#f59e0b",
            "LOW": "#4ade80",
            "SUSPECT": "#f59e0b",
            "GENUINE": "#4ade80",
            "COUNTERFEIT": "#dc2626",
            "INCONCLUSIVE": "#9ca3af",
        }

        module_tag_map = {
            "SCAM": ("SCAM", "#ef444422", "#ef4444"),
            "CURR": ("CURRENCY", "#f59e0b22", "#f59e0b"),
            "FRAUD": ("FRAUD", "#8b5cf622", "#8b5cf6"),
        }

        def feed_class(event_type: str) -> str:
            et = event_type.upper()
            if "SCAM" in et:
                return "feed-item-SCAM"
            if "CURR" in et:
                return "feed-item-CURRENCY"
            if "FRAUD" in et:
                return "feed-item-FRAUD"
            return ""

        for event in recent_events:
            etype = event.get("event_type", "UNKNOWN").upper()
            risk = str(event.get("risk_level", "UNKNOWN")).upper()
            content = event.get("content_preview", "")

            fc = feed_class(etype)
            tag_icon, tag_bg, tag_color = "MOD", "#374151", "#9ca3af"
            for key, (icon, bg, color) in module_tag_map.items():
                if key in etype:
                    tag_icon, tag_bg, tag_color = icon, bg, color
                    break

            rc = risk_color_map.get(risk, "#9ca3af")

            st.markdown(
                f"""
            <div class="feed-item {fc}">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
                    <span style="background:{tag_bg};color:{tag_color};padding:2px 8px;border-radius:10px;font-size:0.68rem;font-weight:bold">
                        {tag_icon} {etype}
                    </span>
                    <span style="color:{rc};font-size:0.68rem;font-weight:bold">{risk}</span>
                </div>
                <div style="color:#9ca3af;line-height:1.4">{content}</div>
            </div>
            """,
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            """
        <div style="text-align:center;padding:40px 0;color:#4b5563">
            <div style="font-size:2.5rem">No intelligence events yet.</div>
            <div style="font-size:0.8rem;margin-top:6px">Analyze threats using the modules in the sidebar.</div>
        </div>
        """,
            unsafe_allow_html=True,
        )


# ── RIGHT: CROSS-MODULE INTELLIGENCE ─────────────────────────────────────────
with col_intel:
    st.markdown("### Cross-Module Correlations")
    st.caption("Entities flagged across multiple detection modules")

    if correlations:
        for corr in correlations:
            entity_val = corr.get("entity_value", "")
            modules_seen = corr.get("modules_seen", [])
            risks = corr.get("risk_levels", [])
            match_count = corr.get("match_count", 0)

            risk_priority = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
            top_risk = next((r for r in risk_priority if r in risks), "UNKNOWN")
            rc_map = {
                "CRITICAL": "#dc2626",
                "HIGH": "#f97316",
                "MEDIUM": "#f59e0b",
                "LOW": "#4ade80",
            }
            rc = rc_map.get(top_risk, "#9ca3af")

            module_badges = " ".join(
                f'<span style="background:#1f2937;color:#e5e7eb;padding:2px 8px;border-radius:8px;font-size:0.65rem">{m}</span>'
                for m in modules_seen
            )

            st.markdown(
                f"""
            <div class="correlation-badge">
                <div style="display:flex;justify-content:space-between;margin-bottom:6px">
                    <code style="color:#a78bfa;font-size:0.8rem">{entity_val}</code>
                    <span style="color:{rc};font-size:0.72rem;font-weight:bold">{top_risk}</span>
                </div>
                <div style="margin-bottom:6px">{module_badges}</div>
                <div style="color:#6b7280;font-size:0.72rem">
                    Detected in {match_count} module{"s" if match_count != 1 else ""} -- high confidence threat signal
                </div>
            </div>
            """,
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            """
        <div style="text-align:center;padding:40px 16px;color:#4b5563;background:#0d1117;border-radius:8px">
            <div style="font-size:2rem">No cross-module correlations found yet.</div>
            <div style="font-size:0.75rem;margin-top:6px;color:#374151">
                Submit the same phone number or account ID across<br/>
                SCAMWatch and FRAUDGraph to see correlations appear here.
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown("### Launch Module")

    nav_items = [
        ("SCAM", "SCAMWatch", "Analyze suspicious messages, calls, and scam texts"),
        (
            "CURRENCY",
            "CURRENCYGuard",
            "Upload currency note image for counterfeit detection",
        ),
        ("FRAUD", "FRAUDGraph", "Map fraud networks and generate intelligence reports"),
    ]

    for icon, name, desc in nav_items:
        st.markdown(
            f"""
        <div class="module-nav-card">
            <div style="font-size:1.6rem">{icon}</div>
            <div style="color:#e5e7eb;font-weight:700;margin:6px 0 4px">{name}</div>
            <div style="color:#6b7280;font-size:0.72rem">{desc}</div>
        </div>
        """,
            unsafe_allow_html=True,
        )


# ── FOOTER ────────────────────────────────────────────────────────────────────
st.markdown("---")
col_f1, col_f2, col_f3 = st.columns(3)

overall_status = health.get("overall", "offline")
overall_color = (
    "#4ade80"
    if overall_status == "operational"
    else "#f59e0b"
    if overall_status == "degraded"
    else "#ef4444"
)

with col_f1:
    st.markdown(
        f"""
    <div style="color:#4b5563;font-size:0.72rem">
        System: <span style="color:{overall_color};font-weight:bold">{overall_status.upper()}</span>
        &middot; SENTINEL v0.4
    </div>
    """,
        unsafe_allow_html=True,
    )

with col_f2:
    st.markdown(
        """
    <div style="color:#374151;font-size:0.72rem;text-align:center">
        ET AI Hackathon 2.0 &middot; AI for Digital Public Safety
    </div>
    """,
        unsafe_allow_html=True,
    )

with col_f3:
    st.markdown(
        f"""
    <div style="color:#4b5563;font-size:0.72rem;text-align:right">
        Intelligence Store: {stats.get("total_events", 0)} events indexed
    </div>
    """,
        unsafe_allow_html=True,
    )
