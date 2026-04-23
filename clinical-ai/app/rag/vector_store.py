
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
   def search(self, vector, k=5):
       D, I = self.index.search(np.array([vector]), k)
       return [self.metadata[i] for i in I[0]]
   def save(self):
       faiss.write_index(self.index, self.index_path)
       with open(self.meta_path, "wb") as f:
           pickle.dump(self.metadata, f)