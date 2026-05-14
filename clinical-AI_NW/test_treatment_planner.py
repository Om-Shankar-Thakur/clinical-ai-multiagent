# test_treatment_planner.py

from agents.treatment_planner_agent import TreatmentPlannerAgent

# ----------------------------
# MOCK UPSTREAM AGENT OUTPUTS
# ----------------------------

# ✅ Example 1: Dengue (high confidence)
diagnosis_output = {
    "final": {
        "diagnosis": "Dengue",
        "confidence": 0.82,
        "uncertainty": False
    }
}

lab_output = {
    "critical_flags": [
        "Platelet count < 50,000",
        "Rising hematocrit"
    ]
}

drug_safety_output = {
    "warnings": [
        "Avoid NSAIDs due to bleeding risk"
    ]
}

# ----------------------------
# RUN TREATMENT PLANNER
# ----------------------------

agent = TreatmentPlannerAgent()

result = agent.analyze(
    diagnosis_output=diagnosis_output,
    lab_output=lab_output,
    drug_safety_output=drug_safety_output
)

print("\n=== TREATMENT PLANNER OUTPUT ===\n")
print(result)