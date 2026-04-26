from rag.embedder import Embedder
from rag.vector_store import VectorStore

class SemanticRetriever:
   def __init__(self):
       self.embedder = Embedder()
       self.vector_store = VectorStore.load()
   def retrieve(self, symptoms, top_k=5):
       query_text = " ".join(symptoms)
       query_vector = self.embedder.encode(query_text)[0]
       results = self.vector_store.search(query_vector, top_k=top_k)
       return results