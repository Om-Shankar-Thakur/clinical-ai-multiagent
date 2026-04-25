from app.agents.symptom_agent import SymptomAgent
from app.agents.lab_agent import LabAgent
from app.agents.diagnosis_agent import DiagnosisAgent
from app.agents.drug_agent import DrugAgent
from app.agents.treatment_agent import TreatmentAgent
from app.agents.drug_interaction_agent import DrugInteractionAgent
from app.safety.guardrails import apply_guardrails
from app.models.clinical_state import ClinicalState

class Orchestrator:
   def __init__(self):
       self.symptom_agent = SymptomAgent()
       self.lab_agent = LabAgent()
       self.diagnosis_agent = DiagnosisAgent()
       self.drug_agent = DrugAgent()
       self.treatment_agent = TreatmentAgent()
       self.interaction_agent = DrugInteractionAgent()
       
   def run(self, patient):
        # ✅ Initialize shared state
        state = ClinicalState(patient)
        # -------------------------------
        # Phase 1: Signals
        # -------------------------------
        state.symptoms = self.symptom_agent.run(state.patient)
        state.labs = self.lab_agent.run(state.patient)
        # Trace
        state.trace["symptoms"] = state.symptoms
        state.trace["labs"] = state.labs
        # -------------------------------
        # Phase 2: Diagnosis
        # -------------------------------
        state.diagnosis = self.diagnosis_agent.run(
            state.symptoms,
            state.labs
        )
        state.trace["diagnosis"] = state.diagnosis
        # -------------------------------
        # Phase 3: Drug Retrieval
        # -------------------------------
        state.drugs = self.drug_agent.run(
            state.diagnosis["final"],   # keep for now (we'll refactor later)
            state.patient
        )
        state.trace["drugs"] = state.drugs
        # -------------------------------
        # Phase 4: Interaction Validation
        # -------------------------------
        state.drug_safety = self.interaction_agent.run(
            state.drugs,
            state.patient
        )
        state.trace["drug_safety"] = state.drug_safety
        # -------------------------------
        # Phase 5: Treatment Planning
        # -------------------------------
        treatment_input = {
            "medications": state.drug_safety["safe_medications"],
            "warnings": state.drug_safety["warnings"],
            "contraindications": []
        }
        state.treatment = self.treatment_agent.run(
            state.diagnosis,
            treatment_input,
            state.patient
        )
        state.trace["treatment"] = state.treatment
        # -------------------------------
        # Final Output (STANDARDIZED)
        # -------------------------------
        final_output = {
               "diagnosis": state.diagnosis,
               "treatment": state.treatment,
               "drug_safety": {
                   "safe": state.drug_safety["safe_medications"],
                   "blocked": state.drug_safety["blocked"],
                   "warnings": state.drug_safety["warnings"]
               },
               "trace": state.trace   # 🔥 IMPORTANT (for Cosmos later)
           }

        return apply_guardrails(final_output)