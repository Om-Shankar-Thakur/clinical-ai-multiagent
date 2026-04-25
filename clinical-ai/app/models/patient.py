class Patient:
   def __init__(
       self,
       symptoms: list,
       labs: dict,
       medications: list = None,
       history: list = None,
       allergies: list = None,
       age: int = None,
       weight: float = None
   ):
       self.symptoms = symptoms or []
       self.labs = labs or {}
       self.medications = medications or []   # current meds
       self.history = history or []           # comorbidities
       self.allergies = allergies or []
       self.age = age
       self.weight = weight
   def to_dict(self):
       return {
           "symptoms": self.symptoms,
           "labs": self.labs,
           "medications": self.medications,
           "history": self.history,
           "allergies": self.allergies,
           "age": self.age,
           "weight": self.weight
       }