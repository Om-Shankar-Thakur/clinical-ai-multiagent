# rag/guideline_indexer.py
import json
from pathlib import Path

from rag.embedder import Embedder
from rag.vector_store import VectorStore


BASE_DIR = Path(__file__).resolve().parents[1]
PROCESSED_DIR = BASE_DIR / "data" / "processed"

GUIDELINE_FILES = [
    "covid19_guidelines_chunks.jsonl",
    "malaria_guidelines_chunks.jsonl",
    "dengue_guidelines_chunks.jsonl",
    "tuberculosis_guidelines_chunks.jsonl",
    "bloodstream_infections_guidelines_chunks.jsonl",
]


class GuidelineIndexer:
    def __init__(self):
        self.embedder = Embedder()

    def build_index(self):
        texts = []
        metadata = []

        for fname in GUIDELINE_FILES:
            path = PROCESSED_DIR / fname
            if not path.exists():
                print(f"⚠️ Missing file: {fname}")
                continue

            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    record = json.loads(line)
                    texts.append(record["content"])
                    metadata.append(record["metadata"])

        if not texts:
            raise RuntimeError("No guideline chunks loaded")

        embeddings = self.embedder.encode(texts)
        store = VectorStore(dim=len(embeddings[0]))
        store.add(embeddings, metadata)
        store.save("guideline_store")

        print("✅ Guideline index built successfully")
        return store


if __name__ == "__main__":
    GuidelineIndexer().build_index()
