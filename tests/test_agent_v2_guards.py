import unittest
from src.agent_v2 import validate_final

class AgentV2GuardTests(unittest.TestCase):
    def test_supported_citation_format_passes(self):
        self.assertIsNone(validate_final({"status": "answered", "answer": "Seven days [c1]", "citations": ["c1"]}, ["c1"], 1))

    def test_plain_abstention_passes(self):
        self.assertIsNone(validate_final({"status": "abstain", "answer": "The corpus has insufficient evidence.", "citations": []}, [], 1))

    def test_chinese_prose_requires_repair(self):
        self.assertIsNotNone(validate_final({"status": "answered", "answer": "\u7b54\u6848 [c1]", "citations": ["c1"]}, ["c1"], 1))

    def test_inline_citation_in_abstention_requires_repair(self):
        self.assertIsNotNone(validate_final({"status": "abstain", "answer": "Insufficient evidence [c1]", "citations": []}, ["c1"], 1))

    def test_unseen_citation_requires_repair(self):
        self.assertIsNotNone(validate_final({"status": "answered", "answer": "Seven days [fake]", "citations": ["fake"]}, ["c1"], 1))

    def test_final_without_search_is_rejected(self):
        self.assertIsNotNone(validate_final({"status": "abstain", "answer": "Insufficient evidence.", "citations": []}, [], 0))

if __name__ == "__main__":
    unittest.main()
