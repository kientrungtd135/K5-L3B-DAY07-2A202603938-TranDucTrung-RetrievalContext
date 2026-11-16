"""Summarize saved traces and AI-proposed reviews without API calls."""
import copy
import hashlib
import json
import re
import statistics
from collections import Counter
from pathlib import Path
from starter.agent_metrics import aggregate

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def lines(path):
    return [
        json.loads(s)
        for s in path.read_text(encoding="utf-8-sig").splitlines()
        if s.strip()
    ] if path.exists() else []

def usage(rows):
    model, embedding = [], []
    repairs = non_tool = embedding_calls = 0

    for row in rows:
        for event in row.get("events", []):
            if event["event"] == "model":
                model.append(event.get("usage") or {})
                non_tool += not event.get("response", {}).get("tool_calls")
            repairs += event["event"] in ("invalid_final", "invalid_search")

        retrievals = [
            e.get("retrieval") or {}
            for e in row.get("events", [])
            if e["event"] == "search"
        ]
        if "retrieval" in row:
            retrievals.append(row["retrieval"] or {})

        for retrieval in retrievals:
            if retrieval.get("method") in ("dense", "hybrid"):
                embedding_calls += 1
                embedding.append(retrieval.get("embedding_usage") or {})

    result = {
        "model_sdk_calls": sum(r.get("model_calls", 0) for r in rows),
        "search_calls": sum(r.get("search_calls", 0) for r in rows),
        "embedding_calls_with_trace": embedding_calls,
        "format_repairs": repairs,
        "non_tool_model_turns": non_tool,
    }

    for kind, values in (("model", model), ("embedding", embedding)):
        totals = [
            v["total_tokens"]
            for v in values
            if type(v.get("total_tokens")) is int
        ]
        costs = [(v.get("x_ckey") or {}).get("cost") for v in values]
        costs = [c for c in costs if type(c) in (int, float)]
        result[kind] = {
            "responses": len(values),
            "token_usage_responses": len(totals),
            "total_tokens": sum(totals) if totals else None,
            "cost_responses": len(costs),
            "provider_cost_raw": sum(costs) if costs else None,
        }
    return result

