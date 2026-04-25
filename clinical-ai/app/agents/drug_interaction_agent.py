from app.config.settings import CRITICAL_INTERACTION

class DrugInteractionAgent:
   
   def run(self, drugs_output, patient):
        safe_meds = []
        blocked = []
        warnings = []

        current_meds = [m.lower() for m in patient.medications]
        allergies = [a.lower() for a in patient.allergies]
        history = [h.lower() for h in patient.history]

        for drug in drugs_output["medications"]:
            name = drug["name"].lower()
            is_blocked = False
            # 1. Allergy
            if name in allergies:
                blocked.append(f"{drug['name']} blocked (allergy)")
                continue
            # 2. Interaction
            for inter in drug.get("interactions", []):
                interacting_drug = inter.get("drug", "").lower()
                severity = inter.get("severity", "").lower()
                if interacting_drug in current_meds:
                    warnings.append(f"{drug['name']} + {inter['drug']} → {inter['effect']}")
                    if severity in CRITICAL_INTERACTION:
                        blocked.append(f"{drug['name']} blocked (severe interaction)")
                        is_blocked = True
                        break
            if is_blocked:
                continue
            # 3. Contraindication
            for contra in drug.get("contraindications", []):
                if contra.lower() in history:
                    blocked.append(f"{drug['name']} blocked (contraindicated for {contra})")
                    is_blocked = True
                    break
            if is_blocked:
                continue
            # ONLY HERE → safe
            safe_meds.append(drug)

        return {
            "safe_medications": safe_meds,
            "blocked": blocked,
            "warnings": list(set(drugs_output["warnings"]))
        }