# streamlit_app.py

"""
Streamlit frontend for the Clinical AI Multi-Agent System.
Collects patient data and displays the orchestrator's structured report.
"""

import streamlit as st
import requests
import json

# ------------------------------------------------------------------ #
#  CONFIG
# ------------------------------------------------------------------ #
API_URL = "http://localhost:8000"

AVAILABLE_SYMPTOMS = [
    "fever", "cough", "productive cough", "dry cough", "chest pain",
    "shortness of breath", "headache", "body pain", "chills", "fatigue",
    "weakness", "nausea", "vomiting", "abdominal pain", "diarrhea",
    "rash", "joint pain", "sore throat", "wheezing", "palpitations",
    "leg swelling", "confusion", "polyuria", "polydipsia", "weight loss",
    "night sweats", "loss of taste", "loss of smell",
]

AVAILABLE_LABS = {
    "platelets": {"unit": "cells/µL", "placeholder": "e.g. 150000"},
    "hemoglobin": {"unit": "g/dL", "placeholder": "e.g. 13.5"},
    "hematocrit": {"unit": "%", "placeholder": "e.g. 45"},
    "sodium": {"unit": "mEq/L", "placeholder": "e.g. 140"},
    "oxygen": {"unit": "% SpO2", "placeholder": "e.g. 97"},
    "glucose": {"unit": "mg/dL", "placeholder": "e.g. 110"},
}

# ------------------------------------------------------------------ #
#  PAGE CONFIG
# ------------------------------------------------------------------ #
st.set_page_config(
    page_title="MedOrchestrator - A multi-agent Clinical AI — Decision Support",
    page_icon="🏥",
    layout="wide",
)


