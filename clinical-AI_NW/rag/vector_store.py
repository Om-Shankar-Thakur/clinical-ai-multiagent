import faiss
import numpy as np
import pickle

# Process-wide cache keyed by path: SymptomAnalyzerAgent and
# TreatmentPlannerAgent each build their own SemanticRetriever, which
# previously re-read and re-unpickled the same index files from disk on every
# construction. Caching by path means each index is loaded at most once per
# process. Safe to share: VectorStore is read-only after load() in normal use.
_STORE_CACHE = {}


class VectorStore:
   def __init__(self, dim):
       self.index = faiss.IndexFlatL2(dim)
       self.metadata = []
   def add(self, vectors, metadata):
       vectors = np.array(vectors).astype("float32")
       self.index.add(vectors)
       self.metadata.extend(metadata)
   def search(self, query_vector, top_k=5):
        query_vector = np.array([query_vector]).astype("float32")
        distances, indices = self.index.search(query_vector, top_k)
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(self.metadata):
                results.append({
                    **self.metadata[idx],
                    "distance": float(distances[0][i])
                })
        return results
   def save(self, path="vector_store"):
       faiss.write_index(self.index, f"{path}.index")
       with open(f"{path}.meta", "wb") as f:
           pickle.dump(self.metadata, f)
   @classmethod
   def load(cls, path="vector_store"):
       cached = _STORE_CACHE.get(path)
       if cached is not None:
           return cached
       index = faiss.read_index(f"{path}.index")
       with open(f"{path}.meta", "rb") as f:
           metadata = pickle.load(f)
       obj = cls(dim=index.d)
       obj.index = index
       obj.metadata = metadata
       _STORE_CACHE[path] = obj
       return obj
