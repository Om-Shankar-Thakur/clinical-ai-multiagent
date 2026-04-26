import json

class LabInterpreterAgent:
   def __init__(self, data_path="data/diseases.json"):
       with open(data_path, "r") as f:
           self.disease_db = json.load(f)

   def analyze(self, lab_results):

    hypotheses = []
    signals = []

    lab_results = {k.lower().strip(): v for k, v in lab_results.items()}

    if "platelets" in lab_results and lab_results["platelets"] < 100000:
        signals.append("low platelets")
    if "hematocrit" in lab_results and lab_results["hematocrit"] > 50:
        signals.append("elevated hematocrit")
    if "sodium" in lab_results and lab_results["sodium"] > 145:
        signals.append("high sodium")

    critical_flags = self._detect_critical_values(lab_results)

    for d in self.disease_db:
        lab_patterns = d.get("lab_patterns", [])
        if not lab_patterns:
            continue
        score, matched = self._match_lab_patterns(lab_results, lab_patterns)
        if score == 0:
            continue
        interpretation = self._interpret_support(score)
        hypotheses.append({
            "disease": d["name"],
            "lab_support": interpretation,
            "score": round(score, 2),
            "matched_lab_patterns": matched
        })

    # sort strongest lab evidence first
    hypotheses = sorted(hypotheses, key=lambda x: x["score"], reverse=True)
    return {
        "lab_hypotheses": hypotheses[:5],
        "critical_flags": critical_flags,
        "lab_signals": signals
    }
 
   # -----------------------------
   # Helpers
   # -----------------------------
   def _get_disease_data(self, disease_name):
       for d in self.disease_db:
           if d["name"].lower() == disease_name.lower():
               return d
       return None
   def _match_lab_patterns(self, lab_results, patterns):
        matched = []
        

        for pattern in patterns:
            pattern = pattern.lower()
            # simple rule-based matching
            if "elevated" in pattern:
                key = pattern.replace("elevated ", "").strip().lower()
                if key in lab_results and lab_results[key] > self._normal_upper(key):
                    matched.append(pattern)
            elif "low" in pattern or "reduced" in pattern:
                key = pattern.replace("low ", "").replace("reduced ", "").strip().lower()
                if key in lab_results and lab_results[key] < self._normal_lower(key):
                    matched.append(pattern)
        score = len(matched) / len(patterns) if patterns else 0
        return score, matched
   
   def _interpret_support(self, score):
       if score > 0.6:
           return "supports"
       elif score > 0.3:
           return "partial"
       elif score > 0:
           return "weak"
       else:
           return "refutes"
       
   def _detect_critical_values(self, labs):
       critical = []
       # simple hardcoded rules (extend later)
       if labs.get("platelets", 150000) < 100000:
           critical.append("Low platelets (possible dengue/sepsis)")
       if labs.get("sodium", 140) > 150:
           critical.append("Hypernatremia")
       if labs.get("hemoglobin", 13) < 8:
           critical.append("Severe anemia")
       return critical
   
   def _normal_upper(self, key):
       return {
           "hematocrit": 50,
           "sodium": 145,
           "platelets": 450000
       }.get(key, 9999)
   
   def _normal_lower(self, key):
       return {
           "hemoglobin": 12,
           "platelets": 150000
       }.get(key, 0)