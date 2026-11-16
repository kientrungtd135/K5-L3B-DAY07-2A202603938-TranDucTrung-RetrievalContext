import argparse
import hashlib
import json
import statistics
from datetime import datetime, timezone

from dotenv import dotenv_values
from starter.baseline import hit
from .agent import RAGAgent as BaselineAgent
from .agent_v2 import RAGAgent as SelectedAgent
from .day6_bridge import Day6Retriever, ROOT
from .evaluate_agent import summarize
from .evaluate_retrieval import measure
from .prepare_benchmark import digest
from .retrieval import UnifiedRetriever


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def check_dev(run, profile, cases):
    directory = ROOT / "results" / run
    plan = read(directory / "plan.json")

    for name, expected in plan["code_hashes"].items():
        if sha(ROOT / name) != expected:
            raise SystemExit(
                "Dev code changed since measurement: " + name
            )

    reviews = {
        (row["profile_id"], row["query_id"]): row
        for row in read(directory / "reviews.json")
    }
    rows, labels = [], []

    for case in cases:
        path = directory / profile / (case["id"] + ".json")
        row = read(path)
        label = reviews.get((profile, case["id"]))

        if (
            not label
            or label["review_status"] not in (
                "ai_proposed", "human_confirmed"
            )
            or sha(path) != label["trace_sha256"]
        ):
            raise SystemExit(
                "Missing/stale dev review: "
                + profile + " " + case["id"]
            )

        if case["answerable"]:
            if (
                label["answer_grade"] not in (0, 1, 2)
                or label["context_grade"] not in (0, 1, 2)
            ):
                raise SystemExit("Incomplete dev grades.")
        elif type(label["abstention_correct"]) is not bool:
            raise SystemExit("Incomplete abstention review.")

        if (
            len(label["citation_support"]) != len(row["citations"])
            or any(
                type(value) is not bool
                for value in label["citation_support"]
            )
        ):
            raise SystemExit("Incomplete citation review.")

        rows.append(row)
        labels.append(label)

    return plan, rows, labels


