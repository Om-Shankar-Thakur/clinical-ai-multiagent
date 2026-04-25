class ClinicalState:
   def __init__(self, patient):
       self.patient = patient
       # intermediate outputs
       self.symptoms = None
       self.labs = None
       self.diagnosis = None
       self.drugs = None
       self.drug_safety = None
       self.treatment = None
       # trace (for logging / debugging / Cosmos later)
       self.trace = {}