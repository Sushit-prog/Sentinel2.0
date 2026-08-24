import streamlit as st
import streamlit.components.v1 as components
import requests
import os
import sys

# Add project root to Python path for backend imports
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="FRAUDGraph — SENTINEL", page_icon="🕸️", layout="wide")

# ── HEADER ───────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
.sentinel-header {
    background: linear-gradient(135deg, #0E1117 0%, #1a1a2e 100%);
    border: 1px solid #00aaff33;
    border-radius: 8px;
    padding: 20px 24px;
    margin-bottom: 24px;
}
.risk-badge {
    display: inline-block;
    padding: 6px 20px;
    border-radius: 20px;
    font-weight: bold;
    font-size: 1.1rem;
    letter-spacing: 1px;
}
.risk-CRITICAL { background: #8B0000; color: white; }
.risk-HIGH     { background: #B84900; color: white; }
.risk-MEDIUM   { background: #8B7000; color: white; }
.risk-LOW      { background: #1B5E20; color: white; }
.entity-tag {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 10px;
    font-size: 0.75rem;
    margin: 2px;
    font-weight: bold;
}
.tag-PHONE    { background: #FF6B6B33; color: #FF6B6B; border: 1px solid #FF6B6B; }
.tag-ACCOUNT  { background: #FFD93D33; color: #FFD93D; border: 1px solid #FFD93D; }
.tag-DEVICE   { background: #6BCB7733; color: #6BCB77; border: 1px solid #6BCB77; }
.tag-VICTIM   { background: #4D96FF33; color: #4D96FF; border: 1px solid #4D96FF; }
.tag-LOCATION { background: #C77DFF33; color: #C77DFF; border: 1px solid #C77DFF; }
</style>

<div class="sentinel-header">
    <h2 style="color:#00aaff;margin:0">🕸️ FRAUDGraph</h2>
    <p style="color:#888;margin:4px 0 0">Graph AI Fraud Network Mapping &nbsp;|&nbsp; Law Enforcement Intelligence Module</p>
</div>
""",
    unsafe_allow_html=True,
)

# How It Works section
with st.expander("How FRAUDGraph Works", expanded=False):
    st.markdown("""
    **FRAUDGraph** maps fraud networks using graph AI and entity resolution:

    1. **Entity Extraction** — Parses phone numbers, accounts, devices from input + LLM extracts from victim statements
    2. **Relationship Inference** — Identifies connections: who called whom, money transfers, device usage
    3. **Neo4j Graph Storage** — Writes entities and relationships to graph database (in-memory fallback available)
    4. **NetworkX Analysis** — Connected components detect fraud rings, betweenness centrality finds hub nodes
    5. **Pyvis Visualization** — Interactive network graph with color-coded entity types
    6. **Evidence Kit** — Court-admissible ZIP bundle with PDF, graph HTML, CSV, JSON, and manifest

    **Entity Types:** PHONE, ACCOUNT, DEVICE, VICTIM, LOCATION

    **Relationship Types:** CALLED, TRANSFERRED_TO, USED_BY, CONTACTED, BELONGS_TO
    """)

# ── INPUT PANEL ──────────────────────────────────────────────────────────────
with st.container():
    col_input, col_legend = st.columns([3, 1])

    with col_input:
        st.markdown("#### 📥 Entity Input")
        col1, col2, col3 = st.columns(3)

        with col1:
            phones_input = st.text_area(
                "📱 Phone Numbers",
                value=st.session_state.get("sample_phones", ""),
                placeholder="One per line:\n9876543210\n8765432109",
                height=120,
                help="Indian or international phone numbers involved in the fraud",
                key="phones_area",
            )

        with col2:
            accounts_input = st.text_area(
                "🏦 Bank Account / UPI IDs",
                value=st.session_state.get("sample_accounts", ""),
                placeholder="One per line:\nACC123456789\nuser@upi",
                height=120,
                help="Bank account numbers, UPI IDs, or wallet IDs",
                key="accounts_area",
            )

        with col3:
            devices_input = st.text_area(
                "📟 Device IDs / IMEI",
                value=st.session_state.get("sample_devices", ""),
                placeholder="One per line:\nIMEI:359847XXXXXX\nMAC:AA:BB:CC",
                height=120,
                help="Device fingerprints, IMEI numbers, or MAC addresses",
                key="devices_area",
            )

        victim_statement = st.text_area(
            "📋 Victim Statement (free text)",
            value=st.session_state.get("sample_statement", ""),
            placeholder="Describe the fraud in detail. Include any phone numbers, accounts, or device details mentioned by the victim. The AI will extract and link entities automatically...",
            height=140,
            help="Free text victim statement. LLM will extract entities and relationships automatically.",
            key="statement_area",
        )

    with col_legend:
        st.markdown("#### 🎨 Entity Legend")
        st.markdown(
            """
        <div style="margin-top:8px">
        <div class="entity-tag tag-PHONE">● PHONE</div><br/>
        <div class="entity-tag tag-ACCOUNT">● ACCOUNT</div><br/>
        <div class="entity-tag tag-DEVICE">● DEVICE</div><br/>
        <div class="entity-tag tag-VICTIM">● VICTIM</div><br/>
        <div class="entity-tag tag-LOCATION">● LOCATION</div>
        </div>
        """,
            unsafe_allow_html=True,
        )

        st.markdown("---")
        st.markdown("**Risk Levels**")
        for level, color in [
            ("CRITICAL", "#CC0000"),
            ("HIGH", "#CC5500"),
            ("MEDIUM", "#AA8800"),
            ("LOW", "#1B7F2A"),
        ]:
            st.markdown(
                f'<span style="color:{color};font-weight:bold">▌</span> {level}',
                unsafe_allow_html=True,
            )

# ── ANALYZE BUTTON ────────────────────────────────────────────────────────────
st.markdown("---")
col_btn, col_status = st.columns([1, 3])

with col_btn:
    analyze_clicked = st.button(
        "🕵️ Build Fraud Network", type="primary", use_container_width=True
    )

# ── SAMPLE DATA ───────────────────────────────────────────────────────────────
SAMPLE_PHONES = "9876543210\n8765432109\n7654321098"
SAMPLE_ACCOUNTS = "HDFC0000123456\nSBI99887766"
SAMPLE_DEVICES = "IMEI:359847101234567"
SAMPLE_STATEMENT = (
    "I received a call from 9876543210 claiming to be from CBI. "
    "They said my Aadhaar number was linked to a money laundering case. "
    "A second person on 8765432109 posed as a Supreme Court judge. "
    "They forced me to transfer 2,40,000 rupees to account HDFC0000123456 "
    "and later 80,000 rupees to SBI99887766. The calls were made from a device "
    "with IMEI 359847101234567. A third operator on 7654321098 coordinated "
    "the entire operation from what sounded like a call centre."
)

with st.expander("Load Sample Data (Digital Arrest Ring)", expanded=False):
    if st.button("Load Sample", key="load_sample"):
        st.session_state["sample_data_loaded"] = True
        st.session_state["sample_phones"] = SAMPLE_PHONES
        st.session_state["sample_accounts"] = SAMPLE_ACCOUNTS
        st.session_state["sample_devices"] = SAMPLE_DEVICES
        st.session_state["sample_statement"] = SAMPLE_STATEMENT
        st.rerun()

# Auto-load sample ONLY on first visit (never overwrite user input)
if "sample_data_loaded" not in st.session_state:
    st.session_state["sample_data_loaded"] = True
    st.session_state["sample_phones"] = SAMPLE_PHONES
    st.session_state["sample_accounts"] = SAMPLE_ACCOUNTS
    st.session_state["sample_devices"] = SAMPLE_DEVICES
    st.session_state["sample_statement"] = SAMPLE_STATEMENT

# Apply sample data only once (pop removes key so it won't re-apply on rerun)
if "sample_phones" in st.session_state:
    phones_input = st.session_state.pop("sample_phones", phones_input)
if "sample_accounts" in st.session_state:
    accounts_input = st.session_state.pop("sample_accounts", accounts_input)
if "sample_devices" in st.session_state:
    devices_input = st.session_state.pop("sample_devices", devices_input)
if "sample_statement" in st.session_state:
    victim_statement = st.session_state.pop("sample_statement", victim_statement)

# ── ANALYSIS ──────────────────────────────────────────────────────────────────
if analyze_clicked:
    phones = [p.strip() for p in phones_input.splitlines() if p.strip()]
    accounts = [a.strip() for a in accounts_input.splitlines() if a.strip()]
    devices = [d.strip() for d in devices_input.splitlines() if d.strip()]

    if not any([phones, accounts, devices, victim_statement.strip()]):
        st.warning(
            "⚠️ Please provide at least one phone number, account ID, device ID, or victim statement."
        )
        st.stop()

    with st.spinner("🕵️ Building fraud network graph..."):
        try:
            response = requests.post(
                f"{API_BASE}/api/fraudgraph/analyze",
                json={
                    "phones": phones,
                    "accounts": accounts,
                    "devices": devices,
                    "victim_statement": victim_statement,
                },
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()

        except requests.exceptions.ConnectionError:
            st.error(
                "❌ Cannot connect to SENTINEL backend. Start it with: `uvicorn backend.main:app --reload --port 8000`"
            )
            st.stop()
        except requests.exceptions.Timeout:
            st.error("⏱️ Analysis timed out. The LLM is processing — try again.")
            st.stop()
        except Exception as e:
            st.error(f"❌ Analysis error: {e}")
            st.stop()

    # ── RESULTS HEADER ────────────────────────────────────────────────────────
    risk_level = data.get("risk_level", "LOW")
    risk_score = data.get("risk_score", 0.0)
    session_id = data.get("session_id", "")

    risk_colors = {
        "CRITICAL": "#CC0000",
        "HIGH": "#CC5500",
        "MEDIUM": "#AA8800",
        "LOW": "#1B7F2A",
    }
    risk_icons = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}
    rc = risk_colors.get(risk_level, "#888")

    st.markdown(
        f"""
    <div style="background:linear-gradient(135deg,{rc}22,{rc}11);border:2px solid {rc};
                border-radius:10px;padding:16px 24px;margin:16px 0;display:flex;
                align-items:center;justify-content:space-between">
        <div>
            <div style="font-size:0.8rem;color:#888;text-transform:uppercase;letter-spacing:2px">Risk Assessment</div>
            <div style="font-size:2rem;font-weight:bold;color:{rc}">{risk_icons.get(risk_level, "⚪")} {risk_level}</div>
        </div>
        <div style="text-align:right">
            <div style="font-size:0.8rem;color:#888">Risk Score</div>
            <div style="font-size:1.8rem;font-weight:bold;color:{rc}">{risk_score:.1%}</div>
        </div>
        <div style="text-align:right">
            <div style="font-size:0.8rem;color:#888">Network Stats</div>
            <div style="color:#ccc">{len(data.get("entities", []))} entities &nbsp;|&nbsp; {len(data.get("relationships", []))} links &nbsp;|&nbsp; {len(data.get("clusters", []))} rings</div>
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    neo4j_status = data.get("neo4j_connected", False)
    if neo4j_status:
        st.success("✅ Neo4j Aura: Graph persisted to cloud database")
    else:
        st.info(
            "ℹ️ Neo4j: Running in in-memory mode (configure NEO4J_URI in .env for persistence)"
        )

    # ── NETWORK GRAPH ─────────────────────────────────────────────────────────
    st.markdown("### 🕸️ Fraud Network Graph")
    graph_html = data.get("graph_html", "")
    if graph_html:
        components.html(graph_html, height=540, scrolling=False)
    else:
        st.warning("Network graph unavailable. Install pyvis: `pip install pyvis`")

    # ── TABS: ENTITIES | RINGS | INTELLIGENCE | PDF ───────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs(
        ["📋 Entities", "🔴 Fraud Rings", "🧠 Intelligence", "📄 Download Report"]
    )

    with tab1:
        st.markdown("#### Detected Entities")
        entities = data.get("entities", [])
        if entities:
            type_groups = {}
            for e in entities:
                etype = e.get("type", "UNKNOWN")
                type_groups.setdefault(etype, []).append(e)

            for etype, ents in type_groups.items():
                css_class = f"tag-{etype}"
                st.markdown(f"**{etype}** ({len(ents)})")
                tags_html = " ".join(
                    f'<span class="entity-tag {css_class}">{e["value"]}</span>'
                    for e in ents
                )
                st.markdown(tags_html, unsafe_allow_html=True)
                st.markdown("")
        else:
            st.info("No entities detected. Add more input data.")

        rels = data.get("relationships", [])
        if rels:
            st.markdown("#### Relationships Mapped")
            rel_rows = [
                [
                    r.get("from_id", "")[:30],
                    r.get("rel_type", ""),
                    r.get("to_id", "")[:30],
                ]
                for r in rels
            ]
            st.table([{"From": r[0], "Relation": r[1], "To": r[2]} for r in rel_rows])

    with tab2:
        st.markdown("#### Fraud Ring Analysis")
        clusters = data.get("clusters", [])
        if clusters:
            for cluster in clusters:
                cid = cluster.get("cluster_id", 0) + 1
                size = cluster.get("size", 0)
                victims = cluster.get("victim_count", 0)
                hub = cluster.get("hub_node", "N/A") or "N/A"
                score = cluster.get("risk_score", 0.0)
                score_pct = f"{score:.1%}"

                ring_color = (
                    "#CC0000"
                    if score >= 0.8
                    else "#CC5500"
                    if score >= 0.6
                    else "#AA8800"
                    if score >= 0.35
                    else "#1B7F2A"
                )

                with st.expander(
                    f"🔴 Ring #{cid} — {size} entities — Risk: {score_pct}",
                    expanded=(cid == 1),
                ):
                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric("Entities in Ring", size)
                    col_b.metric("Victims Identified", victims)
                    col_c.metric("Hub Node", hub[:25] if hub else "N/A")
                    st.markdown(
                        f'**Risk Score:** <span style="color:{ring_color};font-weight:bold">{score_pct}</span>',
                        unsafe_allow_html=True,
                    )
                    nodes_in_ring = cluster.get("nodes", [])
                    if nodes_in_ring:
                        st.markdown(
                            "**Nodes:** "
                            + " · ".join(f"`{n[:25]}`" for n in nodes_in_ring[:10])
                        )
        else:
            st.info(
                "No fraud rings detected. A minimum of 2 connected entities is required to form a ring."
            )

    with tab3:
        st.markdown("#### Intelligence Summary")
        summary = data.get("llm_summary", "No summary generated.")
        st.markdown(
            f"""
        <div style="background:#111827;border-left:3px solid #00aaff;padding:16px 20px;border-radius:0 8px 8px 0;line-height:1.7;color:#e5e7eb">
        {summary.replace(chr(10), "<br/>")}
        </div>
        """,
            unsafe_allow_html=True,
        )

        related = data.get("related_threats", [])
        if related:
            st.markdown("#### 🔗 Related Threats (Cross-Module Intelligence)")
            st.caption(
                "Matching patterns found from SCAMWatch or prior FRAUDGraph sessions"
            )
            for threat in related:
                meta = threat.get("metadata", {})
                st.markdown(
                    f"""
                <div style="border:1px solid #333;border-radius:6px;padding:10px 14px;margin:6px 0;background:#0d1117">
                    <span style="color:#888;font-size:0.75rem">{meta.get("event_type", "UNKNOWN")} &nbsp;|&nbsp; Risk: {meta.get("risk_level", "?")}</span>
                    <div style="color:#ccc;font-size:0.85rem;margin-top:4px">{threat.get("content", "")[:200]}…</div>
                </div>
                """,
                    unsafe_allow_html=True,
                )

    with tab4:
        st.markdown("#### 📄 Download Intelligence Package")
        st.markdown("""
        **PDF Report** includes:
        - Classified header with session metadata
        - Full entity inventory
        - Fraud ring analysis table
        - LLM intelligence summary
        - Legal disclaimer (IT Act 2000 / DPDP Act 2023)
        """)
        if data.get("pdf_available") and session_id:
            col_pdf, col_kit = st.columns(2)

            with col_pdf:
                pdf_url = f"{API_BASE}/api/fraudgraph/report/{session_id}"
                try:
                    pdf_resp = requests.get(pdf_url, timeout=10)
                    if pdf_resp.status_code == 200:
                        st.download_button(
                            label="📥 Download PDF Report",
                            data=pdf_resp.content,
                            file_name=f"SENTINEL_FRAUD_{session_id[:8].upper()}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                        )
                    else:
                        st.error("PDF not found on server.")
                except Exception as e:
                    st.error(f"PDF download error: {e}")

            with col_kit:
                kit_url = f"{API_BASE}/api/fraudgraph/evidence-kit/{session_id}"
                try:
                    kit_resp = requests.get(kit_url, timeout=15)
                    if kit_resp.status_code == 200:
                        st.download_button(
                            label="📦 Download Evidence Kit (ZIP)",
                            data=kit_resp.content,
                            file_name=f"SENTINEL_EVIDENCE_{session_id[:8].upper()}.zip",
                            mime="application/zip",
                            use_container_width=True,
                        )
                        st.caption(
                            "ZIP contains: PDF + Graph HTML + Entity CSV + Analysis JSON + Manifest"
                        )
                    else:
                        st.warning("Evidence kit not available.")
                except Exception as e:
                    st.warning(f"Evidence kit error: {e}")

            st.success("✅ Intelligence packages ready")
        else:
            st.warning("No analysis data available. Run analysis first.")

    # ── PROCESSING METADATA ───────────────────────────────────────────────────
    proc_time = data.get("processing_time_ms", 0)
    st.markdown("---")
    st.caption(
        f"Session: `{session_id[:8]}` &nbsp;|&nbsp; "
        f"Processed in {proc_time}ms &nbsp;|&nbsp; "
        f"Neo4j: {'🟢 Connected' if data.get('neo4j_connected') else '🟡 In-Memory'} &nbsp;|&nbsp; "
        f"SENTINEL v0.3"
    )

# ── EMPTY STATE ───────────────────────────────────────────────────────────────
else:
    st.markdown(
        """
    <div style="text-align:center;padding:60px 20px;color:#4B5563">
        <div style="font-size:4rem">🕸️</div>
        <h3 style="color:#6B7280">Enter entity data to build the fraud network graph</h3>
        <p>Add phone numbers, bank accounts, device IDs, or paste a victim statement above.<br/>
        The AI will extract entities, map relationships, identify fraud rings, and generate an intelligence report.</p>
    </div>
    """,
        unsafe_allow_html=True,
    )
