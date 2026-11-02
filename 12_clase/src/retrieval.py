"""Hybrid retrieval: BM25 + Atlas Vector Search, fused with RRF and reranked with Cohere."""

import re
import unicodedata
from collections import defaultdict
from collections.abc import Sequence

from langchain_cohere import CohereRerank
from langchain_core.documents import BaseDocumentCompressor, Document
from langchain_mongodb import MongoDBAtlasVectorSearch
from pymongo import MongoClient
from rank_bm25 import BM25Okapi

from src.config import Settings
from src.llm import embeddings


def tokenize(text: str) -> list[str]:
    """Lowercase and strip accents so 'térmica' matches 'termica'."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.findall(r"\w+", plain.lower())


def reciprocal_rank_fusion(rankings: Sequence[Sequence[str]], k: int = 60) -> list[str]:
    """RRF_score(d) = sum over rankings of 1 / (k + rank(d)), rank starting at 1."""
    scores: dict[str, float] = defaultdict(float)
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] += 1 / (k + rank)
    return sorted(scores, key=scores.__getitem__, reverse=True)


class HybridRetriever:
    def __init__(
        self,
        vectorstore: MongoDBAtlasVectorSearch,
        documents: list[Document],
        reranker: BaseDocumentCompressor,
        *,
        k_candidates: int,
        rrf_k: int,
    ) -> None:
        if not documents:
            raise ValueError("Empty index: run `uv run main.py ingest` first")
        self.vectorstore = vectorstore
        self.documents = documents
        self.by_id = {d.id: d for d in documents}
        self.bm25 = BM25Okapi([tokenize(d.page_content) for d in documents])
        self.reranker = reranker
        self.k_candidates = k_candidates
        self.rrf_k = rrf_k

    def _bm25_ids(self, query: str) -> list[str]:
        scores = self.bm25.get_scores(tokenize(query))
        ranked = sorted(zip(self.documents, scores), key=lambda pair: pair[1], reverse=True)
        return [d.id for d, score in ranked[: self.k_candidates] if score > 0]

    def search(self, query: str) -> list[Document]:
        dense = self.vectorstore.similarity_search(query, k=self.k_candidates)
        fused = reciprocal_rank_fusion([self._bm25_ids(query), [d.id for d in dense]], k=self.rrf_k)
        candidates = [self.by_id[doc_id] for doc_id in fused[: self.k_candidates]]
        return list(self.reranker.compress_documents(candidates, query))


def open_vectorstore(settings: Settings, client: MongoClient) -> MongoDBAtlasVectorSearch:
    """Vector store over a Mongo collection; the Atlas index is created by the ingest stage."""
    collection = client[settings.vectorstore.database][settings.collection_name]
    return MongoDBAtlasVectorSearch(
        collection,
        embeddings(settings),
        index_name=settings.vectorstore.index,
        relevance_score_fn="cosine",
    )


def load_documents(store: MongoDBAtlasVectorSearch) -> list[Document]:
    """Read every chunk back (without its vector): BM25 is built in memory from them."""
    return [
        Document(id=record.pop("_id"), page_content=record.pop("text"), metadata=record)
        for record in store.collection.find({}, {"embedding": 0})
    ]


def build_retriever(settings: Settings, client: MongoClient) -> HybridRetriever:
    store = open_vectorstore(settings, client)
    reranker = CohereRerank(
        model=settings.retrieval.rerank_model,
        top_n=settings.retrieval.top_n,
        cohere_api_key=settings.secrets.cohere_api_key,
    )
    return HybridRetriever(
        store,
        load_documents(store),
        reranker,
        k_candidates=settings.retrieval.k_candidates,
        rrf_k=settings.retrieval.rrf_k,
    )
