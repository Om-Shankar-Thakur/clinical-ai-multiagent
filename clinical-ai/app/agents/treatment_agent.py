class TreatmentAgent:

    def run(self, diagnosis, drugs_output, patient=None):

        plan = []

        if not drugs_output["medications"]:

            plan.append("No medication recommendation available")

        else:

            for med in drugs_output["medications"]:

                plan.append(f"Start {med['name']} ({med['dose']})")

        monitoring = []

        if diagnosis["final"]["severity"] == "critical":

            monitoring.append("Immediate monitoring required (ICU / emergency care)")

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
 