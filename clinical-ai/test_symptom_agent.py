from app.agents.symptom_agent import SymptomAgent
from app.agents.lab_agent import LabAgent
from app.agents.diagnosis_agent import DiagnosisAgent

class Patient:
   def __init__(self, symptoms, labs):
       self.symptoms = symptoms
       self.labs = labs
    
symptom_agent = SymptomAgent()
lab_agent = LabAgent()
diagnosis_agent = DiagnosisAgent()




patient = Patient(
    symptoms=["chest pain", "radiating arm pain", "nausea"],
    labs={"WBC": 9000, "O2": 88, "lactate": 5}
)



symptom_result = symptom_agent.run(patient)
lab_result = lab_agent.run(patient)

final_output = diagnosis_agent.run(symptom_result, lab_result)

print(final_output)