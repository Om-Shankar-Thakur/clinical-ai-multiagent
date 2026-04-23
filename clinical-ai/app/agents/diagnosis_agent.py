from app.prompts.diagnosis_prompt import build_diagnosis_prompt
from app.services.openai_service import OpenAIService
from app.safety.guardrails import validate_llm_output

class DiagnosisAgent:

    def run(self, symptom_results, lab_result):
        for d in symptom_results:
            d["consistent"] = self.is_consistent(d["name"], lab_result)

        consistent = [d for d in symptom_results if d["consistent"]]

        if consistent:
            top = max(consistent, key=lambda x: x["confidence"])
            uncertainty = False
        else:
            # ⚠️ Lab–symptom conflict
            top = symptom_results[0]
            top["confidence"] = round(top["confidence"] * 0.5, 2)
            uncertainty = True

        final = {
            "diagnosis": top["name"],
            "confidence": top["confidence"],
            "severity": lab_result["severity"],
            "risk_score": lab_result["risk_score"],
            "alerts": lab_result["alerts"],
            "matched_symptoms": top["matched_symptoms"],
            "uncertainty": uncertainty,
            "explaination_type": "lab_driven" if uncertainty else "symptom-aligned",
            "reason": self.build_reason(top, lab_result, uncertainty)
        }

        symptom_results.sort(key=lambda x: x["confidence"], reverse=True)

        return {
            "final": final,
            "candidates": symptom_results
        }

    def is_consistent(self, disease, lab_result):
        alerts = " ".join(lab_result["alerts"]).lower()

        if "lactate" in alerts or "sepsis" in alerts:
            return any(
                key in disease.lower()
                for key in ["sepsis", "pneumonia", "infection", "influenza", "covid"]
            )

        if "oxygen" in alerts:
            return any(
                key in disease.lower()
                for key in ["pneumonia", "respiratory", "pulmonary"]
            )

        return True
    
    def __init__(self):
        self.llm = OpenAIService()

    def build_reason(self, top, lab_result, uncertainty):
        if not top or top["confidence"] < 0.2:
            return "Insufficient data for reliable clinical reasoning."
        prompt = build_diagnosis_prompt(top, lab_result, uncertainty)
        try:
            return self.llm.generate(prompt)
        except Exception as e:
            return "AI reasoning unavailable. Falling back to rule-based explanation."
