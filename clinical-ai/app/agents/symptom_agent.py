from app.rag.retriever import retrieve

class SymptomAgent:

    def run(self, patient):
        query = " ".join(patient.symptoms)
        retrieved = retrieve(query, k=10)
        unique = {}
        for d in retrieved:
            unique[d["name"]] = d
        retrieved = list(unique.values())
        results = []
        for disease in retrieved:
            score_data = self.calculate_score(patient, disease)
            results.append({
                "name": disease["name"],
                "confidence": score_data["final_score"],
                "matched_symptoms": self.get_matches(patient.symptoms, disease["symptoms"]),
                "symptom_score": score_data["symptom_score"],
                "lab_score": score_data["lab_score"],
            })
        results.sort(key=lambda x: x["confidence"], reverse=True)

        return results[:5]
    
    def calculate_score(self, patient, disease):
        symptom_score = self.symptom_score(patient.symptoms, disease["symptoms"])
        lab_score = self.lab_score(patient.labs, disease.get("lab_patterns", []))

        # 🔥 Detect strong infection signal
        infection_signal = patient.labs.get("WBC", 0) > 11000

        # 🔥 Boost diseases that align with infection
        infection_match = any("high wbc" in p.lower() or "elevated wbc" in p.lower() or "infection" in p.lower()
        for p in disease.get("lab_patterns", []))
        
        # base score
        score = (0.7 * symptom_score) + (0.3 * lab_score)

        # 🔥 boost logic
        if infection_signal and infection_match:
            score += 0.15
        elif infection_signal:
            score-=0-1

        # 🔥 penalize mismatch
        if infection_signal and not infection_match:
            score -= 0.1
        return {
            "final_score": max(round(score, 2), 0),
            "symptom_score": round(symptom_score,2),
            "lab_score": round(lab_score, 2)
        }
   

    def symptom_score(self, input_symptoms, disease_symptoms):

        match_count = 0

        for inp in input_symptoms:
            for ds in disease_symptoms:
                if inp.lower() in ds.lower():
                    match_count += 1
                    break
        return match_count / len(input_symptoms)

    def lab_score(self, labs, patterns):
        score = 0
        o2 = labs.get("O2", labs.get("oxygen", 100))
        for p in patterns:
            p = p.lower()
            if ("high wbc" in p or "elevated wbc" in p) and labs.get("WBC", 0) > 11000:
                score += 1
            if "normal wbc" in p and labs.get("WBC", 0) <= 11000:
                score += 1
            if "oxygen" in p and labs.get("O2", 100) < 95:
                score += 1
        return score / len(patterns) if patterns else 0

    def get_matches(self, input_symptoms, disease_symptoms):
        matches = []
        for inp in input_symptoms:
            for ds in disease_symptoms:
                if inp.lower() in ds.lower():
                    matches.append(inp)
                    break
        return matches
 