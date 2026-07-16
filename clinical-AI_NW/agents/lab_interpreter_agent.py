import json
from config.lab_rules import LAB_RULES, LAB_PATTERN_SYNONYMS

class LabInterpreterAgent:
   def __init__(self, data_path="data/diseases.json"):
       with open(data_path, "r") as f:
           self.disease_db = json.load(f)

   def analyze(self, lab_results):

    hypotheses = []
    signals = []
    critical_flags =[]

    lab_results = {k.lower().strip(): v for k, v in lab_results.items()}

    for key, value in lab_results.items():
        if key not in LAB_RULES:
            continue
        rules = LAB_RULES[key]

        for rule_type, rule in rules.items():
            if rule_type == "low" and value < rule["threshold"]:
                signals.append(rule["signal"])
                if rule["critical"]:
                    critical_flags.append(rule["signal"])

            elif rule_type == "high" and value > rule["threshold"]:
                signals.append(rule["signal"])
                if rule["critical"]:
                    critical_flags.append(rule["signal"])

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
        """
        Match a disease's free-text lab_patterns against the collected
        lab_results, using LAB_RULES as the single source of truth for
        thresholds/direction.

        Two paths, in order:
        1. LAB_PATTERN_SYNONYMS - explicit mapping for clinical shorthand
           (e.g. "hypoxemia", "low platelet count") that doesn't literally
           contain the lab field name. This is checked FIRST so critical
           findings (e.g. low oxygen saturation) are recognised even when the
           disease-authored text uses a synonym rather than the exact field
           name - previously these silently failed to match at all.
        2. Fallback: derive the field name directly from the pattern text for
           patterns that already spell out the field name (e.g. "elevated
           hematocrit" -> "hematocrit"). Handles both "high"/"elevated" and
           "low"/"reduced" directions (the original code only handled
           "elevated", so "high glucose" never matched).
        """
        matched = []

        for raw_pattern in patterns:
            pattern = raw_pattern.lower().strip()

            synonym = LAB_PATTERN_SYNONYMS.get(pattern)
            if synonym:
                lab_key, direction = synonym
                if self._rule_fires(lab_results, lab_key, direction):
                    matched.append(raw_pattern)
                continue

            if any(w in pattern for w in ("elevated", "high")):
                key = self._strip_direction_words(pattern, ("elevated ", "high "))
                if self._rule_fires(lab_results, key, "high"):
                    matched.append(raw_pattern)
            elif any(w in pattern for w in ("low", "reduced")):
                key = self._strip_direction_words(pattern, ("low ", "reduced "))
                if self._rule_fires(lab_results, key, "low"):
                    matched.append(raw_pattern)

        score = len(matched) / len(patterns) if patterns else 0
        return score, matched

   @staticmethod
   def _strip_direction_words(pattern, words):
       for w in words:
           pattern = pattern.replace(w, "")
       return pattern.strip()

   @staticmethod
   def _rule_fires(lab_results, lab_key, direction):
       """True if lab_results[lab_key] crosses the LAB_RULES threshold for
       (lab_key, direction). False if the key is unmeasured or unconfigured."""
       if lab_key not in lab_results or lab_key not in LAB_RULES:
           return False
       rule = LAB_RULES[lab_key].get(direction)
       if not rule:
           return False
       value = lab_results[lab_key]
       if direction == "low":
           return value < rule["threshold"]
       return value > rule["threshold"]

   def _interpret_support(self, score):
       if score > 0.6:
           return "supports"
       elif score > 0.3:
           return "partial"
       elif score > 0:
           return "weak"
       else:
           return "refutes"
