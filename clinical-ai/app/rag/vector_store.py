
import faiss
import numpy as np
import pickle
import os
class VectorStore:
   def __init__(self, dim=384, index_path="faiss.index", meta_path="meta.pkl"):
       self.dim = dim
       self.index_path = index_path
       self.meta_path = meta_path
       if os.path.exists(index_path):
           self.index = faiss.read_index(index_path)
           with open(meta_path, "rb") as f:
               self.metadata = pickle.load(f)
       else:
           self.index = faiss.IndexFlatL2(dim)
           self.metadata = []
   def add(self, vectors, meta):
       self.index.add(np.array(vectors))
       self.metadata.extend(meta)
   def search(self, vector, k=5, top_k=None, filter=None):
        # --- Step 1: handle top_k (Azure-style compatibility)
        if top_k is not None:
            k = top_k
        # --- Step 2: FAISS search
        D, I = self.index.search(np.array([vector]), k)
        results = []
        for idx in I[0]:
            if idx < len(self.metadata):
                item = self.metadata[idx]
                results.append(item)
        # --- Step 3: optional filtering (manual, since FAISS doesn't support it)
        if filter:
            def match(meta):
                return all(meta.get(key) == val for key, val in filter.items())
            results = [r for r in results if match(r)]
        return results
   def save(self):
       faiss.write_index(self.index, self.index_path)
       with open(self.meta_path, "wb") as f:
           pickle.dump(self.metadata, f)