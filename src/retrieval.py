import argparse
import json
import re
import time
import unicodedata
from pathlib import Path

import psycopg
from openai import OpenAIError
from rank_bm25 import BM25Okapi

from .day6_bridge import Day6Retriever


def tokenize(text):
    return re.findall(r"\w+", unicodedata.normalize("NFC", text).casefold())


class UnifiedRetriever:
    def __init__(self, method="hybrid", candidate_k=10, rrf_k=60, backend=None):
        if method not in ("dense", "bm25", "hybrid"):
            raise ValueError("Unknown retrieval method.")
        if type(candidate_k) is not int or candidate_k < 1:
            raise ValueError("candidate_k must be a positive integer.")
        if type(rrf_k) is not int or rrf_k < 1:
            raise ValueError("rrf_k must be a positive integer.")

        self.method = method
        self.candidate_k = candidate_k
        self.rrf_k = rrf_k
        self.backend = backend if backend is not None else Day6Retriever()
        self.chunks = self.backend.load_chunks()

        tokens = [tokenize(chunk["text"]) for chunk in self.chunks]
        if not tokens or not any(tokens):
            raise ValueError("Corpus has no searchable text.")

        self.bm25 = BM25Okapi(tokens, k1=1.5, b=0.75)
        self.last_trace = None

    def lexical_search(self, query, filters, top_k):
        scores = self.bm25.get_scores(tokenize(query))
        rows = [
            {**chunk, "score": float(score)}
            for chunk, score in zip(self.chunks, scores)
            if score > 0 and all(
                chunk["metadata"].get(key) == value
                for key, value in filters.items()
            )
        ]
        return sorted(
            rows, key=lambda row: (-row["score"], row["id"])
        )[:top_k]

    def search(self, query, *, filters=None, top_k=3):
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Query must be a nonempty string.")
        if type(top_k) is not int or top_k < 1:
            raise ValueError("top_k must be a positive integer.")

        filters = {} if filters is None else filters
        if not isinstance(filters, dict) or set(filters) - {"category"}:
            raise ValueError("Only the category filter is supported.")
        if filters and filters["category"] not in ("business", "technology"):
            raise ValueError("Unsupported category.")

        self.last_trace = None
        self.backend.last_usage = None
        started = time.perf_counter()
        dense, lexical = [], []
        count = (
            max(top_k, self.candidate_k)
            if self.method == "hybrid" else top_k
        )

        if self.method in ("dense", "hybrid"):
            dense = self.backend.search(
                query, filters=filters, top_k=count
            )
        if self.method in ("bm25", "hybrid"):
            lexical = self.lexical_search(query, filters, count)

        if self.method == "dense":
            results = dense
        elif self.method == "bm25":
            results = lexical
        else:
            merged = {}
            for name, rows in (("dense", dense), ("bm25", lexical)):
                for rank, row in enumerate(rows, 1):
                    entry = merged.setdefault(
                        row["id"], {**row, "score": 0.0}
                    )
                    entry["score"] += 1.0 / (self.rrf_k + rank)
                    entry[name + "_rank"] = rank
                    entry[name + "_score"] = row["score"]

            results = sorted(
                merged.values(),
                key=lambda row: (-row["score"], row["id"]),
            )[:top_k]

        self.last_trace = {
            "method": self.method,
            "query": query,
            "filters": dict(filters),
            "top_k": top_k,
            "candidate_k": count,
            "rrf_k": self.rrf_k if self.method == "hybrid" else None,
            "bm25": {
                "k1": 1.5,
                "b": 0.75,
                "tokenizer": "NFC-casefold-word",
            },
            "dense_candidates": dense,
            "bm25_candidates": lexical,
            "results": results,
            "elapsed_ms": (time.perf_counter() - started) * 1000,
            "embedding_usage": self.backend.last_usage,
        }
        return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--method", choices=("dense", "bm25", "hybrid"), required=True
    )
    parser.add_argument("--question", required=True)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--candidate-k", type=int, default=10)
    parser.add_argument("--rrf-k", type=int, default=60)
    parser.add_argument("--category", choices=("business", "technology"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    started = time.perf_counter()
    retriever = UnifiedRetriever(
        args.method, args.candidate_k, args.rrf_k
    )
    setup_ms = (time.perf_counter() - started) * 1000
    filters = {"category": args.category} if args.category else None

    results = retriever.search(
        args.question, filters=filters, top_k=args.top_k
    )
    trace = {
        "status": "ok",
        "chunks": len(retriever.chunks),
        "setup_ms": setup_ms,
        **retriever.last_trace,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(trace, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Method: {args.method} | Chunks: {len(retriever.chunks)}")
    for rank, row in enumerate(results, 1):
        print(
            f"\nRank {rank} | {row['source_id']} | "
            f"score={row['score']:.6f}"
        )
        print(f"ID: {row['id']}")
        print(row["text"])
    print(f"\nSaved: {args.output}")


if __name__ == "__main__":
    try:
        main()
    except OpenAIError as exc:
        raise SystemExit(
            f"Embedding API error: {type(exc).__name__}; "
            f"HTTP {getattr(exc, 'status_code', None)}"
        ) from None
    except psycopg.Error as exc:
        raise SystemExit(
            f"Database error: {type(exc).__name__}; "
            f"SQLSTATE {exc.sqlstate}"
        ) from None
