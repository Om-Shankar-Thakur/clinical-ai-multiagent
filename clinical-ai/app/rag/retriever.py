from app.rag.embedder import Embedder
from app.rag.index_manager import get_store
embedder = Embedder()
store = get_store()
# ✅ Disease retrieval (FIXED)
def retrieve(query: str, k=5):
   vector = embedder.encode(query)
   results = store.search(vector, k)
   return [r["data"] for r in results if r.get("type") == "disease"]
# ✅ Drug retrieval (FIXED)
def retrieve_drugs(query: str, k=5):
   vector = embedder.encode(query)
   results = store.search(vector, k * 2)
   drugs = [r["data"] for r in results if r.get("type") == "drug"]
   return drugs[:k]