import json

def validate_patient_data(patient):
   if not patient.symptoms:
       return False, "No symptoms provided"
   return True, None


def validate_llm_output(text):
   try:
       data = json.loads(text)
       required_keys = ["diagnosis", "reasoning", "severity", "next_steps"]
       for key in required_keys:
           if key not in data:
               return False, f"Missing required field: {key}"
       # Safety checks
       unsafe_phrases = ["100% sure", "guaranteed", "no need for doctor"]
       for phrase in unsafe_phrases:
           if phrase in data.get("reasoning", "").lower():
               return False, "Unsafe medical claim"
       return True, data
   except Exception:
       return False, "Invalid JSON format"

def apply_guardrails(output):
   disclaimer = (
       "⚠️ This is a clinical decision support system. "
       "All recommendations must be reviewed by a licensed clinician."
   )
   output["disclaimer"] = disclaimer
   # Hard safety: no drugs
   if not output["treatment"]["treatment_plan"]:
       output["critical_alert"] = "No safe treatment available"
   return output
