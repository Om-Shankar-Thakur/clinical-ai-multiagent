import logging
import os

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Local (vendored) model directory, and the Hugging Face hub id used as a
# fallback so the project runs on a fresh clone without a manual model download.
LOCAL_MODEL_DIR = os.path.join("models", "all-MiniLM-L6-v2")
HUB_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


class Embedder:
    def __init__(self, model_path: str = LOCAL_MODEL_DIR, model_name: str = HUB_MODEL_NAME):
        if os.path.isdir(model_path):
            logger.info("Loading embedding model from local directory: %s", model_path)
            self.model = SentenceTransformer(model_path)
        else:
            # Not vendored locally: download + cache from the hub on first use.
            logger.info("Local model dir not found; loading '%s' from Hugging Face.", model_name)
            self.model = SentenceTransformer(model_name)

    def encode(self, texts):
        if isinstance(texts, str):
            texts = [texts]
        return self.model.encode(texts, convert_to_tensor=False)
