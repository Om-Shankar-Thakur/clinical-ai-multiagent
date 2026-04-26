from rag.retriever import SemanticRetriever


class SymptomAnalyzerAgent:

    def __init__(self):

        self.retriever = SemanticRetriever()

    def analyze(self, chief_complaint, symptoms):

        symptoms = [s.lower().strip() for s in symptoms]

        print(f"\n[INFO] Chief Complaint: {chief_complaint}")

        print(f"[INFO] Symptoms: {symptoms}")

        candidates = self.retriever.retrieve(symptoms)

        ranked = self.rank_and_reason(candidates, symptoms)

        return {

            "chief_complaint": chief_complaint,

            "differential_diagnosis": ranked

        }

    def rank_and_reason(self, candidates, input_symptoms):

        results = []

        for c in candidates:

            disease_symptoms = [s.lower() for s in c["symptoms"]]

            matched = list(set(input_symptoms).intersection(disease_symptoms))

            missing = list(set(disease_symptoms) - set(input_symptoms))

            # ❌ FILTER — remove weak candidates

            if len(matched) == 0:

                continue

            # --- SCORING ---

            overlap_score = len(matched) / len(disease_symptoms)

            # FAISS distance → similarity

            semantic_score = 1 / (1 + c["distance"])  # normalize

            # Hybrid score (simple but effective)

            final_score = 0.6 * overlap_score + 0.4 * semantic_score

            # --- CONFIDENCE ---

            if final_score > 0.65:

                confidence = "high"

            elif final_score > 0.4:

                confidence = "medium"

            else:

                confidence = "low"

            # --- REASONING ---

            reasoning = {

                "matched_symptoms": matched,

                "missing_symptoms": missing[:3],  # limit noise

                "confidence": confidence

            }

            results.append({

                "disease": c["disease"],

                "score": round(final_score, 2),

                "reasoning": reasoning,

                "description": c["description"]

            })

        # sort by score

        results = sorted(results, key=lambda x: x["score"], reverse=True)

        return results
 