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

def build_drug_text(d):
   return " ".join([
       d["name"],
       d["class"],
       " ".join(d.get("uses", [])),
       " ".join(d.get("contraindications", []))
   ])

def ingest():
   vectors = []
   metadata = []

   # DISEASES
   with open("data/diseases.json", "r") as f:
       diseases = json.load(f)
   for d in diseases:
       text = build_text(d)
       vec = embedder.encode(text)
       vectors.append(vec)
       metadata.append({
           "type": "disease",
           "data": d
       })

   # LOAD DRUGS
   with open("data/drugs.json", "r") as f:
       drugs = json.load(f)
   for d in drugs:
       text = build_drug_text(d)
       vec = embedder.encode(text)
       vectors.append(vec)
       metadata.append({
           "type": "drug",
           "data": d
       })
       
   # STORE
   store.add(vectors, metadata)
   store.save()
   print(f"✅ Indexed {len(diseases)} diseases")
   print(f"✅ Indexed {len(drugs)} drugs")


if __name__ == "__main__":
    ingest()