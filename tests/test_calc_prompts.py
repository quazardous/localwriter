"""Tests for get_chat_system_prompt_for_document (Writer vs Calc prompt selection). No mocks; minimal real objects."""
import unittest
from core.constants import get_chat_system_prompt_for_document


def _writer_like_model():
    """Minimal object that looks like a Writer document (no getSheets)."""
    return type("WriterDoc", (), {})()


def _calc_like_model():
    """Minimal object that looks like a Calc document (has getSheets)."""
    return type("CalcDoc", (), {"getSheets": lambda self: None})()


class TestGetChatSystemPromptForDocument(unittest.TestCase):
    def test_calc_prompt_contains_calc_tools(self):
        model = _calc_like_model()
        prompt = get_chat_system_prompt_for_document(model, "")
        self.assertIn("read_cell_range", prompt)
        self.assertIn("write_formula", prompt)
        self.assertIn("FORMULA SYNTAX", prompt)
        self.assertIn("semicolon", prompt.lower())

    def test_writer_prompt_contains_writer_tools(self):
        model = _writer_like_model()
        prompt = get_chat_system_prompt_for_document(model, "")
        self.assertIn("get_document_content", prompt)
        self.assertIn("apply_document_content", prompt)

    def test_additional_instructions_appended(self):
        model = _calc_like_model()
        prompt = get_chat_system_prompt_for_document(model, "Be concise.")
        self.assertTrue(prompt.endswith("Be concise.") or "Be concise." in prompt)
        self.assertIn("read_cell_range", prompt)

    def test_additional_instructions_empty_unchanged(self):
        model = _calc_like_model()
        base = get_chat_system_prompt_for_document(model, "")
        with_extra = get_chat_system_prompt_for_document(model, "  \n  ")
        self.assertEqual(base, with_extra)


if __name__ == "__main__":
    unittest.main()
