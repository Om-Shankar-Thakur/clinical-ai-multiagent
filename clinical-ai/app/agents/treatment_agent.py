class TreatmentAgent:

    def run(self, diagnosis, drugs_output, patient=None):

        plan = []

        if not drugs_output["medications"]:
            plan.append("No medication recommendation available")
        else:
            for i, med in enumerate(drugs_output["medications"]):
                tag = "First-line" if i == 0 else "Alternative"
                plan.append(f"{tag}: Start {med['name']} ({med['dose']})")

        monitoring = []
        severity = diagnosis["final"]["severity"]
        if severity == "critical":
            monitoring.append("🚨 Immediate ICU / emergency care required")
            plan.insert(0, "⚠️ Stabilize patient first (airway, breathing, circulation)")
        elif severity == "moderate":
            monitoring.append("Close monitoring required (hospital admission)")
        else:
            monitoring.append("Routine monitoring and follow-up")

        follow_up = "Re-evaluate patient condition in 24-48 hours"

        return {
            "treatment_plan": plan,
            "monitoring": monitoring,
            "follow_up": follow_up,
            "warnings": drugs_output["warnings"],
            "contraindications": drugs_output["contraindications"]
        }
 