class DiagnosisAgent:
   def run(self, symptom_results, lab_result):
       top_disease = None

       for d in symptom_results:
        d["consistent"] = self.is_consistent(d["name"], lab_result)
        
  
       for d in symptom_results:
            if d["consistent"]:
                top_disease = d
                break

       if not top_disease:
            top_disease = symptom_results[0]
       
       final = {
           "diagnosis": top_disease["name"],
           "confidence": top_disease["confidence"],
           "severity": lab_result["severity"],
           "risk_score": lab_result["risk_score"],
           "alerts": lab_result["alerts"],
           "matched_symptoms": top_disease["matched_symptoms"]
       }
       return final
   
   def is_consistent(self, disease, lab_result):
        alerts = " ".join(lab_result["alerts"]).lower()
        # infection signals
        if "lactate" in alerts or "sepsis" in alerts:
            return "infection" in disease.lower() or "sepsis" in disease.lower()
        # oxygen related
        if "oxygen" in alerts:
            return True  # allow broader match for now
        return True