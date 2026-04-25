from app.core.orchestrator import Orchestrator

class Patient:
   def __init__(self, symptoms, labs):
       self.symptoms = symptoms
       self.labs = labs

if __name__ == "__main__":
   patient = Patient(
       symptoms=["chest pain", "radiating arm pain", "nausea"],
       labs={
           "WBC": 12000,
           "O2": 88,
           "lactate": 5
       }
   )
   orchestrator = Orchestrator()
   result = orchestrator.run(patient)
   print("\nFINAL OUTPUT:\n")
   print(result)