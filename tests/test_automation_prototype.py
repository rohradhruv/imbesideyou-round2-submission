"""Regression tests for deterministic onboarding-review decisions."""

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from automation_prototype import MOCK_CASES, evaluate_case, evaluate_item


class OnboardingRuleTests(unittest.TestCase):
    def test_complete_case_is_ready_for_human_completion(self):
        _, decision, _ = evaluate_case(MOCK_CASES["ONB-1001"])
        self.assertEqual(decision, "READY FOR HUMAN COMPLETION")

    def test_missing_required_evidence_requires_human_review(self):
        results, decision, _ = evaluate_case(MOCK_CASES["ONB-1002"])
        statuses = {item.code: status for item, status, _ in results}
        self.assertEqual(decision, "HUMAN REVIEW REQUIRED")
        self.assertEqual(statuses["BANK"], "MISSING")
        self.assertEqual(statuses["EMPLOYMENT_INSURANCE"], "MISSING")

    def test_conflicting_evidence_requires_human_review(self):
        results, decision, _ = evaluate_case(MOCK_CASES["ONB-1003"])
        statuses = {item.code: status for item, status, _ in results}
        self.assertEqual(decision, "HUMAN REVIEW REQUIRED")
        self.assertEqual(statuses["EMPLOYMENT_INSURANCE"], "REQUIRES REVIEW")

    def test_non_required_item_is_not_an_exception(self):
        item = MOCK_CASES["ONB-1001"].items[-1]
        status, _ = evaluate_item(item)
        self.assertEqual(status, "NOT APPLICABLE")


if __name__ == "__main__":
    unittest.main()
