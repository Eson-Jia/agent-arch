from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings


@dataclass
class SearchHit:
    doc_id: str
    snippet: str
    score: float
    metadata: dict[str, Any]


class MockEmbedding:
    def __init__(self, dims: int = 32) -> None:
        self.dims = dims

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dims
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for index in range(self.dims):
                vector[index] += digest[index % len(digest)] / 255.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


class VectorStore:
    def __init__(self, path: Path, collection_name: str = "knowledge_base") -> None:
        self.path = path
        self.path.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(self.path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection_name = collection_name
        self.collection = self.client.get_or_create_collection(name=collection_name)
        self.embedding = MockEmbedding()

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
        embeddings = [self.embedding.embed(text) for text in documents]
        self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)

    def search(self, query: str, k: int = 3) -> list[SearchHit]:
        results = self.collection.query(query_embeddings=[self.embedding.embed(query)], n_results=k)
        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        distances = results.get("distances", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        hits: list[SearchHit] = []
        for doc_id, document, distance, metadata in zip(ids, documents, distances, metadatas):
            score = max(0.0, 1.0 - float(distance))
            hits.append(SearchHit(doc_id=doc_id, snippet=document[:240], score=score, metadata=metadata or {}))
        return hits
