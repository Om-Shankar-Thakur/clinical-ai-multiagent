import logging
from pathlib import Path

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Resolved relative to this file (not the process CWD), so the model loads
# correctly regardless of where the app is launched from.
BASE_DIR = Path(__file__).resolve().parents[1]
LOCAL_MODEL_DIR = BASE_DIR / "models" / "all-MiniLM-L6-v2"
HUB_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Process-wide cache: multiple Embedder() instances (one per agent's
# SemanticRetriever - symptom_agent and treatment_planner each build their own)
# previously each loaded a brand-new SentenceTransformer, doubling model-load
# latency per request. Caching by resolved path means the model is loaded at
# most once per process no matter how many Embedder()s are constructed.
_MODEL_CACHE: dict[str, SentenceTransformer] = {}


class Embedder:
    def __init__(self, model_path: str = str(LOCAL_MODEL_DIR), model_name: str = HUB_MODEL_NAME):
        cache_key = model_path if Path(model_path).is_dir() else model_name

        cached = _MODEL_CACHE.get(cache_key)
        if cached is not None:
            logger.debug("Reusing cached embedding model: %s", cache_key)
            self.model = cached
            return

        if Path(model_path).is_dir():
            logger.info("Loading embedding model from local directory: %s", model_path)
            self.model = SentenceTransformer(model_path)
        else:
            # Not vendored locally: download from the hub once, then save a
            # local copy so every subsequent process start (not just this one)
            # loads from disk instead of hitting the network again.
            logger.info("Local model dir not found; downloading '%s' from Hugging Face (one-time).", model_name)
            self.model = SentenceTransformer(model_name)
            try:
                Path(model_path).parent.mkdir(parents=True, exist_ok=True)
                self.model.save(model_path)
                logger.info("Cached embedding model locally at: %s", model_path)
            except OSError as e:
                logger.warning(
                    "Could not cache embedding model to %s (%s); will re-download next run.",
                    model_path, e,
                )

        _MODEL_CACHE[cache_key] = self.model

    def encode(self, texts):
        if isinstance(texts, str):
            texts = [texts]
        return self.model.encode(texts, convert_to_tensor=False)