# ------------------------------------------------------------------ #
#  CUSTOM CSS
# ------------------------------------------------------------------ #
st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; }
    .stAlert { margin-top: 0.5rem; }
    .metric-card {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 1rem 1.2rem;
        border-left: 4px solid #4a90d9;
        margin-bottom: 0.8rem;
    }
    .metric-card h4 { margin: 0 0 0.3rem 0; color: #333; }
    .metric-card p { margin: 0; color: #555; font-size: 0.95rem; }
    .critical-flag {
        background: #fff3f3;
        border-left: 4px solid #e74c3c;
        border-radius: 6px;
        padding: 0.6rem 1rem;
        margin-bottom: 0.4rem;
    }
    .drug-warning {
        background: #fff8e1;
        border-left: 4px solid #f39c12;
        border-radius: 6px;
        padding: 0.6rem 1rem;
        margin-bottom: 0.4rem;
    }
    .dissent-card {
        background: #f0f4ff;
        border-left: 4px solid #8e44ad;
        border-radius: 6px;
        padding: 0.6rem 1rem;
        margin-bottom: 0.4rem;
    }
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------ #
#  HEADER
# ------------------------------------------------------------------ #
st.title("🏥 MedOrchestrator")
st.caption(
    "**Multi-Agent Clinical Decision Support** · Enter patient data below. The system will run symptom analysis, "
    "lab interpretation, treatment planning, and drug-interaction checks in a coordinated pipeline."
)
st.divider()

# ------------------------------------------------------------------ #
#  SIDEBAR — Patient Input Form
# ------------------------------------------------------------------ #
with st.sidebar:
    st.header("📋 Patient Data")

    chief_complaint = st.text_input(
        "Chief Complaint *",
        placeholder="e.g. High fever with body ache",
    )

    st.subheader("Symptoms")
    selected_symptoms = st.multiselect(
        "Select reported symptoms",
        options=AVAILABLE_SYMPTOMS,
        default=[],
    )
    custom_symptom = st.text_input(
        "Add custom symptom (optional)",
        placeholder="e.g. blurred vision",
    )
    if custom_symptom:
        selected_symptoms.append(custom_symptom.strip().lower())

    st.subheader("Lab Results")
    st.caption("Leave blank to skip a lab parameter.")
    lab_results = {}
    for lab_name, info in AVAILABLE_LABS.items():
        val = st.text_input(
            f"{lab_name.title()} ({info['unit']})",
            placeholder=info["placeholder"],
            key=f"lab_{lab_name}",
        )
        if val:
            try:
                lab_results[lab_name] = float(val)
            except ValueError:
                st.warning(f"Invalid number for {lab_name}")

    st.subheader("Current Medications")
    medications_input = st.text_area(
        "Enter medications (one per line)",
        placeholder="e.g.\nIbuprofen\nMetformin",
        height=100,
    )
    current_medications = [
        m.strip() for m in medications_input.splitlines() if m.strip()
    ]

    st.divider()
    analyze_btn = st.button("🔍 Analyze Patient", type="primary", use_container_width=True)

# ------------------------------------------------------------------ #
#  MAIN AREA — Results
# ------------------------------------------------------------------ #

def call_api(chief_complaint, symptoms, lab_results, current_medications):
    """Send patient data to the FastAPI backend."""
    payload = {
        "chief_complaint": chief_complaint,
        "symptoms": symptoms,
        "lab_results": lab_results,
        "current_medications": current_medications,
    }
    resp = requests.post(f"{API_URL}/analyze", json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()


def render_diagnosis(report):
    """Render primary diagnosis card."""
    dx = report.get("diagnosis", {})
    diagnosis = dx.get("diagnosis", "Unknown")
    confidence = dx.get("confidence", 0)
    uncertainty = dx.get("uncertainty", True)

    col1, col2, col3 = st.columns(3)
    col1.metric("Primary Diagnosis", diagnosis.title())
    col2.metric("Confidence Score", f"{confidence:.1%}")
    col3.metric("Uncertainty Flag", "⚠️ Yes" if uncertainty else "✅ No")


def render_ranked_candidates(report):
    """Render differential diagnosis table."""
    candidates = report.get("ranked_candidates", [])
    if not candidates:
        st.info("No differential candidates found.")
        return

    for i, c in enumerate(candidates, 1):
        with st.expander(
            f"#{i}  {c['disease'].title()}  —  Score: {c['combined_score']:.3f}  |  "
            f"Symptom: {c['symptom_confidence']}  |  Lab: {c['lab_support']}",
            expanded=(i == 1),
        ):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Matched Symptoms**")
                if c["matched_symptoms"]:
                    for s in c["matched_symptoms"]:
                        st.markdown(f"- ✅ {s}")
                else:
                    st.caption("None")
            with col2:
                st.markdown("**Missing Symptoms**")
                if c["missing_symptoms"]:
                    for s in c["missing_symptoms"]:
                        st.markdown(f"- ❓ {s}")
                else:
                    st.caption("None")

            st.markdown("**Matched Lab Patterns**")
            if c["matched_lab_patterns"]:
                for p in c["matched_lab_patterns"]:
                    st.markdown(f"- 🔬 {p}")
            else:
                st.caption("No matching lab patterns")

            if c.get("description"):
                st.caption(c["description"])

            st.markdown(
                f"📊 Symptom Score: `{c['symptom_score']:.3f}` &nbsp;|&nbsp; "
                f"Lab Score: `{c['lab_score']:.3f}` &nbsp;|&nbsp; "
                f"Combined: `{c['combined_score']:.3f}`"
            )


def render_lab_signals(report):
    """Render lab signals and critical flags."""
    critical = report.get("critical_flags", [])
    signals = report.get("lab_signals", [])

    if critical:
        for flag in critical:
            st.markdown(
                f'<div class="critical-flag">🚨 <strong>CRITICAL:</strong> {flag}</div>',
                unsafe_allow_html=True,
            )

    if signals:
        non_critical = [s for s in signals if s not in critical]
        if non_critical:
            for s in non_critical:
                st.info(f"🔬 {s}")
    else:
        st.caption("No significant lab signals detected.")


def render_treatment_plan(report):
    """Render treatment plan options."""
    plan = report.get("treatment_plan", {})
    status = plan.get("status", "unknown")

    status_colors = {
        "draft_for_clinician_review": "🟢",
        "insufficient_confidence": "🟡",
        "generation_failed": "🔴",
    }
    st.markdown(f"**Status:** {status_colors.get(status, '⚪')} {status.replace('_', ' ').title()}")

    options = plan.get("management_options", [])
    if options:
        for i, opt in enumerate(options, 1):
            st.markdown(f'<div class="metric-card">', unsafe_allow_html=True)
            st.markdown(f"**Option {i}:** {opt.get('option', 'N/A')}")
            if opt.get("typical_dosing_range"):
                st.markdown(f"💊 **Typical Dosing Range:** {opt['typical_dosing_range']}")
            st.markdown(f"📋 **Monitoring:** {opt.get('monitoring', 'N/A')}")
            st.markdown(f"📅 **Follow-up:** {opt.get('follow_up', 'N/A')}")
            st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.warning("No management options generated. Manual clinician review required.")

    notes = plan.get("uncertainty_notes", [])
    if notes:
        for note in notes:
            st.warning(f"⚠️ {note}")


def render_drug_interactions(report):
    """Render drug interaction check results."""
    drug = report.get("drug_interaction_check", {})

    if drug.get("note"):
        st.caption(drug["note"])
        return

    warnings = drug.get("warnings", [])
    severity = drug.get("severity", "unknown")
    review = drug.get("review_required", False)

    severity_colors = {"low": "🟢", "medium": "🟡", "high": "🔴", "unknown": "⚪"}
    st.markdown(
        f"**Severity:** {severity_colors.get(severity, '⚪')} {severity.upper()} &nbsp;|&nbsp; "
        f"**Review Required:** {'Yes' if review else 'No'}"
    )

    if warnings:
        for w in warnings:
            st.markdown(
                f'<div class="drug-warning">⚠️ {w}</div>',
                unsafe_allow_html=True,
            )
    else:
        st.success("No drug interaction warnings.")


def render_dissenting_opinions(report):
    """Render disagreements between agents."""
    dissent = report.get("dissenting_opinions", [])
    if not dissent:
        st.success("All agents are in agreement.")
        return

    for d in dissent:
        st.markdown(
            f'<div class="dissent-card">'
            f'🔀 <strong>{d["disease"].title()}</strong>: {d["note"]}'
            f'</div>',
            unsafe_allow_html=True,
        )


# ------------------------------------------------------------------ #
#  MAIN LOGIC
# ------------------------------------------------------------------ #
if analyze_btn:
    # Validation
    if not chief_complaint.strip():
        st.error("Please enter a chief complaint.")
        st.stop()
    if not selected_symptoms:
        st.error("Please select at least one symptom.")
        st.stop()

    with st.spinner("🔄 Running clinical pipeline — this may take a moment …"):
        try:
            report = call_api(
                chief_complaint=chief_complaint,
                symptoms=selected_symptoms,
                lab_results=lab_results,
                current_medications=current_medications,
            )
            st.session_state["report"] = report
        except requests.exceptions.ConnectionError:
            st.error(
                "Cannot connect to backend. Make sure the FastAPI server is running:\n\n"
                "```\nuvicorn server:app --reload --port 8000\n```"
            )
            st.stop()
        except requests.exceptions.HTTPError as e:
            st.error(f"Backend error: {e.response.text}")
            st.stop()
        except Exception as e:
            st.error(f"Unexpected error: {e}")
            st.stop()

# Display results if available
if "report" in st.session_state:
    report = st.session_state["report"]

    # --- Diagnosis ---
    st.header("🩺 Diagnosis")
    render_diagnosis(report)

    # --- Critical flags (show prominently) ---
    if report.get("critical_flags"):
        st.header("🚨 Critical Alerts")
        render_lab_signals(report)
    else:
        with st.expander("🔬 Lab Signals"):
            render_lab_signals(report)

    # --- Differential Diagnosis ---
    st.header("📊 Differential Diagnosis")
    render_ranked_candidates(report)

    # --- Treatment Plan ---
    st.header("💊 Treatment Plan")
    render_treatment_plan(report)

    # --- Drug Interactions ---
    st.header("⚠️ Drug Interaction Check")
    render_drug_interactions(report)

    # --- Dissenting Opinions ---
    st.header("🔀 Dissenting Opinions")
    render_dissenting_opinions(report)

    # --- Disclaimer ---
    st.divider()
    st.caption(report.get("disclaimer", ""))

    # --- Raw JSON ---
    with st.expander("📄 View Raw JSON Report"):
        st.json(report)

else:
    # Landing state
    st.info("👈 Enter patient data in the sidebar and click **Analyze Patient** to begin.")
