from app.rag.retriever import retrieve

class SymptomAgent:
   def run(self, patient):
       query = " ".join(patient.symptoms)
       retrieved = retrieve(query, k=10)
       # 🔹 Deduplicate safely
       unique = {}
       for d in retrieved:
           name = d.get("name")
           if not name:
               continue
           unique[name] = d
       retrieved = list(unique.values())
       # ❗ CRITICAL: prevent empty crash downstream
       if not retrieved:
           return []
       results = []
       for disease in retrieved:
           score_data = self.calculate_score(patient, disease)
           results.append({
               "name": disease.get("name", "unknown"),
               "confidence": score_data["final_score"],
               "matched_symptoms": self.get_matches(
                   patient.symptoms,
                   disease.get("symptoms", [])
               ),
               "symptom_score": score_data["symptom_score"],
               "lab_score": score_data["lab_score"],
           })
       results.sort(key=lambda x: x["confidence"], reverse=True)
       return results[:5]
   # ------------------------------
   def calculate_score(self, patient, disease):
        symptom_score = self.symptom_score(
            patient.symptoms,
            disease.get("symptoms", [])
        )
        lab_score = self.lab_score(
            patient.labs,
            disease.get("lab_patterns", [])
        )
        # 🔥 infection signal
        infection_signal = patient.labs.get("WBC", 0) > 11000
        infection_match = any(
            "high wbc" in p.lower() or
            "elevated wbc" in p.lower() or
            "infection" in p.lower()
            for p in disease.get("lab_patterns", [])
        )
        # base score
        score = 0.8 * symptom_score
        if symptom_score >= 0.6:
            score += 0.2 * lab_score
        # boost
        if infection_signal and infection_match:
            score += 0.15
        elif infection_signal:
            score -= 0.1
        # penalty
        if infection_signal and not infection_match:
            score -= 0.1
        score = min(score, 0.95)
        return {
            "final_score": round(score, 2),
            "symptom_score": round(symptom_score, 2),
            "lab_score": round(lab_score, 2)
        }
   # ------------------------------
   def symptom_score(self, input_symptoms, disease_symptoms):
       if not input_symptoms:
           return 0
       match_count = 0
       for inp in input_symptoms:
           for ds in disease_symptoms:
               if inp.lower() in ds.lower():
                   match_count += 1
                   break
       return match_count / len(input_symptoms)
   # ------------------------------
   def lab_score(self, labs, patterns):
       if not patterns:
           return 0
       score = 0
       for p in patterns:
           p = p.lower()
           if ("high wbc" in p or "elevated wbc" in p) and labs.get("WBC", 0) > 11000:
               score += 1
           if "normal wbc" in p and labs.get("WBC", 0) <= 11000:
               score += 1
           if "oxygen" in p and labs.get("O2", labs.get("oxygen", 100)) < 95:
               score += 1
       return score / len(patterns)
   # ------------------------------
   def get_matches(self, input_symptoms, disease_symptoms):
       matches = []
       for inp in input_symptoms:
           for ds in disease_symptoms:
               if inp.lower() in ds.lower():
                   matches.append(inp)
                   break
       return matches