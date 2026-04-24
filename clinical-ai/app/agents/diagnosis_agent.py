from app.prompts.diagnosis_prompt import build_diagnosis_prompt
from app.services.openai_service import OpenAIService
from app.safety.guardrails import validate_llm_output
from app.rag.retriever import retrieve

import json

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
            return {
                "diagnosis": "Insufficient Data",
                "reasoning": "Not enough confidence for clinical reasoning",
                "severity": "unknown",
                "next_steps": "Collect more patient data"
            }

        # Step 1: Better semantic query
        query = f"""
            Disease: {top['name']}
            Symptoms: {', '.join(top['matched_symptoms'])}
            Lab alerts: {', '.join(lab_result.get('alerts', []))}
        """

        # Step 2: Retrieve
        docs = retrieve(query, k=3)

        # Step 3: Safe context
        context = "\n".join([
            doc.get("text", str(doc))[:300]
            for doc in docs
        ])

        # Step 4: Prompt with RAG
        prompt = build_diagnosis_prompt(top, lab_result, uncertainty, context)
        try:
            response = self.llm.generate(prompt)
            print("RAW LLM OUTPUT:\n", response)

            # Guardrails
            is_valid, safe_output = validate_llm_output(response)
            if not is_valid:
                return {
                    "diagnosis": "Unavailable",
                    "reasoning": safe_output,
                    "severity": "unknown",
                    "next_steps": "Consult a medical professional"
                }
            return safe_output
        except Exception:
            return {
                "diagnosis": "System Error",
                "reasoning": "AI reasoning unavailable",
                "severity": "unknown",
                "next_steps": "Retry or fallback to manual review"
            }
    