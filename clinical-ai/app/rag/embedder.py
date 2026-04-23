from sentence_transformers import SentenceTransformer
import os

class Embedder:
    def __init__(self):
        model_path = os.path.join(
            os.path.dirname(__file__),
            "../../models/all-MiniLM-L6-v2"
        )

        self.model = SentenceTransformer(model_path)

    def encode(self, text: str):
        return self.model.encode(text).astype("float32")