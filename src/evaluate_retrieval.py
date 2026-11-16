import argparse
import hashlib
import json
import statistics
import time

from starter.baseline import hit, pack_context
from .day6_bridge import Day6Retriever, ROOT
from .prepare_benchmark import digest
from .retrieval import UnifiedRetriever


METHODS = ("dense", "bm25", "hybrid")


def measure(retriever, case, budget):
    started = time.perf_counter()
    try:
        results = retriever.search(
            case["question"],
            filters=case.get("filter"),
            top_k=3,
        )
        context, ids = pack_context(results, budget=budget)
        gold = case.get("gold", [])

        return {
            "query_id": case["id"],
            "method": retriever.method,
            "question": case["question"],
            "answerable": case["answerable"],
            "status": "ok",
            "retrieval": retriever.last_trace,
            "context": context,
            "context_ids": ids,
            "context_budget_chars": budget,
            "context_chars": len(context),
            "hit1": bool(results and hit(results[0], gold)),
            "hit3": any(hit(row, gold) for row in results),
            "context_match": any(
                row["id"] in ids and hit(row, gold)
                for row in results
            ),
            "elapsed_ms": (time.perf_counter() - started) * 1000,
        }

    except Exception as exc:
        return {
            "query_id": case["id"],
            "method": retriever.method,
            "question": case["question"],
            "answerable": case["answerable"],
            "status": "error",
            "error_type": type(exc).__name__,
            "http_status": getattr(exc, "status_code", None),
            "sqlstate": getattr(exc, "sqlstate", None),
            "elapsed_ms": (time.perf_counter() - started) * 1000,
        }


def summarize(cases, latest, method):
    rows = [latest[(method, case["id"])] for case in cases]
    answerable = [row for row in rows if row["answerable"]]
    successful = [row for row in rows if row["status"] == "ok"]

    result = {
        "queries": len(rows),
        "errors": len(rows) - len(successful),
        "median_ms": statistics.median(
            row["elapsed_ms"] for row in successful
        ) if successful else None,
    }

    for name in ("hit1", "hit3", "context_match"):
        n = sum(bool(row.get(name, False)) for row in answerable)
        N = len(answerable)
        result[name] = {
            "n": n,
            "N": N,
            "rate": n / N if N else None,
        }

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--budget", type=int, default=4000)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    if args.budget < 1:
        raise SystemExit("Budget must be positive.")

    benchmark = ROOT / "benchmark"
    cases = json.loads(
        (benchmark / "dev.json").read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (benchmark / "manifest.json").read_text(encoding="utf-8")
    )

    if digest(cases) != manifest["dev_sha256"]:
        raise SystemExit(
            "Dev benchmark changed; inspect changes before running."
        )

    if (
        len(cases) != 17
        or sum(c["answerable"] for c in cases) != 15
        or any(c["split"] != "dev" for c in cases)
    ):
        raise SystemExit(
            "Expected 17 dev cases, including 15 answerable."
        )

    backend = Day6Retriever()
    chunks = backend.load_chunks()

    fingerprint = [
        {
            key: chunk[key]
            for key in ("id", "source_id", "source", "page", "text")
        }
        for chunk in sorted(chunks, key=lambda chunk: chunk["id"])
    ]

    if digest(fingerprint) != manifest["corpus_sha256"]:
        raise SystemExit(
            "Index B differs from the frozen benchmark corpus."
        )

    code_hashes = {
        name: hashlib.sha256(
            (ROOT / "src" / name).read_bytes()
        ).hexdigest()
        for name in (
            "day6_bridge.py",
            "retrieval.py",
            "evaluate_retrieval.py",
        )
    }

    plan = {
        "split": "dev",
        "methods": list(METHODS),
        "top_k": 3,
        "candidate_k": 10,
        "rrf_k": 60,
        "budget_chars": args.budget,
        "dev_sha256": manifest["dev_sha256"],
        "corpus_sha256": manifest["corpus_sha256"],
        "code_hashes": code_hashes,
    }

    directory = ROOT / "results" / "retrieval_dev"
    plan_path = directory / "plan.json"
    trace_path = directory / "traces.jsonl"
    latest, attempts = {}, []

    if plan_path.exists():
        if not args.resume:
            raise SystemExit(
                "Results exist. Use --resume to retry errors or continue."
            )

        previous = json.loads(
            plan_path.read_text(encoding="utf-8")
        )
        if previous != plan:
            raise SystemExit(
                "Resume requires unchanged code, data and settings."
            )

        if trace_path.exists():
            attempts = [
                json.loads(line)
                for line in trace_path.read_text(
                    encoding="utf-8"
                ).splitlines()
                if line.strip()
            ]
            latest = {
                (row["method"], row["query_id"]): row
                for row in attempts
            }

    else:
        if trace_path.exists():
            raise SystemExit(
                "Trace exists without a plan; inspect files first."
            )
        directory.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(
            json.dumps(plan, indent=2),
            encoding="utf-8",
        )

    total = len(cases) * len(METHODS)
    position = 0

    with trace_path.open("a", encoding="utf-8") as stream:
        for method in METHODS:
            retriever = UnifiedRetriever(method, backend=backend)

            for case in cases:
                position += 1
                key = (method, case["id"])

                if (
                    key in latest
                    and latest[key]["status"] == "ok"
                ):
                    print(
                        f"[{position}/{total}] {method} "
                        f"{case['id']} saved success",
                        flush=True,
                    )
                    continue

                print(
                    f"[{position}/{total}] {method} "
                    f"{case['id']} running...",
                    flush=True,
                )

                row = measure(retriever, case, args.budget)

                stream.write(
                    json.dumps(row, ensure_ascii=False) + "\n"
                )
                stream.flush()
                latest[key] = row
                attempts.append(row)

                if row["status"] == "ok":
                    print(
                        f"  OK | {row['elapsed_ms']:.0f} ms",
                        flush=True,
                    )
                else:
                    print(
                        f"  ERROR | {row['error_type']} | "
                        f"HTTP {row['http_status']}",
                        flush=True,
                    )

                    if row["http_status"] in (401, 403, 429):
                        raise SystemExit(
                            "Stopped on access/rate-limit error. "
                            "Fix the cause, then use --resume."
                        )

    summary = {
        "plan": plan,
        "methods": {
            method: summarize(cases, latest, method)
            for method in METHODS
        },
        "failed_attempts": sum(
            row["status"] == "error" for row in attempts
        ),
        "cost_usd": None,
        "notes": [
            "Unanswerable cases are excluded from retrieval metric denominators.",
            "Latest errors on answerable cases count as misses; failed attempts remain in the trace.",
            "Context match checks exact gold quotes, not human context grades or generated answers.",
            "Median includes successful search and context packing; excludes retriever initialization.",
            "Embedding usage is retained per trace; provider cost units have not been converted to USD.",
        ],
    }

    (directory / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        "\nMETHOD | HIT@1 | HIT@3 | "
        "CONTEXT MATCH | MEDIAN MS | ERRORS"
    )

    for method, row in summary["methods"].items():
        values = [
            f"{row[name]['n']}/{row[name]['N']}"
            for name in ("hit1", "hit3", "context_match")
        ]
        median = (
            f"{row['median_ms']:.2f}"
            if row["median_ms"] is not None else "N/A"
        )
        print(
            f"{method} | {' | '.join(values)} | "
            f"{median} | {row['errors']}"
        )

    print(
        "Saved: results/retrieval_dev/summary.json and traces.jsonl"
    )


if __name__ == "__main__":
    main()
