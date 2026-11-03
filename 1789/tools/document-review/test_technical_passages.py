"""Technical slicing only: exact characters, bounded sizes, overlap, no historical claims."""

import json
import sys
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "extraction"))
from reviewlib import module, sha  # noqa: E402
from technical_passages import split  # noqa: E402

LocalTokenizer = module(
    "test_technical_local_tokenizer", BASE.parent / "rag/src/cahier_rag/context/tokenization.py"
).LocalTokenizer


class TechnicalPassageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((BASE / "extraction/technical-passages-config.json").read_text())
        path = BASE.parent / cls.config["tokenizer_path"]
        cls.counter = LocalTokenizer(
            path,
            repository="BAAI/bge-m3",
            revision=cls.config["tokenizer_revision"],
            expected_sha256=sha(path.read_bytes()),
        )

    def check_text(self, text, ends):
        frames = split(text, ends, self.counter, self.config)
        self.assertEqual(frames, split(text, ends, self.counter, self.config))
        previous_end = 0
        for i, f in enumerate(frames):
            self.assertTrue(text[f["start"] : f["end"]].strip())
            self.assertEqual(self.counter.count(text[f["start"] : f["end"]]), f["tokens"])
            self.assertLessEqual(f["tokens"], 800)
            self.assertLessEqual(f["start"], previous_end)
            self.assertGreater(f["end"], previous_end)
            if i:
                self.assertLessEqual(self.counter.count(text[f["start"] : previous_end]), 80)
            previous_end = f["end"]
        self.assertEqual(frames[0]["start"], 0)
        self.assertEqual(frames[-1]["end"], len(text))
        return frames

    def test_paragraphs_and_unicode_are_preserved_without_title_prefix(self):
        ps = [
            "\tQue les habitants puissent se réunir librement. " * 55,
            "\n2° Sans moderniser l’imposition, conserver l’égalité. " * 40,
            "\nSigné : Martin.\n\t ",
        ]
        ends = []
        text = ""
        for p in ps:
            text += p
            ends.append(len(text))
        frames = self.check_text(text, ends)
        self.assertTrue(any(f["end_reason"] == "XML_paragraph_end" for f in frames))

    def test_long_paragraph_uses_sentences(self):
        text = "Que les droits soient répartis équitablement, sans privilège. " * 250
        frames = self.check_text(text, [len(text)])
        self.assertGreater(len(frames), 2)
        self.assertTrue(any(f["end_reason"] == "sentence_end" for f in frames))

    def test_long_sentence_uses_word_boundaries(self):
        text = "\n" + "imposition extraordinaire " * 1500
        frames = self.check_text(text, [len(text)])
        self.assertTrue(any(f["end_reason"] == "word_boundary_long_sentence" for f in frames))

    def test_short_text_and_punctuation_are_not_discarded(self):
        for text in [";", "\n1\t", "é", " ? ", "Art. 1. Oui. Art. 2. Non."]:
            self.assertEqual(len(self.check_text(text, [len(text)])), 1)

    def test_whitespace_only_has_no_search_passage(self):
        for text in ["", "\t \n\r   "]:
            self.assertEqual(split(text, [len(text)], self.counter, self.config), [])

    def test_historical_numbers_are_not_mandatory_boundaries(self):
        text = "Art. 1. Que la justice soit gratuite.\nArt. 2. Que le sel soit libre."
        self.assertEqual(len(self.check_text(text, [len(text)])), 1)


if __name__ == "__main__":
    unittest.main()