def main():
    frozen = read(ROOT / "configs/final_selection.json")

    for name, expected in frozen["code_hashes"].items():
        if sha(ROOT / name) != expected:
            raise SystemExit("Frozen code changed: " + name)

    for run, expected in frozen["dev_review_hashes"].items():
        if sha(ROOT / "results" / run / "reviews.json") != expected:
            raise SystemExit("Frozen dev reviews changed: " + run)

    cards = []
    runs = (
        ("agent_dev_v1", "dev"),
        ("agent_dev_v2", "dev"),
        ("agent_test_final", "test"),
    )

    for run, split in runs:
        directory = ROOT / "results" / run
        cases = read(ROOT / "benchmark" / (split + ".json"))
        all_reviews = read(directory / "reviews.json")

        for profile in read(directory / "plan.json")["profiles"]:
            reviews = [r for r in all_reviews if r["profile_id"] == profile]
            by_id = {r["query_id"]: r for r in reviews}

            if len(reviews) != len(cases) or set(by_id) != {c["id"] for c in cases}:
                raise SystemExit("Review identities mismatch: " + profile)

            rows, adjusted_rows, adjusted_reviews = [], [], []
            context_grades = []
            language_errors = format_errors = 0

            for case in cases:
                path = directory / profile / (case["id"] + ".json")
                trace, review = read(path), by_id[case["id"]]

                if (
                    review["review_status"] not in ("ai_proposed", "human_confirmed")
                    or sha(path) != review["trace_sha256"]
                ):
                    raise SystemExit("Missing or stale review: " + str(path))

                rows.append(trace)
                t, r = copy.deepcopy(trace), copy.deepcopy(review)
                inline = list(dict.fromkeys(
                    re.findall(r"\[([^\[\]]+)\]", trace["answer"])
                ))
                extra = [cid for cid in inline if cid not in trace["citations"]]

                if (
                    extra != r.get("unlisted_inline_citations", [])
                    or len(extra) != len(r.get("unlisted_inline_support", []))
                ):
                    raise SystemExit("Unreviewed inline citations: " + str(path))

                t["citations"] += extra
                support = r["citation_support"] + r.get("unlisted_inline_support", [])

                if (
                    len(support) != len(t["citations"])
                    or any(type(v) is not bool for v in support)
                ):
                    raise SystemExit("Incomplete citation support: " + str(path))

                r["citation_support"] = [
                    v and cid in trace["context_ids"] and cid in inline
                    for cid, v in zip(t["citations"], support)
                ]

                if case["answerable"] and trace["status"] != "error":
                    grade = r["context_grade"]
                    if type(grade) is not int or grade not in (0, 1, 2):
                        raise SystemExit("Incomplete context grade: " + str(path))
                    context_grades.append(grade)

                if type(r.get("language_ok")) is not bool:
                    raise SystemExit("Missing language label: " + str(path))

                language_errors += not r["language_ok"]
                format_errors += set(inline) != set(trace["citations"])
                adjusted_rows.append(t)
                adjusted_reviews.append(r)

            metrics = aggregate(cases, adjusted_rows, adjusted_reviews)
            metrics["context_grades"] = dict(Counter(str(g) for g in context_grades))
            metrics["context_evidence"] = {
                "n": context_grades.count(2), "N": len(context_grades)
            }
            metrics["language_errors"] = language_errors
            metrics["citation_format_errors"] = format_errors
            metrics["review_statuses"] = dict(
                Counter(r["review_status"] for r in reviews)
            )

            successes = [r for r in rows if r["status"] != "error"]
            failed = [
                r for r in lines(directory / "failed_attempts.jsonl")
                if r.get("profile_id") == profile
            ]
            metrics["failed_attempts"] = len(failed)
            metrics["median_ms"] = (
                statistics.median(r["elapsed_ms"] for r in successes)
                if successes else None
            )
            metrics["model_call_distribution"] = dict(
                Counter(str(r["model_calls"]) for r in rows)
            )
            metrics["search_call_distribution"] = dict(
                Counter(str(r["search_calls"]) for r in rows)
            )

            card = {
                "run": run, "split": split, "profile": profile,
                "metrics": metrics, "usage": usage(successes + failed),
            }
            cards.append(card)
            print(json.dumps(card, ensure_ascii=False))

    raw_usage = {}
    dev = lines(ROOT / "results/retrieval_dev/traces.jsonl")
    test_dir = ROOT / "results/agent_test_final"

    for method in ("dense", "bm25", "hybrid"):
        raw_usage["dev_" + method] = usage([
            r for r in dev if r.get("method") == method
        ])
        rows = [
            read(p)
            for p in (test_dir / "raw_retrieval" / method).glob("*.json")
        ]
        failed = [
            r for r in lines(test_dir / "failed_attempts.jsonl")
            if r.get("method") == method
        ]
        raw_usage["test_" + method] = usage(
            [r for r in rows if r["status"] != "error"] + failed
        )

    result = {
        "profiles": cards,
        "original_query_usage": raw_usage,
        "raw_retrieval_dev": read(
            ROOT / "results/retrieval_dev/summary.json"
        )["methods"],
        "raw_retrieval_test": read(
            test_dir / "automatic_summary.json"
        )["raw_retrieval"],
        "notes": [
            "AI-proposed review is not independent human confirmation.",
            "Citations include undeclared inline IDs; original traces/reviews remain unchanged.",
            "Usage covers returned trace data and saved failures; excludes smoke checks and Day 6 indexing.",
            "SDK call counts exclude hidden HTTP retries. Provider cost units are unverified, not USD.",
        ],
    }

    path = ROOT / "results/submission_summary.json"
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(path)

    print("ORIGINAL QUERY USAGE:", json.dumps(raw_usage))
    print("RAW RETRIEVAL TEST:", json.dumps(result["raw_retrieval_test"]))
    print("Saved:", path)

if __name__ == "__main__":
    main()
