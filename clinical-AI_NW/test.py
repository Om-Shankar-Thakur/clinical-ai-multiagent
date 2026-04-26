from agents.symptom_analyzer import SymptomAnalyzerAgent
from agents.lab_interpreter_agent import LabInterpreterAgent
from pprint import pprint

def run_test_case(case_id, chief_complaint, symptoms, lab_results):
   print(f"\n{'='*60}")
   print(f"TEST CASE {case_id}")
   print(f"Chief Complaint: {chief_complaint}")
   print(f"Symptoms: {symptoms}")
   print(f"Lab Results: {lab_results}")
   print(f"{'='*60}")
   # Initialize agents
   symptom_agent = SymptomAnalyzerAgent()
   lab_agent = LabInterpreterAgent()
   # -------------------------------
   # Parallel execution (logical)
   # -------------------------------
   symptom_output = symptom_agent.analyze(
       chief_complaint=chief_complaint,
       symptoms=symptoms
   )
   lab_output = lab_agent.analyze(
       lab_results=lab_results
   )
   # -------------------------------
   # Display outputs separately
   # -------------------------------
   print("\n--- Symptom Agent Output ---\n")
   pprint(symptom_output)
   print("\n--- Lab Agent Output ---\n")
   pprint(lab_output)

if __name__ == "__main__":
   # -------------------------------
   # TEST CASE 1 (GI case)
   # -------------------------------
   run_test_case(
       case_id=1,
       chief_complaint="Stomach pain",
       symptoms=["stomach pain", "fever", "vomiting"],
       lab_results={
           "hematocrit": 52,
           "sodium": 150,
           "platelets": 180000
       }
   )
   # -------------------------------
   # TEST CASE 2 (Infection case)
   # -------------------------------
   run_test_case(
       case_id=2,
       chief_complaint="High fever",
       symptoms=["fever", "body pain", "chills"],
       lab_results={
           "platelets": 80000,   # dengue signal
           "hematocrit": 48,
           "sodium": 138
       }
   )
   # -------------------------------
   # TEST CASE 3 (General weakness)
   # -------------------------------
   run_test_case(
       case_id=3,
       chief_complaint="Weakness and headache",
       symptoms=["fever", "weakness", "headache"],
       lab_results={
           "hemoglobin": 9,
           "platelets": 140000,
           "sodium": 142
       }
   )