import argparse
import hashlib
import json
import re

from starter.baseline import hit
from .day6_bridge import Day6Retriever, ROOT
from .prepare_benchmark import digest


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def context_match(row, case, chunks):
    return any(
        chunk_id in chunks
        and hit(chunks[chunk_id], case.get("gold", []))
        for chunk_id in row["context_ids"]
    )


def flags(row, case, chunks):
    result = []

    if row["status"] == "error":
        result.append("SYSTEM_ERROR")
    if case["answerable"] and row["status"] == "abstain":
        result.append("ANSWERABLE_BUT_ABSTAINED")
    if case["answerable"] and not context_match(row, case, chunks):
        result.append("NO_EXACT_GOLD_IN_CONTEXT")
    if not case["answerable"] and row["status"] == "answered":
        result.append("UNANSWERABLE_BUT_ANSWERED")

    repairs = sum(
        event["event"] in ("invalid_final", "invalid_search")
        for event in row["events"]
    )
    if repairs:
        result.append(f"FORMAT_REPAIRS={repairs}")

    return result


def print_case(case, profiles, records, chunks):
    print("\n" + "=" * 60)
    print(
        "QUERY:", case["id"],
        "| ANSWERABLE:", case["answerable"],
    )
    print("QUESTION:", case["question"])
    print(
        "EXPECTED:",
        case.get("expected_answer", "Search and abstain."),
    )

    for gold in case.get("gold", []):
        print(
            "GOLD:", gold["source_id"],
            "page", gold["page"],
            "|", gold["evidence"],
        )

    if not case["answerable"]:
        print(
            "ABSENCE RATIONALE (needs review):",
            case["absence_reason"],
        )

    selected = []
    for profile in profiles:
        row = records[(profile, case["id"])]
        wanted = list(row["citations"])
        wanted += [
            chunk_id for chunk_id in row["context_ids"]
            if chunk_id in chunks
            and hit(chunks[chunk_id], case.get("gold", []))
        ]
        if (
            row["status"] != "answered"
            or not context_match(row, case, chunks)
        ):
            wanted += row["context_ids"]

        for chunk_id in wanted:
            if chunk_id not in selected:
                selected.append(chunk_id)

    aliases = {
        chunk_id: f"C{i}"
        for i, chunk_id in enumerate(selected, 1)
    }

    for profile in profiles:
        row = records[(profile, case["id"])]
        answer = row["answer"]
        print("RAW INLINE CITATIONS", profile, ":", re.findall(r"\[([^\[\]]+)\]", answer))

        for chunk_id, alias in aliases.items():
            answer = answer.replace(
                f"[{chunk_id}]", f"[{alias}]"
            )

        print(
            "\nPROFILE:", profile,
            "| STATUS:", row["status"],
        )
        print("ANSWER:", answer)
        print(
            "CITATIONS:",
            [
                aliases.get(chunk_id, chunk_id)
                for chunk_id in row["citations"]
            ],
        )
        print(
            "CITATION IDS IN CONTEXT:",
            all(
                chunk_id in row["context_ids"]
                for chunk_id in row["citations"]
            ) if row["citations"] else "N/A",
        )
        print(
            "CONTEXT EXACT MATCH:",
            context_match(row, case, chunks)
            if case["answerable"] else "N/A",
        )
        print("FLAGS:", flags(row, case, chunks))

        repairs = [
            event for event in row["events"]
            if event["event"] in (
                "invalid_final", "invalid_search"
            )
        ]
        if repairs:
            print("REPAIR EVENTS:", repairs)

        print(
            "SEARCH QUERIES:",
            [
                event["query"]
                for event in row["events"]
                if event["event"] == "search"
            ],
        )

    print(
        "\nEVIDENCE CHUNKS "
        "(C1/C2 are display aliases only):"
    )
    for chunk_id, alias in aliases.items():
        chunk = chunks.get(chunk_id)
        print(f"\n[{alias}] ID={chunk_id}")

        if chunk is None:
            print("CHUNK NOT FOUND IN FROZEN CORPUS")
            continue

        print(
            "SOURCE:", chunk["source_id"],
            "| PAGE:", chunk["page"],
            "| URL:", chunk["source"],
        )
        print(chunk["text"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-name", default="agent_test_final")
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--query-id")
    parser.add_argument(
        "--diagnostics-only", action="store_true"
    )
    args = parser.parse_args()

    if args.start < 1 or args.count < 1:
        raise SystemExit("start/count must be positive.")

    directory = ROOT / "results" / args.run_name
    cases = read(ROOT / "benchmark/test.json")
    manifest = read(ROOT / "benchmark/manifest.json")

    if digest(cases) != manifest["test_sha256"]:
        raise SystemExit("Test benchmark changed.")

    plan = read(directory / "plan.json")
    profiles = list(plan["profiles"])
    rows = Day6Retriever().load_chunks()

    fingerprint = [
        {
            key: chunk[key]
            for key in ("id", "source_id", "source", "page", "text")
        }
        for chunk in sorted(rows, key=lambda chunk: chunk["id"])
    ]
    if digest(fingerprint) != manifest["corpus_sha256"]:
        raise SystemExit(
            "Corpus changed; cannot review against a different index."
        )

    chunks = {chunk["id"]: chunk for chunk in rows}
    records, templates = {}, []

    for profile in profiles:
        for case in cases:
            path = (
                directory / profile
                / (case["id"] + ".json")
            )
            row = read(path)

            if (
                row["query_id"] != case["id"]
                or row["profile_id"] != profile
            ):
                raise SystemExit(
                    "Trace identity mismatch: " + str(path)
                )

            records[(profile, case["id"])] = row
            templates.append({
                "profile_id": profile,
                "query_id": case["id"],
                "trace_sha256": hashlib.sha256(
                    path.read_bytes()
                ).hexdigest(),
                "answer_grade": None,
                "context_grade": None,
                "citation_support": [
                    None for _ in row["citations"]
                ],
                "abstention_correct": None,
                "reason": "",
                "review_status": "pending",
            })

    review_path = directory / "reviews.json"

    if review_path.exists():
        existing = {
            (row["profile_id"], row["query_id"]): row
            for row in read(review_path)
        }
        if (
            len(existing) != len(templates)
            or any(
                existing.get(
                    (row["profile_id"], row["query_id"]), {}
                ).get("trace_sha256") != row["trace_sha256"]
                for row in templates
            )
        ):
            raise SystemExit(
                "Review/trace mismatch. "
                "Existing reviews were not modified."
            )
    else:
        review_path.write_text(
            json.dumps(
                templates, ensure_ascii=False, indent=2
            ),
            encoding="utf-8",
        )

    print(
        "REVIEWS:", len(templates),
        "rows; grades remain pending until reviewed.",
    )
    print(
        "DIAGNOSTICS "
        "(exact-quote misses are not automatic semantic grades):"
    )

    for case in cases:
        for profile in profiles:
            row = records[(profile, case["id"])]
            issues = flags(row, case, chunks)
            if issues:
                print(
                    profile, case["id"],
                    "|", ", ".join(issues),
                )

    if args.diagnostics_only:
        return

    selected = (
        [
            case for case in cases
            if case["id"] == args.query_id
        ]
        if args.query_id
        else cases[
            args.start - 1:args.start - 1 + args.count
        ]
    )

    if not selected:
        raise SystemExit("No matching test cases.")

    for case in selected:
        print_case(case, profiles, records, chunks)


if __name__ == "__main__":
    main()
