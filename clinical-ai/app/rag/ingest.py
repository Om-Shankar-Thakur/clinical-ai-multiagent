import json
from app.rag.embedder import Embedder
from app.rag.vector_store import VectorStore
embedder = Embedder()
store = VectorStore()
def build_text(d):
   return " ".join([
       d["name"],
       " ".join(d["symptoms"]),
       " ".join(d.get("lab_patterns", [])),
       " ".join(d.get("risk_factors", [])),
       d.get("description", "")
   ])
def ingest():
   with open("data/diseases.json", "r") as f:
       diseases = json.load(f)
   vectors = []
   metadata = []
   for d in diseases:
       text = build_text(d)
       vec = embedder.encode(text)
       vectors.append(vec)
       metadata.append(d)
   store.add(vectors, metadata)
   store.save()
   print(f"✅ Indexed {len(metadata)} diseases")
if __name__ == "__main__":
   ingest()