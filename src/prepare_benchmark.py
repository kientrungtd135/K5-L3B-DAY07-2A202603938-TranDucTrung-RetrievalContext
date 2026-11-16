import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .day6_bridge import Day6Retriever, ROOT


def digest(value):
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_cases(old_questions, chunks):
    dev = []
    for question in old_questions:
        if question["split"] != "dev":
            continue

        dev.append({
            "id": "d7-dev-" + question["id"],
            "split": "dev",
            "question": question["question"],
            "answerable": True,
            "expected_answer": question["expected_answer"],
            "expected_behavior": "search_and_answer",
            "gold": [{
                "source_id": question["gold_source_id"],
                "page": question["gold_page"],
                "evidence": question["evidence_quote"],
            }],
            "filter": question.get("filter", {}),
            "provenance": "Reused Day 6 dev question.",
        })

    if len(dev) != 15:
        raise ValueError("Expected exactly 15 Day 6 dev questions.")

    specifications = [
        (
            "doc_0033",
            "According to the Google Search article, approximately how many zettabytes of data were people creating every year in 2013?",
            "Around 9 zettabytes (9 ZB) per year.",
            "In 2013, people were creating around 9 ZB of data every year",
        ),
        (
            "doc_0034",
            "According to the Helena World Chronicle lawsuit article, how many facts and entities did Google's Knowledge Graph contain by 2020?",
            "500 billion facts about 5 billion entities.",
            "By 2020, the Knowledge Graph had grown to 500 billion facts about 5 billion entities.",
        ),
        (
            "doc_0043",
            "According to the Epic Games trial preview, what commission range did Google charge app developers on sales processed through its first-party billing system?",
            "15% to 30%.",
            "charges app developers a 15% to 30% commission on the sales it processes.",
        ),
        (
            "doc_0090",
            "In the Manchester United article, what planned infrastructure investment amount is mentioned in US dollars and pounds?",
            "US$300 million, equivalent to 237 million pounds.",
            "invest $300m (\u00a3237m) into infrastructure",
        ),
        (
            "doc_0098",
            "According to the Menendez article, what was the reported dollar value of gold bars found in the raid on his house?",
            "$100,000.",
            "A raid of Menendez\u2019s house turned up $100,000 in gold bars and bundles of cash stuffed into jacket pockets.",
        ),
    ]

    old_sources = {q["gold_source_id"] for q in old_questions}
    test = []

    for number, specification in enumerate(specifications, 1):
        source_id, question, answer, evidence = specification

        if source_id in old_sources:
            raise ValueError(
                "New test source overlaps a Day 6 question source."
            )

        test.append({
            "id": f"d7-test-{number:02d}",
            "split": "test",
            "question": question,
            "answerable": True,
            "expected_answer": answer,
            "expected_behavior": "search_and_answer",
            "gold": [{
                "source_id": source_id,
                "page": 1,
                "evidence": evidence,
            }],
            "filter": {},
            "provenance": "New Day 7 test question.",
        })

    absent = [
        (
            "dev",
            "What exact percentage of Fred Ruckel's Ripple Rug sales came from Amazon in calendar year 2022?",
            "doc_0003",
            ["Ruckel", "Ripple Rug", "2022", "90%"],
            "The article gives Ruckel's prices and losses, but no 2022 sales percentage. The 90% figure concerns Molson Hart, a different seller.",
        ),
        (
            "dev",
            "What was Betashares' net profit after tax for the financial year ended 30 June 2023?",
            "doc_0002",
            ["Betashares", "net profit", "profit after tax"],
            "Betashares is mentioned for an acquisition and funds under management, not its annual net profit.",
        ),
        (
            "test",
            "What exact monthly subscription price in US dollars did Mozilla announce for Mozilla.social?",
            "doc_0027",
            ["Mozilla.social", "subscription", "monthly", "price"],
            "The article describes a private beta and moderation plans but gives no monthly subscription price. Absence of a price does not imply a zero-dollar price.",
        ),
        (
            "test",
            "What exact dollar amount in damages did the court ultimately award Helena World Chronicle in its lawsuit against Google?",
            "doc_0034",
            ["Helena", "damages", "award", "judgment"],
            "The snapshot describes a newly filed lawsuit and requested relief, not a damages award. Google's Canadian media agreement is a different matter.",
        ),
    ]

    counters = {"dev": 0, "test": 0}
    audit = []

    for split, question, source_id, terms, reason in absent:
        counters[split] += 1
        case_id = f"d7-{split}-u{counters[split]:02d}"

        case = {
            "id": case_id,
            "split": split,
            "question": question,
            "answerable": False,
            "expected_behavior": "search_and_abstain",
            "absence_reason": reason,
            "gold": [],
            "filter": {},
        }

        (dev if split == "dev" else test).append(case)

        audit.append({
            "query_id": case_id,
            "split": split,
            "related_source_id": source_id,
            "search_terms": terms,
            "reason": reason,
            "review_status": "ai_proposed_needs_human_review",
            "review_method": (
                "Inspect the relevant original article and search all "
                "30 articles; top-k failure alone is insufficient."
            ),
        })

    for case in dev + test:
        for gold in case["gold"]:
            matches = [
                chunk for chunk in chunks
                if chunk["source_id"] == gold["source_id"]
                and chunk["page"] == gold["page"]
                and gold["evidence"] in chunk["text"]
            ]

            if not matches:
                raise ValueError(
                    "Evidence not contained in index B: " + case["id"]
                )

            gold["source"] = matches[0]["source"]

    if len({q["id"] for q in dev + test}) != 24:
        raise ValueError("Expected 24 unique cases.")

    return dev, test, audit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--day6-root", type=Path, required=True)
    args = parser.parse_args()

    directory = ROOT / "benchmark"
    names = (
        "dev.json",
        "test.json",
        "absence_audit.json",
        "manifest.json",
    )

    if any((directory / name).exists() for name in names):
        raise SystemExit(
            "Benchmark already exists; no files were overwritten."
        )

    old_path = args.day6_root / "benchmark" / "questions.json"
    old = json.loads(old_path.read_text(encoding="utf-8-sig"))
    old_questions = old["questions"] if isinstance(old, dict) else old

    chunks = Day6Retriever().load_chunks()
    documents = len({chunk["source_id"] for chunk in chunks})

    if len(chunks) != 701 or documents != 30:
        raise ValueError(
            "Unexpected corpus; expected B with 701 chunks and 30 documents."
        )

    dev, test, audit = build_cases(old_questions, chunks)

    fingerprint = [
        {
            key: chunk[key]
            for key in ("id", "source_id", "source", "page", "text")
        }
        for chunk in sorted(chunks, key=lambda chunk: chunk["id"])
    ]

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "strategy": "B",
        "chunks": 701,
        "documents": 30,
        "corpus_sha256": digest(fingerprint),
        "dev_sha256": digest(dev),
        "test_sha256": digest(test),
        "day6_questions_sha256": hashlib.sha256(
            old_path.read_bytes()
        ).hexdigest(),
        "counts": {
            "dev": {"answerable": 15, "unanswerable": 2},
            "test": {"answerable": 5, "unanswerable": 2},
        },
        "policy": (
            "Tune on dev only. Freeze pipeline before running test. "
            "Never send gold, expected answers or absence reasons to the agent."
        ),
        "selection_rule": (
            "DEV: highest mean grounded-answer grade, then context evidence "
            "rate, then citation validity, then lower median end-to-end "
            "latency. Report usage and cost separately."
        ),
        "page_note": (
            "page=1 is an independent article unit, not a PDF page."
        ),
        "absence_review": "AI-proposed; human review is pending.",
    }

    directory.mkdir(parents=True, exist_ok=True)

    for name, value in zip(names, (dev, test, audit, manifest)):
        (directory / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print("DEV: 15 answerable + 2 unanswerable = 17")
    print("TEST: 5 new answerable + 2 unanswerable = 7")
    print("TOTAL: 24 cases; all 20 answerable gold quotes resolve in index B.")
    print("Saved benchmark files. Absence labels still require human review.")


if __name__ == "__main__":
    main()
