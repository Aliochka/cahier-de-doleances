"""The draw is frozen; tests neither draw again nor write review decisions."""

import json
import unittest
from pathlib import Path

from campaigns.draw_five import draw


class CampaignTests(unittest.TestCase):
    def test_reproducible_without_replacement_and_input_order_independent(self):
        population = [f"document-{i:02}" for i in range(24)]
        self.assertEqual(draw(population), draw(list(reversed(population))))
        self.assertEqual(len(set(draw(population))), 5)
        self.assertTrue(set(draw(population)).issubset(population))

    def test_frozen_campaign_matches_draw_and_excludes_prior_review(self):
        campaign = json.loads((Path(__file__).parent / "campaigns/five-cahiers.json").read_text())
        self.assertEqual(len(campaign["population_human_validated_parents"]), 29)
        self.assertEqual(len(campaign["excluded_any_prior_article_event"]), 5)
        self.assertEqual(len(campaign["eligible_document_ids"]), 24)
        selected = [p["id"] for p in campaign["selected"]]
        self.assertEqual(selected, draw(campaign["eligible_document_ids"]))
        self.assertFalse(set(selected) & set(campaign["excluded_any_prior_article_event"]))
        self.assertTrue(
            all(p["initial_human_article_decisions"] == 0 for p in campaign["selected"])
        )


if __name__ == "__main__":
    unittest.main()
