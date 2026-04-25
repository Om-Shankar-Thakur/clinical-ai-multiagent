from app.agents.symptom_agent import SymptomAgent

from app.agents.lab_agent import LabAgent

from app.agents.diagnosis_agent import DiagnosisAgent

from app.agents.drug_agent import DrugAgent

from app.agents.treatment_agent import TreatmentAgent


class Orchestrator:

    def __init__(self):

        self.symptom_agent = SymptomAgent()

        self.lab_agent = LabAgent()

        self.diagnosis_agent = DiagnosisAgent()

        self.drug_agent = DrugAgent()

        self.treatment_agent = TreatmentAgent()

    def run(self, patient):

        # Step 1: Symptoms

        symptom_results = self.symptom_agent.run(patient)

        # Step 2: Labs

        lab_results = self.lab_agent.run(patient)

        # Step 3: Diagnosis

        diagnosis = self.diagnosis_agent.run(symptom_results, lab_results)

        # Step 4: Drugs

        drugs = self.drug_agent.run(diagnosis["final"], patient)

        # Step 5: Treatment

        treatment = self.treatment_agent.run(diagnosis, drugs, patient)

        return {

            "diagnosis": diagnosis,

            "treatment": treatment

        }
 