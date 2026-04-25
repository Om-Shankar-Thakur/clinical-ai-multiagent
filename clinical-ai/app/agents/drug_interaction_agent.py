from app.config.settings import CRITICAL_INTERACTION, SEVERITY_RANK

class DrugInteractionAgent:
   
   def run(self, drugs_output, patient):
        safe_meds = []
        blocked = []
        warnings = []
        interaction_details=[]

        

        current_meds = [m.lower() for m in patient.medications]
        allergies = [a.lower() for a in patient.allergies]
        history = [h.lower() for h in patient.history]

        for drug in drugs_output["medications"]:
            name = drug["name"].lower()
            is_blocked = False
            # 1. Allergy
            if name in allergies:
                interaction_details.append({
                    "drug": drug["name"],
                    "type": "allergy",
                    "severity": "critical",
                    "reason": "Patient allergic to this drug"
                })
                blocked.append(drug['name'])
                continue
            # 2. Interaction
            for inter in drug.get("interactions", []):
                interacting_drug = inter.get("drug", "").lower()
                severity = inter.get("severity", "").lower()

                if interacting_drug in current_meds:
                    interaction_details.append({
                        "drug": drug["name"],
                        "interacts_with": inter["drug"],
                        "severity": severity,
                        "effect": inter.get("effect",""),
                        "type": "drug_interaction"
                    })
                    
                    if SEVERITY_RANK.get(severity, 0) >= 3:
                        blocked.append(f"{drug['name']} blocked (severe interaction)")
                        is_blocked = True
                        break
            if is_blocked:
                continue
            # 3. Contraindication
            for contra in drug.get("contraindications", []):
                if contra.lower() in history:

                    interaction_details.append({
                        "drug": drug["name"],
                        "type": "contraindications",
                        "condition": contra,
                        "severity": "high",
                        "reason": f"contradicated for {contra}"
                    })
                    blocked.append(drug["name"])
                    is_blocked = True
                    break
            if is_blocked:
                continue
            # ONLY HERE → safe
            safe_meds.append(drug)

        return {
            "safe_medications": safe_meds,
            "blocked": blocked,
            "warnings": warnings,
            "interaction_details": interaction_details
        }