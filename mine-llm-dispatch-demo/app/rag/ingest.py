from __future__ import annotations

from pathlib import Path

from app.storage.vector_store import VectorStore


def _chunk_text(text: str, max_lines: int = 8) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    chunks: list[str] = []
    for index in range(0, len(lines), max_lines):
        chunks.append("\n".join(lines[index : index + max_lines]))
    return chunks or [text.strip()]


def ingest_knowledge_base(store: VectorStore, knowledge_base_path: Path) -> int:
    docs: list[dict] = []
    for doc_path in sorted(knowledge_base_path.glob("*.md")):
        text = doc_path.read_text(encoding="utf-8")
        for chunk_index, chunk in enumerate(_chunk_text(text)):
            docs.append(
                {
                    "id": f"DOC-{doc_path.name}#chunk-{chunk_index}",
                    "text": chunk,
                    "metadata": {
                        "doc_name": doc_path.name,
                        "chunk_index": chunk_index,
                    },
                }
            )
    store.reset()
    store.upsert_documents(docs)
    return len(docs)
