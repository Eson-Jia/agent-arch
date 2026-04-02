from app.storage.vector_store import SearchHit, VectorStore


def retrieve_top_k(store: VectorStore, query: str, k: int = 3) -> list[SearchHit]:
    return store.search(query, k=k)
