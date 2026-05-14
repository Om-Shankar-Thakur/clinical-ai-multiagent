from rag.embedder import Embedder
from rag.vector_store import VectorStore

class SemanticRetriever:
    def __init__(self):
        self.embedder = Embedder()
        self.disease_store = VectorStore.load("vector_store")
        self.guideline_store = VectorStore.load("guideline_store")

    def retrieve_diseases(self, symptoms, top_k=5):
        query_text = " ".join(symptoms)
        query_vector = self.embedder.encode(query_text)[0]
        return self.disease_store.search(query_vector, top_k=top_k)

    def retrieve_guidelines(self, query, top_k=5, disease_filter=None):
        query_vec = self.embedder.encode(query)[0]
        results = self.guideline_store.search(query_vec, top_k=top_k)

        if disease_filter:
            results = [
                r for r in results
                if r.get("disease", "").lower() == disease_filter.lower()
            ]

        return results