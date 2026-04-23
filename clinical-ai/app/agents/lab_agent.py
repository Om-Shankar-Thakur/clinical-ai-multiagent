class LabAgent:
   def run(self, patient):
       labs = patient.labs
       score = 0
       alerts = []
       # WBC check
       wbc = labs.get("WBC", 0)
       if wbc > 15000:
           score += 0.4
           alerts.append("High WBC (possible severe infection)")
       elif wbc > 11000:
           score += 0.2
       # Oxygen check
       o2 = labs.get("O2", labs.get("oxygen", 100))
       if o2 < 90:
           score += 0.4
           alerts.append("Low oxygen (critical)")
       elif o2 < 95:
           score += 0.2
       # Lactate (sepsis indicator)
       lactate = labs.get("lactate", 1)
       if lactate > 4:
           score += 0.4
           alerts.append("High lactate (sepsis risk)")
       # Final severity classification
       if score >= 0.7:
           severity = "critical"
       elif score >= 0.4:
           severity = "moderate"
       elif score > 0:
           severity = "mild"
       else:
           severity = "normal"
       return {
           "severity": severity,
           "risk_score": round(score, 2),
           "alerts": alerts
       }