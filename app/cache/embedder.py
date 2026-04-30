from functools import lru_cache
from sentence_transformers import SentenceTransformer


@lru_cache(maxsize=1)
def _load_model() -> SentenceTransformer:
    return SentenceTransformer("all-MiniLM-L6-v2")


def embed(text: str) -> list[float]:
    model = _load_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()
