from app.rag.retriever import retrieve_drugs
class DrugAgent:
   def run(self, diagnosis_output, patient=None):
       disease = diagnosis_output.get("diagnosis", "")
       if not disease:
           return {
               "medications": [],
               "warnings": ["No diagnosis available"],
               "contraindications": []
           }
       # 🔥 RAG retrieval
       matched_drugs = retrieve_drugs(disease, k=5)
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
           for inter in drug.get("interactions", []):
               warnings.append(
                   f"{drug['name']} + {inter['drug']} → {inter['effect']}"
               )
           contraindications.extend(drug.get("contraindications", []))
       return {
           "medications": medications,
           "warnings": list(set(warnings)),
           "contraindications": list(set(contraindications))
       }