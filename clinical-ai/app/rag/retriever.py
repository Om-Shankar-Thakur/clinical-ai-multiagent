from app.rag.embedder import Embedder
from app.rag.index_manager import get_store
from functools import lru_cache
embedder = Embedder()
store = get_store()

# 🔹 Cache embeddings (performance boost)
@lru_cache(maxsize=100)
def cached_encode(text: str):
   return embedder.encode(text)

# ✅ Disease retrieval
def retrieve(query: str, k=5):
   vector = cached_encode(query)
   results = store.search(vector, k=k)
   cleaned = []
   for r in results:
       data = r.get("data", r)
       # ensure valid structure
       if isinstance(data, dict) and "name" in data:
           cleaned.append(data)
   return cleaned

# ✅ Drug retrieval
def retrieve_drugs(query: str, k=5):
   vector = cached_encode(query)
   results = store.search(vector, k=k * 3)
   drugs = []
   for r in results:
       data = r.get("data", r)
       # 🔥 HARD FILTER: must look like drug
       if not isinstance(data, dict):
           continue
       if "name" not in data:
           continue
       # 👇 KEY FIX
       if "dose" not in data and "interactions" not in data:
           continue  # skip diseases
       drugs.append(data)
   return drugs[:k]