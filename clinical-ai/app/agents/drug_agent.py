from app.rag.retriever import retrieve_drugs
from app.config.settings import TOP_K_DRUGS
class DrugAgent:
   def run(self, diagnosis_output, patient=None):
       disease = diagnosis_output.get("diagnosis", "")
       severity = diagnosis_output.get("severity", "")
       symptoms = patient.symptoms if patient else []
       if not disease:
           return {
               "medications": [],
               "warnings": ["No diagnosis available"],
               "contraindications": []
           }
       # Better query
       query = f"{disease} treatment {severity} {' '.join(symptoms)}"
       matched_drugs = retrieve_drugs(query, k=TOP_K_DRUGS)
       if not matched_drugs:
           return {
               "medications": [],
               "warnings": ["No matching drugs found"],
               "contraindications": []
           }
       medications = []
       warnings = []
       contraindications = []
       for drug in matched_drugs:
           dose = drug.get("dosage_range", {})
           medications.append({
               "name": drug["name"],
               "dose": f"{dose.get('min')} - {dose.get('max')} {dose.get('unit')}"
           })
           # Keep ALL interaction info (do not filter here)
           for inter in drug.get("interactions", []):
               warnings.append(
                   f"{drug['name']} + {inter['drug']} ({inter['severity']}) → {inter['effect']}"
               )
           contraindications.extend(drug.get("contraindications", []))
       return {
           "medications": medications,
           "warnings": warnings,
           "contraindications": list(set(contraindications))
       }