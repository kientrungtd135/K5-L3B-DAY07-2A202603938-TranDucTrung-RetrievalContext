import argparse
import json
import math
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from dotenv import dotenv_values
from openai import OpenAI, OpenAIError


ROOT = Path(__file__).resolve().parents[1]
DIMENSIONS = 1536


class Day6Retriever:
    def __init__(self):
        self.config = dotenv_values(ROOT / ".env", encoding="utf-8-sig")
        required = (
            "DATABASE_URL",
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
            "EMBEDDING_MODEL",
        )
        missing = [key for key in required if not self.config.get(key)]
        if missing:
            raise ValueError("Missing settings: " + ", ".join(missing))
        if self.config["EMBEDDING_MODEL"] != "text-embedding-3-small":
            raise ValueError("Embedding model must match the Day 6 index.")
        self.last_usage = None

    def connect(self):
        connection = psycopg.connect(
            self.config["DATABASE_URL"],
            connect_timeout=10,
            row_factory=dict_row,
        )
        connection.read_only = True
        return connection

    def load_chunks(self):
        with self.connect() as connection:
            rows = connection.execute("""
                SELECT chunk_id AS id, document_id AS source_id,
                       source, page, text, metadata,
                       vector_dims(embedding) AS dimensions
                FROM public.day6_chunks
                WHERE strategy = %s
                ORDER BY chunk_id
            """, ("B",)).fetchall()

        if not rows:
            raise ValueError("Index B is empty.")
        for row in rows:
            if row.pop("dimensions") != DIMENSIONS:
                raise ValueError("Incompatible vector dimensions.")
        return rows

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

        with OpenAI(
            api_key=self.config["OPENAI_API_KEY"],
            base_url=self.config["OPENAI_BASE_URL"],
            timeout=60,
            max_retries=1,
        ) as client:
            response = client.embeddings.create(
                model=self.config["EMBEDDING_MODEL"],
                input=[query],
            )

        if len(response.data) != 1 or response.data[0].index != 0:
            raise ValueError("Unexpected embedding response.")

        vector = response.data[0].embedding
        if (
            len(vector) != DIMENSIONS
            or not all(math.isfinite(value) for value in vector)
            or not any(vector)
        ):
            raise ValueError("Invalid query embedding.")

        self.last_usage = (
            response.usage.model_dump() if response.usage else None
        )
        literal = json.dumps(vector, allow_nan=False)

        category_sql = (
            " AND metadata ->> 'category' = %s" if filters else ""
        )
        params = [literal, "B"]
        if filters:
            params.append(filters["category"])
        params.extend([literal, top_k])

        with self.connect() as connection:
            rows = connection.execute("""
                SELECT chunk_id AS id, document_id AS source_id,
                       source, page, text, metadata,
                       1 - (embedding <=> %s::vector) AS score
                FROM public.day6_chunks
                WHERE strategy = %s
            """ + category_sql + """
                ORDER BY embedding <=> %s::vector, chunk_id
                LIMIT %s
            """, params).fetchall()

        return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--question")
    args = parser.parse_args()

    retriever = Day6Retriever()
    chunks = retriever.load_chunks()
    documents = len({chunk["source_id"] for chunk in chunks})

    print(
        f"Strategy B: {len(chunks)} chunks; "
        f"{documents} documents; {DIMENSIONS} dimensions"
    )

    if args.question:
        results = retriever.search(args.question)
        for rank, chunk in enumerate(results, 1):
            print(
                f"\nRank {rank} | {chunk['id']} | "
                f"score={chunk['score']:.4f}"
            )
            print(f"Source: {chunk['source']} | page={chunk['page']}")
            print(chunk["text"])

        print("\nEmbedding usage:", json.dumps(retriever.last_usage))


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
