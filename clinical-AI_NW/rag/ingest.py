import json

from rag.embedder import Embedder

from rag.vector_store import VectorStore


class DiseaseIndexer:

    def __init__(self):

        self.embedder = Embedder()

    def build_index(self, data_path="data/diseases.json"):

        with open(data_path, "r") as f:

            diseases = json.load(f)

        texts = []

        metadata = []

        for d in diseases:

            # ✅ FIXED KEYS

            combined_text = (

                d["name"] + " " +

                " ".join(d["symptoms"]) + " " +

                " ".join(d.get("risk_factors", []))

            )

            texts.append(combined_text)

            metadata.append({

                "id": d["id"],

                "disease": d["name"],   # normalized key

                "symptoms": d["symptoms"],

                "description": d.get("description", ""),

                "treatment": d.get("treatment", [])

            })

        embeddings = self.embedder.encode(texts)

        vector_store = VectorStore(dim=len(embeddings[0]))

        vector_store.add(embeddings, metadata)

        return vector_store


def build_and_save():

    indexer = DiseaseIndexer()

    store = indexer.build_index()

    store.save()

    print("✅ Index built and saved")


if __name__ == "__main__":

    build_and_save()
 