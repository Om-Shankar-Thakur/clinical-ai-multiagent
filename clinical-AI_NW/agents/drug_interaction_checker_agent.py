from config.prompts import DRUG_INTERACTION_CHECKER_SYSTEM_PROMPT
from llm.gemini_client import GeminiLLM


class DrugInteractionCheckerAgent:
    """
    Uses an LLM to review medication safety risks.
    Flags interactions, contraindications, or allergy risks.
    """

    def __init__(self):
        self.llm = GeminiLLM()

    def check(self, diagnosis, current_medications, proposed_plan):
        user_prompt = {
            "diagnosis": diagnosis,
            "current_medications": current_medications,
            "proposed_management_options": [
                opt.get("option", "")
                for opt in proposed_plan.get("management_options", [])
            ]
        }

        response = self.llm.generate(
            system_prompt=DRUG_INTERACTION_CHECKER_SYSTEM_PROMPT,
            user_prompt=str(user_prompt)
        )

        return response