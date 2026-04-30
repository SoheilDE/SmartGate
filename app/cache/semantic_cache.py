import uuid

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct, ScoredPoint

from app.cache.embedder import embed
from app.config.settings import settings

_VECTOR_SIZE = 384  # all-MiniLM-L6-v2 output dimension


def _client() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url)


def init_collection() -> None:
    client = _client()
    existing = {c.name for c in client.get_collections().collections}
    if settings.qdrant_collection not in existing:
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE),
        )


def lookup(prompt: str) -> str | None:
    client = _client()
    vector = embed(prompt)
    results: list[ScoredPoint] = client.search(
        collection_name=settings.qdrant_collection,
        query_vector=vector,
        limit=1,
        with_payload=True,
    )
    if results and results[0].score >= settings.cache_similarity_threshold:
        return results[0].payload.get("response")
    return None


def store(prompt: str, response: str) -> None:
    client = _client()
    vector = embed(prompt)
    client.upsert(
        collection_name=settings.qdrant_collection,
        points=[
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={"prompt": prompt, "response": response},
            )
        ],
    )
