# orchestrator.py

"""
Clinical AI Orchestrator
========================
Coordinates all agents according to the required execution flow:

1. Symptom Analyzer & Lab Interpreter run IN PARALLEL
2. Results are combined; a diagnosis is arbitrated
3. Treatment Planner generates candidate plans
4. Drug Interaction Checker validates plans and flags conflicts
5. Orchestrator produces final output with confidence scores
   and dissenting opinions (if agents disagree)
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from agents.symptom_analyzer import SymptomAnalyzerAgent
from agents.lab_interpreter_agent import LabInterpreterAgent
from agents.treatment_planner_agent import TreatmentPlannerAgent
from agents.drug_interaction_checker_agent import DrugInteractionCheckerAgent

logger = logging.getLogger(__name__)


class ClinicalOrchestrator:
    """
    Runs the full clinical decision-support pipeline.
    All final decisions remain with the supervising clinician.
    """

    def __init__(self):
        self.symptom_agent = SymptomAnalyzerAgent()
        self.lab_agent = LabInterpreterAgent()
        self.treatment_agent = TreatmentPlannerAgent()
        self.drug_interaction_agent = DrugInteractionCheckerAgent()

    # ------------------------------------------------------------------ #
    #  PUBLIC ENTRY POINT                                                  #
    # ------------------------------------------------------------------ #
    def run(
        self,
        chief_complaint: str,
        symptoms: list[str],
        lab_results: dict,
        current_medications: list[str] | None = None,
    ) -> dict:
        """
        Execute the full pipeline and return a consolidated clinical report.

        Parameters
        ----------
        chief_complaint : str
            Patient's chief complaint in free text.
        symptoms : list[str]
            List of reported symptoms.
        lab_results : dict
            Lab name → numeric value pairs (e.g. {"platelets": 80000}).
        current_medications : list[str] | None
            Medications the patient is currently taking.

        Returns
        -------
        dict  – Final orchestrated clinical report.
        """
        current_medications = current_medications or []

        # ============================================================
        # STEP 1: PARALLEL EXECUTION — Symptom Analyzer + Lab Interpreter
        # ============================================================
        print("\n[ORCHESTRATOR] Step 1 — Running Symptom Analyzer & Lab Interpreter in parallel …")

        symptom_output, lab_output = self._run_parallel(
            chief_complaint, symptoms, lab_results
        )

        print("[ORCHESTRATOR] ✓ Both agents completed.")

        # ============================================================
        # STEP 2: DIAGNOSIS ARBITRATION
        # ============================================================
        print("[ORCHESTRATOR] Step 2 — Arbitrating diagnosis from combined results …")

        diagnosis_output, dissenting_opinions = self._arbitrate_diagnosis(
            symptom_output, lab_output
        )

        primary_dx = diagnosis_output["final"]["diagnosis"]
        confidence = diagnosis_output["final"]["confidence"]

        print(f"[ORCHESTRATOR] ✓ Primary diagnosis: {primary_dx} (confidence: {confidence:.2f})")

        # ============================================================
        # STEP 3: TREATMENT PLANNER
        # ============================================================
        print("[ORCHESTRATOR] Step 3 — Generating treatment plan …")

        treatment_output = self.treatment_agent.analyze(
            diagnosis_output=diagnosis_output,
            lab_output=lab_output,
            drug_safety_output=None,       # drug check happens AFTER
        )

        print("[ORCHESTRATOR] ✓ Treatment plan generated.")

        # ============================================================
        # STEP 4: DRUG INTERACTION CHECKER
        # ============================================================
        print("[ORCHESTRATOR] Step 4 — Checking drug interactions …")

        drug_check_output = self._check_drug_interactions(
            diagnosis=primary_dx,
            current_medications=current_medications,
            treatment_plan=treatment_output,
        )

        print("[ORCHESTRATOR] ✓ Drug interaction check completed.")

        # ============================================================
        # STEP 5: FINAL CONSOLIDATED OUTPUT
        # ============================================================
        print("[ORCHESTRATOR] Step 5 — Assembling final report …\n")

        final_report = self._build_final_report(
            chief_complaint=chief_complaint,
            symptoms=symptoms,
            lab_results=lab_results,
            current_medications=current_medications,
            symptom_output=symptom_output,
            lab_output=lab_output,
            diagnosis_output=diagnosis_output,
            treatment_output=treatment_output,
            drug_check_output=drug_check_output,
            dissenting_opinions=dissenting_opinions,
        )

        return final_report

    # ------------------------------------------------------------------ #
    #  STEP 1 — PARALLEL EXECUTION                                        #
    # ------------------------------------------------------------------ #
    def _run_parallel(self, chief_complaint, symptoms, lab_results):
        """Run Symptom Analyzer and Lab Interpreter concurrently."""
        results = {}

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                executor.submit(
                    self.symptom_agent.analyze, chief_complaint, symptoms
                ): "symptom",
                executor.submit(
                    self.lab_agent.analyze, lab_results
                ): "lab",
            }

            for future in as_completed(futures):
                agent_name = futures[future]
                try:
                    results[agent_name] = future.result()
                except Exception as e:
                    logger.error("Agent '%s' failed: %s", agent_name, e)
                    results[agent_name] = self._agent_error_fallback(agent_name, e)

        return results["symptom"], results["lab"]

    # ------------------------------------------------------------------ #
    #  STEP 2 — DIAGNOSIS ARBITRATION                                      #
    # ------------------------------------------------------------------ #
    def _arbitrate_diagnosis(self, symptom_output, lab_output):
        """
        Merge Symptom Analyzer and Lab Interpreter results into a single
        authoritative diagnosis with confidence and dissenting opinions.

        Strategy
        --------
        1. Score each disease by combining symptom score + lab score.
        2. Pick the top-scoring disease as primary diagnosis.
        3. Collect dissenting opinions where agents disagree on ranking.
        """
        # -- Symptom candidates --
        symptom_candidates = {}
        for entry in symptom_output.get("differential_diagnosis", []):
            disease = entry["disease"].lower()
            symptom_candidates[disease] = {
                "symptom_score": entry["score"],
                "confidence": entry["reasoning"]["confidence"],
                "matched_symptoms": entry["reasoning"]["matched_symptoms"],
                "missing_symptoms": entry["reasoning"]["missing_symptoms"],
                "description": entry.get("description", ""),
            }

        # -- Lab candidates --
        lab_candidates = {}
        for entry in lab_output.get("lab_hypotheses", []):
            disease = entry["disease"].lower()
            lab_candidates[disease] = {
                "lab_score": entry["score"],
                "lab_support": entry["lab_support"],
                "matched_lab_patterns": entry["matched_lab_patterns"],
            }

        # -- Merge --
        all_diseases = set(symptom_candidates.keys()) | set(lab_candidates.keys())

        merged = []
        for disease in all_diseases:
            sym = symptom_candidates.get(disease, {})
            lab = lab_candidates.get(disease, {})

            symptom_score = sym.get("symptom_score", 0.0)
            lab_score = lab.get("lab_score", 0.0)

            # Weighted combination: 55 % symptoms, 45 % lab
            combined_score = 0.55 * symptom_score + 0.45 * lab_score

            merged.append({
                "disease": disease,
                "combined_score": round(combined_score, 3),
                "symptom_score": round(symptom_score, 3),
                "lab_score": round(lab_score, 3),
                "lab_support": lab.get("lab_support", "no lab data"),
                "symptom_confidence": sym.get("confidence", "none"),
                "matched_symptoms": sym.get("matched_symptoms", []),
                "missing_symptoms": sym.get("missing_symptoms", []),
                "matched_lab_patterns": lab.get("matched_lab_patterns", []),
                "description": sym.get("description", ""),
            })

        merged.sort(key=lambda x: x["combined_score"], reverse=True)

        # -- Primary diagnosis --
        if merged:
            top = merged[0]
            primary_diagnosis = top["disease"]
            primary_confidence = top["combined_score"]
            uncertainty = primary_confidence < 0.6
        else:
            primary_diagnosis = None
            primary_confidence = 0.0
            uncertainty = True

        diagnosis_output = {
            "final": {
                "diagnosis": primary_diagnosis,
                "confidence": round(primary_confidence, 3),
                "uncertainty": uncertainty,
            },
            "ranked_candidates": merged[:5],
        }

        # -- Dissenting opinions --
        dissenting = []
        if len(merged) >= 2:
            for alt in merged[1:4]:                    # top 3 alternatives
                # Check if symptom-based ranking disagrees with lab-based
                symptom_rank = self._rank_position(merged, alt["disease"], "symptom_score")
                lab_rank = self._rank_position(merged, alt["disease"], "lab_score")

                if abs(symptom_rank - lab_rank) >= 2:
                    dissenting.append({
                        "disease": alt["disease"],
                        "symptom_rank": symptom_rank + 1,
                        "lab_rank": lab_rank + 1,
                        "note": (
                            f"Symptom analysis ranks this #{symptom_rank + 1} "
                            f"but lab evidence ranks it #{lab_rank + 1}."
                        ),
                    })

        return diagnosis_output, dissenting

    # ------------------------------------------------------------------ #
    #  STEP 4 — DRUG INTERACTION CHECK                                     #
    # ------------------------------------------------------------------ #
    def _check_drug_interactions(self, diagnosis, current_medications, treatment_plan):
        """
        Run the Drug Interaction Checker on the proposed treatment plan.
        Returns parsed JSON or a raw-string fallback.
        """
        if not current_medications:
            return {
                "warnings": [],
                "severity": "low",
                "review_required": False,
                "note": "No current medications provided; interaction check skipped.",
            }

        try:
            raw = self.drug_interaction_agent.check(
                diagnosis=diagnosis,
                current_medications=current_medications,
                proposed_plan=treatment_plan,
            )
            # The agent returns raw LLM text; try to parse as JSON
            return self._safe_parse_json(raw)
        except Exception as e:
            logger.error("Drug interaction check failed: %s", e)
            return {
                "warnings": ["Drug interaction check encountered an error."],
                "severity": "unknown",
                "review_required": True,
                "error": str(e),
            }

    # ------------------------------------------------------------------ #
    #  STEP 5 — FINAL REPORT                                               #
    # ------------------------------------------------------------------ #
    def _build_final_report(
        self,
        chief_complaint,
        symptoms,
        lab_results,
        current_medications,
        symptom_output,
        lab_output,
        diagnosis_output,
        treatment_output,
        drug_check_output,
        dissenting_opinions,
    ) -> dict:
        """Assemble the consolidated clinical report."""

        return {
            # — Input summary —
            "patient_input": {
                "chief_complaint": chief_complaint,
                "symptoms": symptoms,
                "lab_results": lab_results,
                "current_medications": current_medications,
            },

            # — Diagnosis —
            "diagnosis": diagnosis_output["final"],
            "ranked_candidates": diagnosis_output.get("ranked_candidates", []),

            # — Lab signals —
            "lab_signals": lab_output.get("lab_signals", []),
            "critical_flags": lab_output.get("critical_flags", []),

            # — Treatment plan —
            "treatment_plan": {
                "status": treatment_output.get("recommendation_status"),
                "management_options": treatment_output.get("management_options", []),
                "uncertainty_notes": treatment_output.get("uncertainty_notes", []),
            },

            # — Drug safety —
            "drug_interaction_check": drug_check_output,

            # — Dissenting opinions —
            "dissenting_opinions": dissenting_opinions,

            # — Meta —
            "clinician_action_required": True,
            "disclaimer": (
                "This output is a clinical decision support aid only. "
                "It does NOT constitute a prescription or medical order. "
                "All treatment decisions must be made by a licensed clinician "
                "after independent evaluation."
            ),
        }

    # ------------------------------------------------------------------ #
    #  UTILITIES                                                           #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _rank_position(merged_list, disease, score_key):
        """Return the rank (0-based) of *disease* when sorted by *score_key*."""
        ordered = sorted(merged_list, key=lambda x: x[score_key], reverse=True)
        for i, entry in enumerate(ordered):
            if entry["disease"] == disease:
                return i
        return len(ordered)

    @staticmethod
    def _safe_parse_json(text: str) -> dict:
        """Try to parse JSON from LLM output, tolerating markdown fences."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(
                line for line in cleaned.splitlines()
                if not line.strip().startswith("```")
            )
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {
                "raw_response": text,
                "warnings": ["Could not parse drug interaction response as JSON."],
                "severity": "unknown",
                "review_required": True,
            }

    @staticmethod
    def _agent_error_fallback(agent_name, error):
        """Return a safe empty structure when an agent fails."""
        if agent_name == "symptom":
            return {"chief_complaint": None, "differential_diagnosis": []}
        elif agent_name == "lab":
            return {"lab_hypotheses": [], "critical_flags": [], "lab_signals": []}
        return {}
