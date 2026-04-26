(venv) C:\Users\2477108\OneDrive - Cognizant\Documents\caliber\clinical-ai>python -m app.main
Loading weights: 100%|███████████████████████████████████████████████████████████████████████████████████████| 103/103 [00:00<00:00, 1604.74it/s]
RAW LLM OUTPUT:
 {
  "diagnosis": "Community-Acquired Pneumonia",
  "reasoning": "The symptoms of fever, cough, and shortness of breath align with the typical presentation of community-acquired pneumonia. Lab results show high WBC, low oxygen, and high lactate, which correlate with severe infection and sepsis risk. The risk score of 1.2 indicates a moderate risk, supporting the diagnosis. There is no uncertainty present.",
  "severity": "critical",
  "next_steps": "Immediate clinical evaluation and management are necessary due to critical lab severity and symptoms."
}

========== FINAL OUTPUT ==========

Diagnosis:
{'diagnosis': 'Community-Acquired Pneumonia', 'confidence': 1.0, 'severity': 'critical', 'risk_score': 1.2, 'alerts': ['High WBC (possible severe infection)', 'Low oxygen (critical)', 'High lactate (sepsis risk)'], 'matched_symptoms': ['fever', 'cough', 'shortness of breath'], 'uncertainty': False, 'explanation_type': 'symptom-aligned', 'reason': {'diagnosis': 'Community-Acquired Pneumonia', 'reasoning': 'The symptoms of fever, cough, and shortness of breath align with the typical presentation of community-acquired pneumonia. Lab results show high WBC, low oxygen, and high lactate, which correlate with severe infection and sepsis risk. The risk score of 1.2 indicates a moderate risk, supporting the diagnosis. There is no uncertainty present.', 'severity': 'critical', 'next_steps': 'Immediate clinical evaluation and management are necessary due to critical lab severity and symptoms.'}}

Treatment Plan:
- ⚠️ Stabilize patient first (airway, breathing, circulation)
- First-line: Start Azithromycin (500 - 500 mg/day)
- Alternative: Start Clarithromycin (500 - 1000 mg/day)
- Alternative: Start Amoxicillin (500 - 3000 mg/day)
- Alternative: Start Colchicine (0.5 - 2 mg/day)
- Alternative: Start Ceftriaxone (1000 - 4000 mg/day)

Monitoring:
- 🚨 Immediate ICU / emergency care required

Drug Safety:
Safe Drugs: [{'name': 'Azithromycin', 'dose': '500 - 500 mg/day'}, {'name': 'Clarithromycin', 'dose': '500 - 1000 mg/day'}, {'name': 'Amoxicillin', 'dose': '500 - 3000 mg/day'}, {'name': 'Colchicine', 'dose': '0.5 - 2 mg/day'}, {'name': 'Ceftriaxone', 'dose': '1000 - 4000 mg/day'}]
Warnings: []
⚠️ This is a clinical decision support system. All recommendations must be reviewed by a licensed clinician.