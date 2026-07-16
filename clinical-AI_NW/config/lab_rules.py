LAB_RULES = {
   "platelets": {
       "low": {
           "threshold": 100000,
           "signal": "low platelets",
           "critical": True
       }
   },
   "hematocrit": {
       "high": {
           "threshold": 50,
           "signal": "elevated hematocrit",
           "critical": False
       }
   },
   "sodium": {
       "high": {
           "threshold": 145,
           "signal": "high sodium",
           "critical": False
       }
   },
   "hemoglobin": {
       "low": {
           "threshold": 10,
           "signal": "low hemoglobin",
           "critical": False
       }
   },
   "oxygen": {
       "low": {
           "threshold": 92,
           "signal": "low oxygen saturation",
           "critical": True
       }
   },
   "glucose": {
       "high": {
           "threshold": 200,
           "signal": "high blood sugar",
           "critical": True
       }
   }
}

# --------------------------------------------------------------------------- #
# LAB_PATTERN_SYNONYMS
# --------------------------------------------------------------------------- #
# The disease knowledge base (data/diseases.json) describes lab findings in
# free-text clinical shorthand (e.g. "hypoxemia", "low platelet count",
# "high glucose") that does not literally match the collected lab field names
# ("oxygen", "platelets", "glucose") used as keys in LAB_RULES / lab_results.
#
# Without this map, LabInterpreterAgent._match_lab_patterns silently fails to
# recognise these patterns (wrong key extracted, e.g. "oxygen saturation"
# instead of "oxygen"), so a critical finding like low SpO2 never contributed
# to the lab_score of clinically-related diagnoses (pneumonia, PE, COPD, ...).
#
# Each entry maps a known pattern string (lowercase, as it appears in
# data/diseases.json) to the (lab_field, direction) it represents, where
# `direction` matches a key under LAB_RULES[lab_field] ("low" or "high").
LAB_PATTERN_SYNONYMS = {
    # oxygen / hypoxemia
    "low oxygen saturation": ("oxygen", "low"),
    "hypoxemia": ("oxygen", "low"),
    # platelets / thrombocytopenia
    "low platelet count": ("platelets", "low"),
    "thrombocytopenia": ("platelets", "low"),
    # hemoglobin / anemia
    "anemia": ("hemoglobin", "low"),
    "possible anemia": ("hemoglobin", "low"),
    "iron deficiency anemia": ("hemoglobin", "low"),
    "low hemoglobin": ("hemoglobin", "low"),
    # hematocrit
    "elevated hematocrit": ("hematocrit", "high"),
    # sodium
    "elevated sodium": ("sodium", "high"),
    # NOTE: "hyponatremia" (low sodium) is intentionally NOT mapped here -
    # LAB_RULES defines no "low" rule/threshold for sodium, so there is no
    # validated threshold to evaluate it against. Add a "low" rule to
    # LAB_RULES["sodium"] before mapping this synonym.
    # glucose
    "high glucose": ("glucose", "high"),
    "elevated fasting glucose": ("glucose", "high"),
}