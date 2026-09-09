"""RAG retriever with pgvector and ACL filtering.

Retrieves relevant document chunks for a given query, filtered by:
- Client ID (only chunks belonging to the target client)
- ACL groups (only chunks the requesting RM is authorized to see)

Falls back to ILIKE keyword search when vector search returns no results
or when the embedding provider fails.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy import text, or_, func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.rag.embeddings import get_embedding_provider

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """A retrieved document chunk with metadata."""
    chunk_id: str
    document_id: str
    content: str
    score: float
    document_type: Optional[str] = None
    document_title: Optional[str] = None


def _apply_acl_filter(query, acl_groups, acl_enabled):
    """Apply ACL filtering on a query.

    Works on both PostgreSQL (JSONB) and SQLite (JSON text).
    """
    if not acl_enabled or not acl_groups:
        return query

    from app.db.models import Chunk

    acl_conditions = []
    for group in acl_groups:
        # Cast JSONB to text so LIKE works on PostgreSQL
        acl_conditions.append(
            func.cast(Chunk.acl_groups, func.type_coerce("text")).like(f'%"{group}"%')
        )

    return query.filter(or_(*acl_conditions))


def retrieve(
    db: Session,
    query: str,
    client_id: str,
    rm_acl_groups: Optional[List[str]] = None,
    top_k: Optional[int] = None,
) -> List[RetrievedChunk]:
    """Retrieve relevant chunks for a query with ACL filtering."""
    settings = get_settings()
    k = top_k or settings.rag_top_k
    acl_enabled = settings.rag_acl_enabled

    try:
        results = _vector_search(db, query, client_id, rm_acl_groups, k, acl_enabled)
        if results:
            return results
    except Exception as e:
        logger.warning("Vector search failed: %s, falling back to keyword search", e)

    return _keyword_search(db, query, client_id, rm_acl_groups, k, acl_enabled)


def _vector_search(
    db: Session,
    query: str,
    client_id: str,
    rm_acl_groups: Optional[List[str]],
    top_k: int,
    acl_enabled: bool,
) -> List[RetrievedChunk]:
    """Perform vector similarity search using embeddings."""
    embedder = get_embedding_provider()
    query_embedding = embedder.embed([query])[0]

    from app.db.models import Chunk, Document

    q = (
        db.query(Chunk, Document)
        .join(Document, Chunk.document_id == Document.id)
        .filter(Chunk.client_id == client_id)
    )

    q = _apply_acl_filter(q, rm_acl_groups, acl_enabled)

    chunks = q.limit(top_k * 2).all()

    if not chunks:
        return []

    import numpy as np
    query_vec = np.array(query_embedding)
    results = []

    for chunk, doc in chunks:
        if chunk.embedding is None:
            continue
        chunk_vec = np.array(chunk.embedding)
        norm_q = np.linalg.norm(query_vec)
        norm_c = np.linalg.norm(chunk_vec)
        if norm_q > 0 and norm_c > 0:
            similarity = float(np.dot(query_vec, chunk_vec) / (norm_q * norm_c))
        else:
            similarity = 0.0

        results.append(RetrievedChunk(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            content=chunk.content,
            score=similarity,
            document_type=doc.document_type,
            document_title=doc.title,
        ))

    results.sort(key=lambda x: x.score, reverse=True)
    return results[:top_k]


def _keyword_search(
    db: Session,
    query: str,
    client_id: str,
    rm_acl_groups: Optional[List[str]],
    top_k: int,
    acl_enabled: bool,
) -> List[RetrievedChunk]:
    """Fallback keyword search using ILIKE."""
    from app.db.models import Chunk, Document

    keywords = [w.strip() for w in query.split() if len(w.strip()) > 2]
    if not keywords:
        keywords = [query]

    q = (
        db.query(Chunk, Document)
        .join(Document, Chunk.document_id == Document.id)
        .filter(Chunk.client_id == client_id)
    )

    q = _apply_acl_filter(q, rm_acl_groups, acl_enabled)

    keyword_conditions = []
    for kw in keywords:
        keyword_conditions.append(Chunk.content.ilike(f"%{kw}%"))
    q = q.filter(or_(*keyword_conditions))

    rows = q.limit(top_k).all()

    results = []
    for chunk, doc in rows:
        content_lower = chunk.content.lower()
        score = sum(1 for kw in keywords if kw.lower() in content_lower) / max(len(keywords), 1)

        results.append(RetrievedChunk(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            content=chunk.content,
            score=score,
            document_type=doc.document_type,
            document_title=doc.title,
        ))

    results.sort(key=lambda x: x.score, reverse=True)
    return results


def retrieve_all_for_client(
    db: Session,
    client_id: str,
    rm_acl_groups: Optional[List[str]] = None,
    limit: int = 50,
) -> List[RetrievedChunk]:
    """Retrieve all chunks for a client (for data validation).

    Applies ACL filtering when rm_acl_groups is provided.
    """
    from app.db.models import Chunk, Document
    from app.core.config import get_settings

    settings = get_settings()
    acl_enabled = settings.rag_acl_enabled

    q = (
        db.query(Chunk, Document)
        .join(Document, Chunk.document_id == Document.id)
        .filter(Chunk.client_id == client_id)
    )

    q = _apply_acl_filter(q, rm_acl_groups, acl_enabled)

    rows = q.limit(limit).all()
    return [
        RetrievedChunk(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            content=chunk.content,
            score=1.0,
            document_type=doc.document_type,
            document_title=doc.title,
        )
        for chunk, doc in rows
    ]