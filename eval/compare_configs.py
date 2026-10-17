"""
Runs eval/dataset.py against the live engine and reports false-negative
rate PER CATEGORY (structured/ner/near_miss/clean), not aggregate
accuracy — an aggregate number can hide "100% on SSNs, 40% on names" the
same way it nearly hid injection-guard's 22M model's non-English-specific
weakness. "multilingual" is reported separately and explicitly: it's a
known, stated-in-README gap, not a regression to chase to zero in v1.

Usage: uv run python eval/compare_configs.py
"""

import time

from pii_guard import engine


def main():
    engine.load_engines()

    from dataset import CASES

    by_category = {}
    for case in CASES:
        by_category.setdefault(case["category"], []).append(case)

    for category in ["structured", "ner", "near_miss", "clean", "multilingual"]:
        cases = by_category.get(category, [])
        if not cases:
            continue

        print(f"\n=== {category} ===")
        false_negatives = []
        false_positives = []
        latencies = []

        for case in cases:
            start = time.perf_counter()
            result = engine.analyze_and_redact(case["text"])
            latencies.append((time.perf_counter() - start) * 1000)

            found_types = {e["entity_type"] for e in result["entities"]}
            missing = case["expected"] - found_types
            unexpected = found_types - case["expected"]

            status = "OK"
            if missing:
                status = "FN"
                false_negatives.append((case["text"], missing))
            elif unexpected and not case["expected"]:
                # only flag as a false positive when we expected NOTHING
                # and got something — partial over-detection on a real
                # PII case is a different, less severe issue
                status = "FP"
                false_positives.append((case["text"], unexpected))

            expected_str = str(case["expected"]) if case["expected"] else "{}"
            found_str = str(found_types) if found_types else "{}"
            print(f"  [{status}] expected={expected_str:30} found={found_str}  {case['text'][:50]!r}")

        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        print(f"  {category}: {len(cases)} cases, FN={len(false_negatives)}, FP={len(false_positives)}, avg_latency={avg_latency:.1f}ms")
        if category == "multilingual" and false_negatives:
            print("  (expected — en_core_web_lg is English-only, see README \"Language scope\")")


if __name__ == "__main__":
    main()
