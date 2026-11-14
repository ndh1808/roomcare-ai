from scripts.evaluate_demo import ROOT, evaluate_cases, load_cases


def test_evaluation_fixture_has_all_categories_and_unique_cases():
    cases = load_cases(ROOT / "data" / "evaluation_cases.json")
    assert len(cases) == 48
    assert len({case["expected_category"] for case in cases}) == 6


def test_metrics_report_false_negatives_instead_of_hiding_them():
    cases = [
        {"id": "A", "description": "danger", "expected_category": "Điện", "expected_priority": "Khẩn cấp", "expected_emergency": True},
        {"id": "B", "description": "normal", "expected_category": "Nước", "expected_priority": "Trung bình", "expected_emergency": False},
    ]
    def incorrect(description, api_key):
        assert api_key == ""
        return {"category": "Nước", "priority": "Trung bình", "emergency": description == "normal"}
    result = evaluate_cases(cases, incorrect)
    assert result["category_accuracy"] == 0.5
    assert result["priority_accuracy"] == 0.5
    assert result["emergency_recall"] == 0.0
    assert result["emergency_confusion"]["false_negative"] == 1
    assert result["emergency_confusion"]["false_positive"] == 1
    assert len(result["mismatches"]) == 2


def test_empty_dataset_does_not_invent_perfect_accuracy():
    result = evaluate_cases([])
    assert result["category_accuracy"] is None
    assert result["emergency_recall"] is None
