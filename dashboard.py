"""
Eco-Bridge -- SME Dashboard
"""

import streamlit as st
from data_collection_agent import compute_footprint
from scoring_agent import score_sme
from report_generation_agent import generate_report_markdown

st.set_page_config(page_title="Eco-Bridge", page_icon="leaf", layout="centered")

st.title("Eco-Bridge")
st.caption("Agentic sustainability compliance auditor for textile SME manufacturers")

st.divider()

sme_id = st.text_input("Enter SME ID", value="SME0071", placeholder="e.g. SME0071")

col1, col2 = st.columns([1, 3])
with col1:
    run_button = st.button("Generate Report", type="primary")

if run_button and sme_id:
    with st.spinner("Fetching real emissions data from BigQuery..."):
        try:
            footprint = compute_footprint(sme_id)
        except Exception as e:
            st.error(f"Could not find data for {sme_id}: {e}")
            st.stop()

    with st.spinner("Scoring against sourced Carbonfact + grid benchmarks..."):
        result = score_sme(sme_id)
        rubric = result["rubric"]

    if rubric.get("score") is None:
        st.warning("Insufficient data to generate a compliance score for this SME.")
        st.stop()

    score = rubric["score"]

    if score >= 80:
        st.success(f"### Compliance Score: {score}/100 -- Strong")
    elif score >= 50:
        st.warning(f"### Compliance Score: {score}/100 -- Moderate")
    else:
        st.error(f"### Compliance Score: {score}/100 -- Needs Improvement")

    m1, m2, m3 = st.columns(3)
    m1.metric("Material", footprint["material"])
    m2.metric("Location", footprint["location"])
    m3.metric("Monthly Production", f"{footprint['monthly_production_kg']} kg")

    m4, m5, m6 = st.columns(3)
    m4.metric("Scope 2 (Grid)", f"{footprint['scope2_ghg_kgco2e']} kgCO2e")
    m5.metric("Scope 1/3 (Process)", f"{footprint['scope1_3_ghg_kgco2e']} kgCO2e")
    m6.metric("Total Emissions", f"{footprint['total_ghg_kgco2e']} kgCO2e")

    st.divider()

    st.write("**Where you stand:**")
    best = rubric["best_case_ghg_per_kg"]
    worst = rubric["worst_case_ghg_per_kg"]
    actual = rubric["actual_ghg_per_kg"]
    position_pct = (worst - actual) / (worst - best) if worst != best else 1.0
    st.progress(max(0.0, min(1.0, position_pct)))
    st.caption(f"Best case: {best} kgCO2e/kg  |  Your footprint: {actual} kgCO2e/kg  |  Worst case: {worst} kgCO2e/kg")

    st.divider()

    st.subheader("Analysis & Recommendations")
    st.write(result["explanation"])

    st.divider()

    full_report = generate_report_markdown(sme_id)
    st.download_button(
        label="Download Full Report (Markdown)",
        data=full_report,
        file_name=f"compliance_report_{sme_id}.md",
        mime="text/markdown",
    )

    with st.expander("View data sources & methodology"):
        st.write("""
        - Scope 2 grid factor: Google's Regional Carbon-Free Energy dataset (BigQuery public dataset)
        - Scope 1/3 process factors: Carbonfact Open Source LCA Database (CC-BY-SA 4.0)
        - Scoring method: Position between the best and worst real emission profiles found in the sourced dataset
        """)
