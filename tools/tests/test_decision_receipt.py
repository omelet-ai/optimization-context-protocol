"""Synthetic source/receipt tampering tests; these grant no authorization."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_d02 import MESSAGE_SHA256, SCOPE, verify

MESSAGE = "좋아. omelet-ai/oi-foundry의 main 기준으로 별도 worktree와 feat/ocp-consumer-integration 브랜치에서 추천한 최소 연동을 진행해줘. 하네스 검증 후 커밋·푸시·draft PR 생성까지 승인한다. 외부 trial 담당자·환경·예산은 별도로 정하자.\n"


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "synthetic.jsonl"
        self.entry = {"type": "response_item", "timestamp": "synthetic-test-only", "payload": {
            "role": "user", "content": [{"type": "input_text", "text": MESSAGE}]}}
        self.source.write_text(json.dumps(self.entry) + "\n")
        self.receipt = dict(deepcopy(SCOPE), source_file=str(self.source), line=1,
                            timestamp="synthetic-test-only", record=self.entry, message_sha256=MESSAGE_SHA256)

    def test_exact_receipt_parses_without_broadening(self):
        self.assertEqual(verify(self.receipt)["versions"]["branch"], SCOPE["branch"])

    def test_source_deletion_fails(self):
        self.source.unlink()
        with self.assertRaises(ValueError): verify(self.receipt)

    def test_scope_cannot_add_merge_or_deploy(self):
        self.receipt["actions"].append("merge")
        with self.assertRaises(ValueError): verify(self.receipt)

    def test_different_branch_fails(self):
        self.receipt["branch"] = "main"
        with self.assertRaises(ValueError): verify(self.receipt)

    def test_tool_or_assistant_quote_is_not_user_instruction(self):
        self.entry["payload"]["role"] = "assistant"
        self.source.write_text(json.dumps(self.entry) + "\n")
        with self.assertRaises(ValueError): verify(self.receipt)

    def test_changed_original_message_fails(self):
        self.entry["payload"]["content"][0]["text"] += "extra scope"
        self.source.write_text(json.dumps(self.entry) + "\n")
        with self.assertRaises(ValueError): verify(self.receipt)

    def test_changed_receipt_fails(self):
        self.receipt["record"] = deepcopy(self.entry)
        self.receipt["record"]["timestamp"] = "changed"
        with self.assertRaises(ValueError): verify(self.receipt)

    def test_missing_line_or_boolean_line_fails(self):
        for line in (2, True):
            self.receipt["line"] = line
            with self.assertRaises(ValueError): verify(self.receipt)


if __name__ == "__main__":
    result = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(ReceiptTests))
    ok = result.wasSuccessful() and result.testsRun == 8 and not result.skipped
    print(json.dumps({"status": "PASS" if ok else "FAIL", "tests_run": result.testsRun,
                      "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
                      "scope": "Synthetic decision-provenance regressions; not an actual authorization"}))
    sys.exit(0 if ok else 1)
