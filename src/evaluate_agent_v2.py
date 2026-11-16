import argparse
import hashlib
import json
import re
import statistics

from dotenv import dotenv_values
from starter.baseline import hit
from .agent_v2 import RAGAgent
from .day6_bridge import Day6Retriever, ROOT
from .prepare_benchmark import digest


PROFILES = {'auto_english_v2': {'hypothesis': 'Explicit English output, strict abstention citation consistency, and question-focused answers address observed v1 failures.', 'params': {'method': 'auto', 'top_k': 3, 'budget': 4000, 'max_searches': 3}}}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def fraction(n, N):
    return {"n": n, "N": N, "rate": n / N if N else None}


def summarize(cases, rows, chunks):
    successes = [
        row for row in rows if row["status"] != "error"
    ]
    answerable = [
        (case, row)
        for case, row in zip(cases, rows)
        if case["answerable"]
    ]
    scores = {
        "first_search_hit1": 0,
        "first_search_hit3": 0,
        "context_match": 0,
    }

    for case, row in answerable:
        searches = [
            event for event in row["events"]
            if event["event"] == "search"
        ]
        first = searches[0]["results"] if searches else []

        scores["first_search_hit1"] += bool(
            first and hit(first[0], case["gold"])
        )
        scores["first_search_hit3"] += any(
            hit(chunk, case["gold"]) for chunk in first[:3]
        )
        scores["context_match"] += any(
            chunk_id in chunks
            and hit(chunks[chunk_id], case["gold"])
            for chunk_id in row["context_ids"]
        )

    return {
        "queries": len(rows),
        "answered": sum(
            row["status"] == "answered" for row in rows
        ),
        "abstain": sum(
            row["status"] == "abstain" for row in rows
        ),
        "errors": sum(
            row["status"] == "error" for row in rows
        ),
        "tool_use": fraction(
            sum(
                any(
                    event["event"] == "search"
                    for event in row["events"]
                )
                for row in successes
            ),
            len(successes),
        ),
        "median_ms": (
            statistics.median(
                row["elapsed_ms"] for row in successes
            )
            if successes else None
        ),
        **{
            name: fraction(n, len(answerable))
            for name, n in scores.items()
        },
        "human_review": (
            "pending; statuses are not answer-quality grades"
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-name", default="agent_dev_v2")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.run_name):
        raise SystemExit(
            "Use letters, digits, underscores or hyphens for run-name."
        )

    benchmark = ROOT / "benchmark"
    cases = read_json(benchmark / "dev.json")
    manifest = read_json(benchmark / "manifest.json")

    if (
        digest(cases) != manifest["dev_sha256"]
        or len(cases) != 17
        or sum(case["answerable"] for case in cases) != 15
        or any(case["split"] != "dev" for case in cases)
    ):
        raise SystemExit(
            "Dev benchmark does not match the frozen manifest."
        )

    chunks = Day6Retriever().load_chunks()
    fingerprint = [
        {
            key: chunk[key]
            for key in ("id", "source_id", "source", "page", "text")
        }
        for chunk in sorted(chunks, key=lambda chunk: chunk["id"])
    ]
    if digest(fingerprint) != manifest["corpus_sha256"]:
        raise SystemExit(
            "Index B changed. Inspect the corpus before running."
        )
    chunk_map = {chunk["id"]: chunk for chunk in chunks}

    config = dotenv_values(
        ROOT / ".env", encoding="utf-8-sig"
    )
    model = config.get("AGENT_MODEL")
    if not model:
        raise SystemExit("AGENT_MODEL is missing.")

    files = (
        "src/agent_v2.py",
        "src/retrieval.py",
        "src/day6_bridge.py",
        "src/evaluate_agent_v2.py",
        "starter/baseline.py",
    )
    plan = {
        "split": "dev",
        "model": model,
        "profiles": PROFILES,
        "dev_sha256": manifest["dev_sha256"],
        "corpus_sha256": manifest["corpus_sha256"],
        "code_hashes": {
            name: hashlib.sha256(
                (ROOT / name).read_bytes()
            ).hexdigest()
            for name in files
        },
        "selection_rule": manifest["selection_rule"],
    }

    directory = ROOT / "results" / args.run_name
    plan_path = directory / "plan.json"

    if plan_path.exists():
        if not args.resume:
            raise SystemExit(
                "Run exists. Use --resume or choose a new --run-name."
            )
        if read_json(plan_path) != plan:
            raise SystemExit(
                "Code, model, data or settings changed. "
                "Use a new --run-name."
            )
    else:
        if directory.exists() and any(directory.iterdir()):
            raise SystemExit(
                "Output directory is not empty; choose another run-name."
            )
        directory.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(
            json.dumps(plan, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    total = len(cases) * len(PROFILES)
    position = 0
    summaries = {}

    for profile_id, profile in PROFILES.items():
        agent = RAGAgent(
            **profile["params"],
            model=model,
            verbose=True,
        )
        rows = []

        try:
            for case in cases:
                position += 1
                path = (
                    directory / profile_id
                    / (case["id"] + ".json")
                )

                if path.exists():
                    previous = read_json(path)
                    if previous["status"] != "error":
                        rows.append(previous)
                        print(
                            f"[{position}/{total}] {profile_id} "
                            f"{case['id']} saved success",
                            flush=True,
                        )
                        continue

                print(
                    f"\n[{position}/{total}] {profile_id} "
                    f"{case['id']} running...",
                    flush=True,
                )

                result = agent.run(
                    case["question"], case.get("filter")
                )
                result.update(
                    query_id=case["id"],
                    split="dev",
                    profile_id=profile_id,
                )

                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    json.dumps(
                        result, ensure_ascii=False, indent=2
                    ),
                    encoding="utf-8",
                )
                rows.append(result)

                print(
                    f"STATUS={result['status']} | "
                    f"searches={result['search_calls']} | "
                    f"model_calls={result['model_calls']}",
                    flush=True,
                )

                if result["status"] == "error":
                    with (
                        directory / "failed_attempts.jsonl"
                    ).open("a", encoding="utf-8") as stream:
                        stream.write(
                            json.dumps(
                                result, ensure_ascii=False
                            ) + "\n"
                        )

                    print(
                        "ERROR:",
                        result["termination_reason"],
                        flush=True,
                    )

                    last_error = next(
                        (
                            event
                            for event in reversed(result["events"])
                            if event["event"] == "error"
                        ),
                        {},
                    )
                    if last_error.get("http_status") in (
                        401, 403, 429
                    ):
                        raise SystemExit(
                            "Stopped on access/rate-limit error. "
                            "Fix the cause, then use --resume."
                        )
        finally:
            agent.client.close()

        summaries[profile_id] = summarize(
            cases, rows, chunk_map
        )

    summary = {
        "split": "dev",
        "model": model,
        "profiles": summaries,
        "cost_usd": None,
        "notes": [
            "Only dev was run. No test question was sent to the agent.",
            "Gold and expected answers were used only after agent.run returned.",
            "Agent first-search metrics use model-generated queries; original-query metrics are in results/retrieval_dev.",
            "Context match is an exact-quote check, not a human context grade.",
            "Answered/abstain are statuses, not correctness or abstention grades.",
            "Model and embedding usage remain in each trace; USD conversion is unverified.",
        ],
    }

    (directory / "automatic_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        "\nPROFILE | ANSWERED | ABSTAIN | ERRORS | "
        "FIRST HIT@3 | CONTEXT MATCH | MEDIAN MS"
    )

    for profile_id, row in summaries.items():
        hit3 = row["first_search_hit3"]
        context = row["context_match"]
        median = (
            f"{row['median_ms']:.2f}"
            if row["median_ms"] is not None else "N/A"
        )

        print(
            f"{profile_id} | {row['answered']} | "
            f"{row['abstain']} | {row['errors']} | "
            f"{hit3['n']}/{hit3['N']} | "
            f"{context['n']}/{context['N']} | {median}"
        )

    print(
        "Saved:",
        directory / "automatic_summary.json",
    )
    print(
        "Answer correctness, citation support and "
        "abstention still require review."
    )


if __name__ == "__main__":
    main()
