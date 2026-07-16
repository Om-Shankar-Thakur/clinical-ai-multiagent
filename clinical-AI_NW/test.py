# test.py
# Manual smoke test for the Drug Interaction Checker agent (needs GEMINI_API_KEY).
# Run: python test.py

from agents.drug_interaction_checker_agent import DrugInteractionCheckerAgent


def test_drug_interaction_checker_llm():
    agent = DrugInteractionCheckerAgent()

    diagnosis = "Dengue"
    current_medications = ["Ibuprofen"]
    proposed_plan = {
        "management_options": [
            {
                "option": "The clinician may consider supportive care and pain control if required.",
                "typical_dosing_range": None,
                "monitoring": "Monitor platelet count and hematocrit.",
                "follow_up": "Reassess clinically.",
            }
        ]
    }

    result = agent.check(
        diagnosis=diagnosis,
        current_medications=current_medications,
        proposed_plan=proposed_plan,
    )

    print("\n=== DRUG INTERACTION CHECK (LLM) RESULT ===\n")
    print(result)


if __name__ == "__main__":
    test_drug_interaction_checker_llm()