def save_result(path, result, directory):
    write(path, result)

    if result["status"] == "error":
        with (
            directory / "failed_attempts.jsonl"
        ).open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps(result, ensure_ascii=False) + "\n"
            )

        error = next(
            (
                event
                for event in reversed(result.get("events", []))
                if event["event"] == "error"
            ),
            {},
        )
        code = (
            result.get("http_status")
            or error.get("http_status")
        )
        print(
            "ERROR:",
            result.get("termination_reason")
            or result.get("error_type"),
            code,
            flush=True,
        )
        if code in (401, 403, 429):
            raise SystemExit(
                "Stopped on access/rate-limit error. "
                "Fix access, then use --resume with the same pipeline."
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    manifest = read(ROOT / "benchmark/manifest.json")
    dev = read(ROOT / "benchmark/dev.json")
    if digest(dev) != manifest["dev_sha256"]:
        raise SystemExit("Dev benchmark changed.")

    baseline_plan, _, baseline_labels = check_dev(
        "agent_dev_v1", "dense_baseline", dev
    )
    selected_plan, selected_rows, selected_labels = check_dev(
        "agent_dev_v2", "auto_english_v2", dev
    )

    for case, row, label in zip(
        dev, selected_rows, selected_labels
    ):
        if (
            row["status"] == "error"
            or label.get("language_ok") is not True
            or label.get("citation_format_ok") is not True
            or (
                case["answerable"]
                and (
                    label["answer_grade"] != 2
                    or label["context_grade"] != 2
                )
            )
            or (
                not case["answerable"]
                and label["abstention_correct"] is not True
            )
            or not all(label["citation_support"])
        ):
            raise SystemExit(
                "Selected dev profile needs review: " + case["id"]
            )

    config = dotenv_values(
        ROOT / ".env", encoding="utf-8-sig"
    )
    model = config.get("AGENT_MODEL")
    if (
        not model
        or model != baseline_plan["model"]
        or model != selected_plan["model"]
    ):
        raise SystemExit("Model differs from dev runs.")

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
            "Corpus differs from the dev benchmark."
        )

    profiles = {
        "dense_baseline": {
            "module": "src.agent",
            "params": baseline_plan["profiles"][
                "dense_baseline"
            ]["params"],
        },
        "auto_english_v2": {
            "module": "src.agent_v2",
            "params": selected_plan["profiles"][
                "auto_english_v2"
            ]["params"],
        },
    }
    files = (
        "src/agent.py",
        "src/agent_v2.py",
        "src/retrieval.py",
        "src/day6_bridge.py",
        "src/evaluate_agent.py",
        "src/evaluate_agent_v2.py",
        "src/evaluate_retrieval.py",
        "src/prepare_benchmark.py",
        "src/final_test.py",
        "starter/baseline.py",
    )

    decision = {
        "model": model,
        "endpoint": (
            config.get("AGENT_BASE_URL")
            or config.get("OPENAI_BASE_URL")
        ),
        "profiles": profiles,
        "raw_retrieval_methods": ["dense", "bm25", "hybrid"],
        "dev_sha256": manifest["dev_sha256"],
        "test_sha256": manifest["test_sha256"],
        "corpus_sha256": manifest["corpus_sha256"],
        "code_hashes": {
            name: sha(ROOT / name) for name in files
        },
        "dev_review_hashes": {
            run: sha(
                ROOT / "results" / run / "reviews.json"
            )
            for run in ("agent_dev_v1", "agent_dev_v2")
        },
        "original_selection_rule": manifest["selection_rule"],
        "dev_policy_refinement": (
            "Before test, strict English and inline/list citation "
            "consistency were made functional eligibility requirements "
            "after observed v1 failures. V2 retains dev content quality "
            "with higher latency; v1 is preserved as baseline."
        ),
        "review_provenance": (
            "AI-proposed source inspection; "
            "human confirmation is not implied."
        ),
        "selected_dev_points": sum(
            row["answer_grade"]
            for row in selected_labels
            if row["answer_grade"] is not None
        ),
        "baseline_dev_points": sum(
            row["answer_grade"]
            for row in baseline_labels
            if row["answer_grade"] is not None
        ),
        "test_policy": (
            "Freeze before reading test questions; no parameter or prompt "
            "tuning on test. Resume retries system errors only "
            "and preserves failed attempts."
        ),
    }

    frozen_path = ROOT / "configs/final_selection.json"
    if frozen_path.exists():
        frozen = read(frozen_path)
        previous = {
            key: value for key, value in frozen.items()
            if key != "frozen_at_utc"
        }
        if previous != decision:
            raise SystemExit(
                "Frozen selection differs. "
                "Do not overwrite or tune using test."
            )
    else:
        frozen = {
            "frozen_at_utc": datetime.now(
                timezone.utc
            ).isoformat(),
            **decision,
        }
        write(frozen_path, frozen)

    print("FROZEN:", frozen_path, flush=True)

    cases = read(ROOT / "benchmark/test.json")
    if (
        digest(cases) != frozen["test_sha256"]
        or len(cases) != 7
        or sum(case["answerable"] for case in cases) != 5
        or any(case["split"] != "test" for case in cases)
    ):
        raise SystemExit(
            "Test benchmark does not match the frozen manifest."
        )

    answerable = [
        case for case in cases if case["answerable"]
    ]
    if any(
        not any(hit(chunk, case["gold"]) for chunk in chunks)
        for case in answerable
    ):
        raise SystemExit(
            "A test gold quote does not resolve in the frozen corpus."
        )

    directory = ROOT / "results/agent_test_final"
    plan_path = directory / "plan.json"
    if plan_path.exists():
        if not args.resume:
            raise SystemExit(
                "Test run exists. Only --resume "
                "of system errors is supported."
            )
        if read(plan_path) != frozen:
            raise SystemExit("Test plan mismatch.")
    else:
        if directory.exists() and any(directory.iterdir()):
            raise SystemExit(
                "Test output directory is not empty."
            )
        write(plan_path, frozen)

    raw_summary = {}
    for method in ("dense", "bm25", "hybrid"):
        retriever = UnifiedRetriever(
            method, backend=backend
        )
        rows = []

        for case in answerable:
            path = (
                directory / "raw_retrieval" / method
                / (case["id"] + ".json")
            )
            if path.exists() and read(path)["status"] == "ok":
                row = read(path)
            else:
                print(
                    "RAW TEST:", method, case["id"],
                    flush=True,
                )
                row = measure(retriever, case, 4000)
                row["split"] = "test"
                save_result(path, row, directory)
            rows.append(row)

        successful = [
            row for row in rows if row["status"] == "ok"
        ]
        raw_summary[method] = {
            "N": len(rows),
            "hit1": sum(
                row.get("hit1", False) for row in rows
            ),
            "hit3": sum(
                row.get("hit3", False) for row in rows
            ),
            "context_match": sum(
                row.get("context_match", False) for row in rows
            ),
            "errors": len(rows) - len(successful),
            "median_ms": (
                statistics.median(
                    row["elapsed_ms"] for row in successful
                )
                if successful else None
            ),
        }

    classes = {
        "dense_baseline": BaselineAgent,
        "auto_english_v2": SelectedAgent,
    }
    summaries, position = {}, 0
    chunk_map = {
        chunk["id"]: chunk for chunk in chunks
    }

    for profile, settings in profiles.items():
        agent = classes[profile](
            **settings["params"],
            model=model,
            verbose=True,
        )
        rows = []

        try:
            for case in cases:
                position += 1
                path = (
                    directory / profile
                    / (case["id"] + ".json")
                )

                if (
                    path.exists()
                    and read(path)["status"] in (
                        "answered", "abstain"
                    )
                ):
                    row = read(path)
                    print(
                        f"[{position}/14] {profile} "
                        f"{case['id']} saved success",
                        flush=True,
                    )
                else:
                    print(
                        f"\n[{position}/14] {profile} "
                        f"{case['id']} running...",
                        flush=True,
                    )
                    row = agent.run(
                        case["question"], case.get("filter")
                    )
                    row.update(
                        query_id=case["id"],
                        split="test",
                        profile_id=profile,
                    )
                    save_result(path, row, directory)
                    print(
                        "STATUS:", row["status"],
                        flush=True,
                    )
                rows.append(row)
        finally:
            agent.client.close()

        summaries[profile] = summarize(
            cases, rows, chunk_map
        )

    summary = {
        "split": "test",
        "profiles": summaries,
        "raw_retrieval": raw_summary,
        "review_status": "pending",
        "cost_usd": None,
        "notes": [
            "No test-based tuning; frozen pipeline.",
            "Original-query rankings and model-rewritten first-search rankings are separate.",
            "Answer correctness and citation support require source review.",
        ],
    }
    write(directory / "automatic_summary.json", summary)

    print(
        "\nORIGINAL QUERY | HIT@1 | HIT@3 | "
        "CONTEXT MATCH | ERRORS"
    )
    for method, row in raw_summary.items():
        print(
            f"{method} | {row['hit1']}/{row['N']} | "
            f"{row['hit3']}/{row['N']} | "
            f"{row['context_match']}/{row['N']} | "
            f"{row['errors']}"
        )

    print(
        "\nPROFILE | ANSWERED | ABSTAIN | ERRORS | "
        "FIRST HIT@3 | CONTEXT MATCH | MEDIAN MS"
    )
    for profile, row in summaries.items():
        h = row["first_search_hit3"]
        c = row["context_match"]
        median = (
            f"{row['median_ms']:.2f}"
            if row["median_ms"] is not None else "N/A"
        )
        print(
            f"{profile} | {row['answered']} | "
            f"{row['abstain']} | {row['errors']} | "
            f"{h['n']}/{h['N']} | "
            f"{c['n']}/{c['N']} | {median}"
        )

    print(
        "Saved:",
        directory / "automatic_summary.json",
    )


if __name__ == "__main__":
    main()
