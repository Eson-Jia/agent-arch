from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

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
        *,
        uri: str | None = None,
        token: str | None = None,
    ) -> None:
        if embedding_provider is None:
            raise ValueError("embedding_provider is required")
        try:
            from pymilvus import DataType, MilvusClient
        except ImportError as exc:
            raise RuntimeError("pymilvus is required; run `uv sync --extra dev` to install Milvus support") from exc

        self.path = path
        self.collection_name = collection_name
        self.embedding_provider = embedding_provider
        self._client_type = MilvusClient
        self._data_type = DataType
        self._local_uri = self._resolve_local_uri(path)
        self.uri = uri or self._local_uri
        self.token = token
        self.vector_field = "embedding"
        self.text_field = "text"
        self.metadata_field = "metadata"
        self.doc_name_field = "doc_name"
        self.chunk_index_field = "chunk_index"
        self._dims = len(self.embedding_provider.embed("milvus vector store bootstrap"))
        self.client = self._build_client()
        self._ensure_collection()

    def _resolve_local_uri(self, path: Path) -> str:
        if path.suffix:
            path.parent.mkdir(parents=True, exist_ok=True)
            return str(path)
        path.mkdir(parents=True, exist_ok=True)
        return str(path / "milvus_lite.db")

    def _build_client(self):
        if self.token:
            return self._client_type(uri=self.uri, token=self.token)
        return self._client_type(uri=self.uri)

    def _collection_exists(self) -> bool:
        try:
            return self.client.has_collection(collection_name=self.collection_name)
        except Exception:
            return self.collection_name in self.client.list_collections()

    def _create_collection(self) -> None:
        schema = self._client_type.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field(field_name="id", datatype=self._data_type.VARCHAR, is_primary=True, max_length=512)
        schema.add_field(field_name=self.vector_field, datatype=self._data_type.FLOAT_VECTOR, dim=self._dims)
        schema.add_field(field_name=self.text_field, datatype=self._data_type.VARCHAR, max_length=8192)
        schema.add_field(field_name=self.doc_name_field, datatype=self._data_type.VARCHAR, max_length=512)
        schema.add_field(field_name=self.chunk_index_field, datatype=self._data_type.INT64)
        schema.add_field(field_name=self.metadata_field, datatype=self._data_type.JSON)

        index_params = self._client_type.prepare_index_params()
        index_params.add_index(
            field_name=self.vector_field,
            index_name="kb_vector_idx",
            index_type="AUTOINDEX",
            metric_type="COSINE",
        )
        self.client.create_collection(
            collection_name=self.collection_name,
            schema=schema,
            index_params=index_params,
        )

    def _ensure_collection(self) -> None:
        if not self._collection_exists():
            self._create_collection()

    def reset(self) -> None:
        if self._collection_exists():
            self.client.drop_collection(collection_name=self.collection_name)
        self._create_collection()

    def upsert_documents(self, docs: list[dict[str, Any]]) -> None:
        if not docs:
            return
        texts = [doc["text"] for doc in docs]
        embeddings = self.embedding_provider.embed_many(texts)
        rows: list[dict[str, Any]] = []
        for doc, embedding in zip(docs, embeddings):
            metadata = doc.get("metadata", {}) or {}
            rows.append(
                {
                    "id": str(doc["id"]),
                    self.vector_field: embedding,
                    self.text_field: doc["text"],
                    self.doc_name_field: str(metadata.get("doc_name", "")),
                    self.chunk_index_field: int(metadata.get("chunk_index", 0)),
                    self.metadata_field: json.loads(json.dumps(metadata, ensure_ascii=False, default=str)),
                }
            )
        self.client.upsert(collection_name=self.collection_name, data=rows)

    def search(self, query: str, k: int = 3) -> list[SearchHit]:
        results = self.client.search(
            collection_name=self.collection_name,
            data=[self.embedding_provider.embed(query)],
            limit=k,
            output_fields=[self.text_field, self.metadata_field],
            search_params={"metric_type": "COSINE"},
        )
        rows = results[0] if results and isinstance(results[0], list) else results
        hits: list[SearchHit] = []
        for row in rows or []:
            entity = row.get("entity", {}) if isinstance(row, dict) else {}
            metadata = entity.get(self.metadata_field) or row.get(self.metadata_field) or {}
            snippet = entity.get(self.text_field) or row.get(self.text_field) or ""
            doc_id = row.get("id") or entity.get("id") or ""
            score = float(row.get("distance", 0.0) or 0.0)
            hits.append(
                SearchHit(
                    doc_id=str(doc_id),
                    snippet=str(snippet)[:240],
                    score=score,
                    metadata=metadata if isinstance(metadata, dict) else {},
                )
            )
        return hits
