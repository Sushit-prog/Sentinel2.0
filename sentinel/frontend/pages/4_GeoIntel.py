"""GeoIntel — Geospatial Intelligence Map for SENTINEL."""

import streamlit as st
import requests
import pydeck as pdk

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="GeoIntel — SENTINEL", page_icon="🗺️", layout="wide")

# ── STYLES ───────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}

.geo-card {
    background: #111827;
    border: 1px solid #1f2937;
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 10px;
}
.geo-stat-num {
    font-size: 2rem;
    font-weight: 800;
    line-height: 1.1;
    margin: 2px 0;
}
.geo-stat-label {
    font-size: 0.7rem;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 1.5px;
}
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
        🗺️ GeoIntel
    </h1>
    <p style="color:#00aaff;margin:4px 0 0;font-size:0.9rem;letter-spacing:1px">
        Geospatial Fraud Intelligence Map
    </p>
</div>
""",
    unsafe_allow_html=True,
)


# ── DATA FETCH ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def fetch_incidents():
    try:
        r = requests.get(f"{API_BASE}/api/geo/incidents?limit=200", timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return []


@st.cache_data(ttl=30)
def fetch_heatmap():
    try:
        r = requests.get(f"{API_BASE}/api/geo/heatmap", timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return []


incidents = fetch_incidents()
heatmap_data = fetch_heatmap()


# ── SIDEBAR FILTERS ──────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Filters")

    module_filter = st.multiselect(
        "Module",
        ["SCAMWatch", "CURRENCYGuard", "FRAUDGraph"],
        default=["SCAMWatch", "CURRENCYGuard", "FRAUDGraph"],
    )

    risk_filter = st.multiselect(
        "Risk Level",
        ["CRITICAL", "HIGH", "MEDIUM", "LOW"],
        default=["CRITICAL", "HIGH", "MEDIUM", "LOW"],
    )

    st.divider()
    st.markdown("**Map Layers**")
    show_heatmap = st.checkbox("Heatmap overlay", value=True)
    show_markers = st.checkbox("Individual incidents", value=True)

    st.divider()
    st.markdown("**Hotspot Locations**")
    st.caption("Based on NCRB/RBI/MHA reported fraud hotspots across India")


# ── FILTER DATA ──────────────────────────────────────────────────────────────
filtered = [
    inc
    for inc in incidents
    if inc.get("module") in module_filter and inc.get("risk_level") in risk_filter
]


# ── SUMMARY METRICS ──────────────────────────────────────────────────────────
st.markdown("### Intelligence Summary")

total = len(filtered)
scam_count = sum(1 for i in filtered if i.get("module") == "SCAMWatch")
curr_count = sum(1 for i in filtered if i.get("module") == "CURRENCYGuard")
fraud_count = sum(1 for i in filtered if i.get("module") == "FRAUDGraph")
critical_count = sum(1 for i in filtered if i.get("risk_level") == "CRITICAL")

# Top hotspot
top_hotspot = "--"
if filtered:
    from collections import Counter

    loc_counts = Counter(i.get("location_name", "") for i in filtered)
    if loc_counts:
        top_hotspot = loc_counts.most_common(1)[0][0]

# Dominant scam type
dominant_type = "--"
if filtered:
    type_counts = Counter(i.get("type", "") for i in filtered)
    if type_counts:
        dominant_type = type_counts.most_common(1)[0][0]

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.markdown(
        f"""
    <div class="geo-card" style="text-align:center">
        <div class="geo-stat-label">Total Incidents</div>
        <div class="geo-stat-num" style="color:#00aaff">{total}</div>
    </div>
    """,
        unsafe_allow_html=True,
    )
with col2:
    st.markdown(
        f"""
    <div class="geo-card" style="text-align:center">
        <div class="geo-stat-label">Scam Alerts</div>
        <div class="geo-stat-num" style="color:#ef4444">{scam_count}</div>
    </div>
    """,
        unsafe_allow_html=True,
    )
with col3:
    st.markdown(
        f"""
    <div class="geo-card" style="text-align:center">
        <div class="geo-stat-label">Currency Flags</div>
        <div class="geo-stat-num" style="color:#f59e0b">{curr_count}</div>
    </div>
    """,
        unsafe_allow_html=True,
    )
with col4:
    st.markdown(
        f"""
    <div class="geo-card" style="text-align:center">
        <div class="geo-stat-label">Fraud Networks</div>
        <div class="geo-stat-num" style="color:#8b5cf6">{fraud_count}</div>
    </div>
    """,
        unsafe_allow_html=True,
    )
with col5:
    st.markdown(
        f"""
    <div class="geo-card" style="text-align:center">
        <div class="geo-stat-label">Critical</div>
        <div class="geo-stat-num" style="color:#dc2626">{critical_count}</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

