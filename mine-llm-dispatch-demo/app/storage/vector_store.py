from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.embeddings.providers import EmbeddingProvider

@dataclass
class SearchHit:
    doc_id: str
    snippet: str
    score: float
    metadata: dict[str, Any]

class VectorStore:
    def __init__(
        self,
        path: Path,
        collection_name: str = "knowledge_base",
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.path = path
        self.path.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(self.path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection_name = collection_name
        self.collection = self.client.get_or_create_collection(name=collection_name)
        self.embedding_provider = embedding_provider
        if self.embedding_provider is None:
            raise ValueError("embedding_provider is required")

    def reset(self) -> None:
        try:
            self.client.delete_collection(self.collection_name)
        except ValueError:
            pass
        self.collection = self.client.get_or_create_collection(name=self.collection_name)

    def upsert_documents(self, docs: list[dict[str, Any]]) -> None:
        if not docs:
            return
        ids = [doc["id"] for doc in docs]
        documents = [doc["text"] for doc in docs]
        metadatas = [doc["metadata"] for doc in docs]
        embeddings = self.embedding_provider.embed_many(documents)
        self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)

    def search(self, query: str, k: int = 3) -> list[SearchHit]:
        results = self.collection.query(query_embeddings=[self.embedding_provider.embed(query)], n_results=k)
        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        distances = results.get("distances", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        hits: list[SearchHit] = []
        for doc_id, document, distance, metadata in zip(ids, documents, distances, metadatas):
            score = max(0.0, 1.0 - float(distance))
            hits.append(SearchHit(doc_id=doc_id, snippet=document[:240], score=score, metadata=metadata or {}))
        return hits
