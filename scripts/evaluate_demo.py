"""Evaluate only deterministic demo rules on a labelled synthetic dataset.

Run from the repository root: python scripts/evaluate_demo.py
Optional: --output work/demo-evaluation.json
This never reads an API key, calls Gemini, or measures vision performance.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from roomcare.ai import analyze_issue, CATEGORIES, PRIORITIES  # noqa: E402


def evaluate_cases(cases, analyzer=analyze_issue):
    """Return reproducible label metrics, including safety false negatives."""
    category_correct = priority_correct = tp = tn = fp = fn = 0
    mismatches = []
    matrix = {expected: {predicted: 0 for predicted in CATEGORIES} for expected in CATEGORIES}
    for case in cases:
        result = analyzer(case["description"], api_key="")
        expected = case["expected_category"]
        predicted = result["category"]
        matrix[expected][predicted] += 1
        category_correct += predicted == expected
        priority_correct += result["priority"] == case["expected_priority"]
        actual_emergency = case["expected_emergency"]
        predicted_emergency = result["emergency"]
        tp += actual_emergency and predicted_emergency
        tn += not actual_emergency and not predicted_emergency
        fp += not actual_emergency and predicted_emergency
        fn += actual_emergency and not predicted_emergency
        wrong_fields = [name for name in ("category", "priority", "emergency") if result[name] != case[f"expected_{name}"]]
        if wrong_fields:
            mismatches.append({
                "id": case["id"], "fields": wrong_fields,
                "expected": {name: case[f"expected_{name}"] for name in wrong_fields},
                "predicted": {name: result[name] for name in wrong_fields},
            })
    total = len(cases)
    return {
        "mode": "demo_rules_only",
        "cases": total,
        "category_accuracy": round(category_correct / total, 4) if total else None,
        "priority_accuracy": round(priority_correct / total, 4) if total else None,
        "emergency_precision": round(tp / (tp + fp), 4) if tp + fp else None,
        "emergency_recall": round(tp / (tp + fn), 4) if tp + fn else None,
        "emergency_confusion": {"true_positive": tp, "true_negative": tn, "false_positive": fp, "false_negative": fn},
        "category_confusion": matrix,
        "mismatches": mismatches,
        "limitations": "Dữ liệu giả lập đã dùng phát triển quy tắc, không phải holdout; nhãn chưa xác minh độc lập. Chỉ đánh giá demo; không đo Gemini, ảnh hay hiệu quả với người dùng thật. Đây không phải bảo đảm an toàn.",
    }


def load_cases(path):
    dataset = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = dataset["cases"]
    ids = set()
    for case in cases:
        if case["id"] in ids or case["expected_category"] not in CATEGORIES or case["expected_priority"] not in PRIORITIES or type(case["expected_emergency"]) is not bool:
            raise ValueError("Dataset contains duplicate ids or invalid labels")
        if not isinstance(case["description"], str) or not case["description"].strip():
            raise ValueError("Dataset contains an empty description")
        ids.add(case["id"])
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "data" / "evaluation_cases.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate_cases(load_cases(args.dataset))
    # ASCII escaping keeps the CLI usable under legacy Windows console encodings.
    text = json.dumps(result, ensure_ascii=True, indent=2)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
