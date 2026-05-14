# test_orchestrator.py

"""
End-to-end test for the Clinical Orchestrator.
Runs the full pipeline:
  1. Symptom Analyzer + Lab Interpreter (parallel)
  2. Diagnosis arbitration
  3. Treatment Planner
  4. Drug Interaction Checker
  5. Final consolidated report
"""

import json
from orchestrator import ClinicalOrchestrator


def run_case(case_id, chief_complaint, symptoms, lab_results, current_medications):
    print(f"\n{'=' * 70}")
    print(f"  TEST CASE {case_id}")
    print(f"  Chief Complaint : {chief_complaint}")
    print(f"  Symptoms        : {symptoms}")
    print(f"  Lab Results     : {lab_results}")
    print(f"  Medications     : {current_medications}")
    print(f"{'=' * 70}")

    orchestrator = ClinicalOrchestrator()

    report = orchestrator.run(
        chief_complaint=chief_complaint,
        symptoms=symptoms,
        lab_results=lab_results,
        current_medications=current_medications,
    )

    print("\n" + "=" * 70)
    print("  FINAL REPORT")
    print("=" * 70)
    print(json.dumps(report, indent=2, default=str))
    return report


if __name__ == "__main__":

    # ------------------------------------------------------------------
    # CASE 1: Dengue-like presentation
    # ------------------------------------------------------------------
    run_case(
        case_id=1,
        chief_complaint="High fever with body ache",
        symptoms=["fever", "body pain", "headache", "chills"],
        lab_results={
            "platelets": 80000,
            "hematocrit": 52,
            "sodium": 138,
        },
        current_medications=["Ibuprofen"],
    )

    # ------------------------------------------------------------------
    # CASE 2: Respiratory infection
    # ------------------------------------------------------------------
    run_case(
        case_id=2,
        chief_complaint="Cough and shortness of breath",
        symptoms=["fever", "productive cough", "chest pain", "shortness of breath"],
        lab_results={
            "oxygen": 89,
            "hemoglobin": 13,
            "platelets": 250000,
        },
        current_medications=["Aspirin", "Metformin"],
    )

    # ------------------------------------------------------------------
    # CASE 3: Weakness (low confidence expected)
    # ------------------------------------------------------------------
    run_case(
        case_id=3,
        chief_complaint="General weakness",
        symptoms=["weakness", "fatigue"],
        lab_results={
            "hemoglobin": 9,
            "platelets": 140000,
            "sodium": 142,
        },
        current_medications=[],
    )
