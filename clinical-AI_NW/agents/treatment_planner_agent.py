# agents/treatment_planner_agent.py

import json
import logging
from llm.azure_client import AzureLLM
from rag.retriever import SemanticRetriever
from config.prompts import TREATMENT_PLANNER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.4

DISCLAIMER = (
    "This output is a clinical decision support aid only. "
    "It does NOT constitute a prescription or medical order. "
    "All treatment decisions must be made by a licensed clinician "
    "after independent evaluation."
)


class TreatmentPlannerAgent:
    """
    Formats guideline-aligned MANAGEMENT OPTIONS for clinician review.
    This agent NEVER prescribes, NEVER decides treatment,
    and NEVER changes the diagnosis.
    """

    def __init__(self):
        self.llm = AzureLLM()
        self.retriever = SemanticRetriever()

    def analyze(
        self,
        diagnosis_output: dict,
        lab_output: dict,
        drug_safety_output: dict | None = None,
    ) -> dict:
        """
        Generate conservative, guideline-aligned management options.

        Inputs:
        - diagnosis_output: output from diagnosis / arbitration stage
        - lab_output: output from LabInterpreterAgent
        - drug_safety_output: rule-based interaction warnings

        Returns:
        - Structured management options for clinician review
        """

        # -----------------------------
        # Extract authoritative diagnosis
        # -----------------------------
        final_dx = diagnosis_output.get("final", {})

        diagnosis = final_dx.get("diagnosis")
        confidence = float(final_dx.get("confidence", 0.0))
        uncertainty = final_dx.get("uncertainty", True)

        critical_flags = lab_output.get("critical_flags", [])
        drug_warnings = (drug_safety_output or {}).get("warnings", [])

        # ------------------------------------------------
        # STEP 1: RULE-BASED CONFIDENCE GATING
        # ------------------------------------------------
        if not diagnosis or confidence < CONFIDENCE_THRESHOLD:
            return self._insufficient_confidence_response(
                diagnosis, confidence, critical_flags, drug_warnings
            )

        # ------------------------------------------------
        # STEP 2: RETRIEVE GUIDELINE CONTEXT (RAG)
        # ------------------------------------------------
        guideline_results = self.retriever.retrieve_guidelines(
            query=f"{diagnosis} treatment management guidelines",
            top_k=5
        )

        guideline_text = "\n---\n".join(
            g.get("text", "") for g in guideline_results if g.get("text")
        )

        # ------------------------------------------------
        # STEP 3: BUILD CONSTRAINED USER PROMPT
        # ------------------------------------------------
        user_prompt = f"""
Clinical Context:
- Primary Diagnosis: {diagnosis}
- Diagnostic Confidence: {confidence}
- Diagnostic Uncertainty: {uncertainty}
- Critical Lab Alerts: {json.dumps(critical_flags)}
- Drug Interaction Warnings: {json.dumps(drug_warnings)}

Retrieved Clinical Guideline Excerpts:
{guideline_text}

Generate conservative MANAGEMENT OPTIONS only.
Return JSON exactly as specified.
"""

        # ------------------------------------------------
        # STEP 4: CALL LLM (FORMATTING ONLY)
        # ------------------------------------------------
        try:
            raw_response = self.llm.generate(
                TREATMENT_PLANNER_SYSTEM_PROMPT,
                user_prompt
            )
            parsed = self._parse_response(raw_response)
        except Exception as e:
            logger.error("Treatment planning failed: %s", e)
            return self._generation_failed_response(
                diagnosis, confidence, critical_flags, drug_warnings
            )

        # ------------------------------------------------
        # STEP 5: ENFORCE SAFETY FIELDS (NON-OVERRIDABLE)
        # ------------------------------------------------
        return {
            "recommendation_status": "draft_for_clinician_review",
            "primary_diagnosis": diagnosis,
            "diagnosis_confidence": confidence,
            "management_options": parsed.get("management_options", []),
            "uncertainty_notes": parsed.get("uncertainty_notes", []),
            "critical_lab_alerts": critical_flags,
            "drug_interaction_warnings": drug_warnings,
            "clinician_action_required": True,
            "disclaimer": DISCLAIMER,
        }

    # ------------------------------------------------
    # SAFE FALLBACKS
    # ------------------------------------------------

    def _parse_response(self, raw: str) -> dict:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(
                line for line in cleaned.splitlines()
                if not line.strip().startswith("```")
            )
        return json.loads(cleaned)

    def _insufficient_confidence_response(
        self,
        diagnosis: str,
        confidence: float,
        critical_flags: list,
        drug_warnings: list,
    ) -> dict:
        return {
            "recommendation_status": "insufficient_confidence",
            "primary_diagnosis": diagnosis,
            "diagnosis_confidence": confidence,
            "management_options": [],
            "uncertainty_notes": [
                f"Diagnostic confidence ({confidence:.2f}) is below the threshold "
                f"({CONFIDENCE_THRESHOLD}). Further evaluation is required."
            ],
            "critical_lab_alerts": critical_flags,
            "drug_interaction_warnings": drug_warnings,
            "clinician_action_required": True,
            "disclaimer": DISCLAIMER,
        }

    def _generation_failed_response(
        self,
        diagnosis: str,
        confidence: float,
        critical_flags: list,
        drug_warnings: list,
    ) -> dict:
        return {
            "recommendation_status": "generation_failed",
            "primary_diagnosis": diagnosis,
            "diagnosis_confidence": confidence,
            "management_options": [],
            "uncertainty_notes": [
                "Treatment option generation failed. Manual clinician review required."
            ],
            "critical_lab_alerts": critical_flags,
            "drug_interaction_warnings": drug_warnings,
            "clinician_action_required": True,
            "disclaimer": DISCLAIMER,
        }