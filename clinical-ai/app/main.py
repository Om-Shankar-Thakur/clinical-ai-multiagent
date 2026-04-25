from app.core.orchestrator import Orchestrator
from app.models.patient import Patient

def run_test_case():
   # Simulated patient
   patient = Patient(
       symptoms=["fever", "cough", "shortness of breath"],
       labs={
           "WBC": 16000,
           "O2": 88,
           "lactate": 5
       },
       medications=["Warfarin"],   # existing drug → interaction test
       history=["hypertension"],
       allergies=["penicillin"]
   )
   orchestrator = Orchestrator()
   result = orchestrator.run(patient)

   print("\n========== FINAL OUTPUT ==========\n")

   print("Diagnosis:")
   print(result["diagnosis"]["final"])

   print("\nTreatment Plan:")
   for step in result["treatment"]["treatment_plan"]:
       print("-", step)

   print("\nMonitoring:")
   for m in result["treatment"]["monitoring"]:
       print("-", m)

   print("\nDrug Safety:")
   print("Safe Drugs:", result["drug_safety"]["safe"])
   print("Warnings:", result["drug_safety"]["warnings"])
   print(result["disclaimer"])

if __name__ == "__main__":
   run_test_case()