# Sub-metrics row
col_a, col_b = st.columns(2)
with col_a:
    st.markdown(
        f"""
    <div style="color:#6b7280;font-size:0.75rem;margin-top:-4px">
        <strong>Top Hotspot:</strong> {top_hotspot}
    </div>
    """,
        unsafe_allow_html=True,
    )
with col_b:
    st.markdown(
        f"""
    <div style="color:#6b7280;font-size:0.75rem;margin-top:-4px">
        <strong>Dominant Type:</strong> {dominant_type}
    </div>
    """,
        unsafe_allow_html=True,
    )

st.markdown("---")


# ── MAP ──────────────────────────────────────────────────────────────────────
st.markdown("### Fraud Incident Map")

# Module color mapping (matching FRAUDGraph pyvis colors)
MODULE_COLORS = {
    "SCAMWatch": [239, 68, 68],  # red
    "CURRENCYGuard": [245, 158, 11],  # orange
    "FRAUDGraph": [139, 92, 246],  # purple
}

RISK_SIZES = {
    "CRITICAL": 400,
    "HIGH": 300,
    "MEDIUM": 200,
    "LOW": 120,
}

# Build marker layer
marker_data = []
for inc in filtered:
    color = MODULE_COLORS.get(inc.get("module"), [150, 150, 150])
    size = RISK_SIZES.get(inc.get("risk_level"), 150)
    marker_data.append(
        {
            "lat": inc["lat"],
            "lng": inc["lng"],
            "color": color,
            "radius": size,
            "module": inc.get("module", ""),
            "type": inc.get("type", ""),
            "risk": inc.get("risk_level", ""),
            "location": inc.get("location_name", ""),
        }
    )

layers = []

# Heatmap layer
if show_heatmap and heatmap_data:
    heat_data = [
        {"lat": h["lat"], "lng": h["lng"], "weight": h["count"]} for h in heatmap_data
    ]
    layers.append(
        pdk.Layer(
            "HeatmapLayer",
            data=heat_data,
            get_position=["lng", "lat"],
            get_weight="weight",
            radiusPixels=60,
            intensity=1,
            threshold=0.05,
            colorRange=[
                [255, 255, 178, 40],
                [254, 204, 92, 100],
                [253, 141, 60, 150],
                [240, 59, 32, 200],
                [189, 0, 38, 255],
            ],
        )
    )

# Scatter layer
if show_markers and marker_data:
    layers.append(
        pdk.Layer(
            "ScatterplotLayer",
            data=marker_data,
            get_position=["lng", "lat"],
            get_fill_color="color",
            get_radius="radius",
            radiusMinPixels=6,
            radiusMaxPixels=30,
            pickable=True,
            auto_highlight=True,
        )
    )

# Hotspot labels
if heatmap_data:
    label_data = [
        {
            "lat": h["lat"],
            "lng": h["lng"],
            "name": h["location_name"],
            "count": h["count"],
        }
        for h in heatmap_data
        if h["count"] >= 1
    ]
    layers.append(
        pdk.Layer(
            "TextLayer",
            data=label_data,
            get_position=["lng", "lat"],
            get_text="name",
            get_size=10,
            get_color=[255, 255, 255, 200],
            get_alignment_baseline="'bottom'",
        )
    )

# View state
view = pdk.ViewState(
    latitude=22.9,
    longitude=78.6,
    zoom=4.5,
    pitch=0,
)

# Render
st.pydeck_chart(
    pdk.Deck(
        layers=layers,
        initial_view_state=view,
        map_style="mapbox://styles/mapbox/dark-v10",
        tooltip={
            "html": "<b>{location}</b><br/>"
            "Module: {module}<br/>"
            "Type: {type}<br/>"
            "Risk: {risk}",
            "style": {
                "backgroundColor": "#111827",
                "color": "#e5e7eb",
                "fontSize": "12px",
                "padding": "8px",
                "borderRadius": "6px",
            },
        },
    )
)

# ── HOTSPOT TABLE ────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### Top Hotspot Locations")

if heatmap_data:
    table_data = []
    for h in heatmap_data[:10]:
        risk_color = (
            "#dc2626"
            if h["risk_score"] >= 0.8
            else "#f97316"
            if h["risk_score"] >= 0.6
            else "#f59e0b"
            if h["risk_score"] >= 0.35
            else "#4ade80"
        )
        table_data.append(
            {
                "Location": h["location_name"],
                "Incidents": h["count"],
                "Dominant Type": h["dominant_type"],
                "Risk Score": f"{h['risk_score']:.0%}",
            }
        )
    st.table(table_data)
else:
    st.info(
        "No hotspot data available. Run analyses in SCAMWatch, CURRENCYGuard, or FRAUDGraph to generate incidents."
    )

# ── FOOTER ───────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    f"GeoIntel v0.1 · {total} incidents mapped · "
    f"Hotspot data based on NCRB/RBI/MHA reports · "
    f"SENTINEL v0.4"
)
