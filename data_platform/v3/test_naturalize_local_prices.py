"""Numerical properties of personal fixture prices; no database writes."""

import unittest
import os
from datetime import timedelta

import numpy as np

from naturalize_local_prices import connect_local, generate_path
from domain_roll import statements


class NaturalPriceTests(unittest.TestCase):
    def test_reproducible_and_series_independent(self):
        first = generate_path("market-one", 2500, 1096)
        np.testing.assert_array_equal(first, generate_path("market-one", 2500, 1096))
        self.assertFalse(np.array_equal(first, generate_path("market-two", 2500, 1096)))
        # Extending a history keeps every previous price stable.
        np.testing.assert_array_equal(first[:731], generate_path("market-one", 2500, 731))

    def test_order_positive_and_bounds(self):
        for base, category in [(1200, "vegetable"), (2200, "cereal"), (18000, "spice")]:
            path = generate_path(category, base, 1096, category)
            self.assertTrue(np.isfinite(path).all())
            self.assertTrue((path[:, 0] > 0).all())
            self.assertTrue((path[:, 0] <= path[:, 1]).all())
            self.assertTrue((path[:, 1] <= path[:, 2]).all())
            self.assertTrue((path[:, 1] >= base * .60 - 1).all())
            self.assertTrue((path[:, 1] <= base * 1.70 + 1).all())

    def test_no_repeating_wave_and_daily_movement(self):
        for series in ("wheat-punjab", "rice-tamil-nadu", "tomato-maharashtra"):
            prices = generate_path(series, 2600, 1096)[:, 1]
            changes = np.diff(prices)
            yearly_correlation = np.corrcoef(changes[:-365], changes[365:])[0, 1]
            self.assertLess(abs(yearly_correlation), .2)
            self.assertGreater(np.mean(changes > 0), .30)
            self.assertGreater(np.mean(changes < 0), .30)
            self.assertGreater(len(np.unique(prices)), 300)
            self.assertLess(np.max(np.abs(changes / prices[:-1])), .08)
            # Daily increments are not a repeating oscillator or white-price noise.
            self.assertGreater(np.corrcoef(changes[:-1], changes[1:])[0, 1], .05)


@unittest.skipUnless(os.environ.get("SKYVIEW_LOCAL_PRICE_INTEGRATION") == "1", "Opt-in local transaction test")
class PriceRolloverIntegrationTests(unittest.TestCase):
    def test_rollover_carries_paths_without_overwriting_or_flattening(self):
        conn = connect_local()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT max(observed_on) FROM sv3.price_observations")
                tomorrow = cur.fetchone()[0] + timedelta(days=1)
                cur.execute(statements(tomorrow))
                cur.execute("""SELECT count(*),count(*) FILTER(WHERE p.modal_price<>expected.central_price)
                    FROM sv3.price_observations p JOIN domain_roll_series s ON s.id=p.series_id
                    JOIN LATERAL(SELECT pp.central_price FROM sv3.price_projections pp JOIN sv3.forecast_runs r ON r.id=pp.run_id
                        JOIN sv3.datasets d ON d.id=r.dataset_id WHERE pp.series_id=p.series_id AND pp.valid_on=p.observed_on
                        AND pp.kind='scenario' AND d.origin='synthetic' ORDER BY r.issued_at DESC LIMIT 1)expected ON true
                    WHERE p.observed_on=%s""", (tomorrow,))
                count, mismatch = cur.fetchone()
                self.assertGreater(count, 0)
                self.assertEqual(mismatch, 0)
                cur.execute("SELECT count(*),count(DISTINCT central_price) FROM sv3.price_projections WHERE valid_on=%s", (tomorrow + timedelta(days=365),))
                tail_count, distinct = cur.fetchone()
                self.assertGreater(distinct, 100)
                cur.execute("DROP TABLE domain_roll_series")
                cur.execute(statements(tomorrow))
                cur.execute("SELECT count(*) FROM sv3.price_observations WHERE observed_on=%s", (tomorrow,))
                self.assertEqual(cur.fetchone()[0], count)
                cur.execute("SELECT count(*) FROM sv3.price_projections WHERE valid_on=%s", (tomorrow + timedelta(days=365),))
                self.assertEqual(cur.fetchone()[0], tail_count)
        finally:
            # Never advance the actual local data clock during a test.
            conn.rollback()
            conn.close()


if __name__ == "__main__":
    unittest.main()
