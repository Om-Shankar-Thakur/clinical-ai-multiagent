def validate_patient_data(patient):
   if not patient.symptoms:
       return False, "No symptoms provided"
   return True, None

def validate_llm_output(text):
   if "I recommend surgery" in text:
       return False, "Unsafe medical advice"
   return True, text