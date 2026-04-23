from app.rag.embedder import Embedder
from app.rag.index_manager import get_store
embedder = Embedder()
store = get_store()
def retrieve(query: str, k=5):
   vector = embedder.encode(query)
   return store.search(vector, k)