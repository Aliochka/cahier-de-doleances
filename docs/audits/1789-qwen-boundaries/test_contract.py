"""Régressions réelles : identifiants Persée et titre du voisin ne sont pas des limites correctes."""

import copy
import json
import unittest

from evaluate import assess
from prompt import messages, parse
from qcommon import HERE, rows


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.windows = {w["id"]: w for w in rows(HERE / "data/windows.jsonl")}
        cls.refs = {r["window_id"]: r for r in rows(HERE / "data/reference-validation.jsonl")}
        cls.outputs = {
            (r["window_id"], r["method"]): r for r in rows(HERE / "data/validation-outputs.jsonl")
        }

    def test_B_C_only_proposal_differs(self):
        w = self.windows["validation-26"]
        b = json.loads(messages(w, "B")[1]["content"].split("\n", 1)[1])
        c = json.loads(messages(w, "C")[1]["content"].split("\n", 1)[1])
        c.pop("proposal_from_rules")
        self.assertEqual(b, c)

    def test_actual_Perse_e_identifier_hallucination_rejected(self):
        raw = next(
            r
            for r in rows(HERE / "data/pilot-v1-outputs.jsonl")
            if r["error"] and "unknown ancillary" in r["error"]
        )["raw"]
        with self.assertRaises(ValueError):
            parse(raw, self.windows["development-01"])

    def test_valid_known_ID_is_not_necessarily_correct_end(self):
        w = self.windows["validation-32"]
        r = self.outputs[(w["id"], "C")]
        self.assertIsNotNone(r["parsed"])
        a = assess(w, self.refs[w["id"]], "C", r)
        self.assertFalse(a["exact"])
        self.assertTrue(a["neighbour_title_absorbed"])

    def test_reversed_ids_and_pb_rejected(self):
        w = self.windows["validation-02"]
        r = copy.deepcopy(self.outputs[(w["id"], "B")]["parsed"])
        r["start_id"], r["end_id"] = r["end_id"], r["start_id"]
        with self.assertRaises(ValueError):
            parse(json.dumps(r), w)
        r["start_id"] = next(b["id"] for b in w["blocks"] if b["tag"] == "pb")
        with self.assertRaises(ValueError):
            parse(json.dumps(r), w)

    def test_abstention_with_non_null_bounds_rejected(self):
        w = self.windows["validation-02"]
        r = copy.deepcopy(self.outputs[(w["id"], "B")]["parsed"])
        r["decision"] = "abstain"
        r["uncertain"] = True
        with self.assertRaises(ValueError):
            parse(json.dumps(r), w)

    def test_duplicate_keys_rejected(self):
        with self.assertRaises(ValueError):
            parse('{"decision":"propose","decision":"abstain"}', self.windows["validation-02"])


if __name__ == "__main__":
    unittest.main()
