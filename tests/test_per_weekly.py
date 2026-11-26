import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from per_weekly import weekly_per_observations


class WeeklyPERTests(unittest.TestCase):
    def test_last_observation_is_not_relabelled_friday_and_partial_week_is_explicit(self):
        rows = weekly_per_observations([
            {'date':'2026-11-13','pe':20}, {'date':'2026-11-16','pe':19.5},
            {'date':'2026-11-17','pe':19}, {'date':'2026-11-26','pe':18}], '2026-11-26')
        self.assertEqual([r['week_start'] for r in rows], ['2026-11-09','2026-11-16','2026-11-23'])
        self.assertEqual(rows[1]['date'], '2026-11-17')
        self.assertEqual(rows[1]['observations'], 2)
        self.assertEqual(rows[1]['change_pct'], -5)
        self.assertEqual(rows[2]['baseline_date'], '2026-11-17')
        self.assertTrue(rows[2]['is_partial_week'])
        self.assertFalse(rows[1]['is_partial_week'])

    def test_gap_does_not_compare_with_older_week(self):
        rows = weekly_per_observations([{'date':'2026-11-13','pe':20}, {'date':'2026-11-26','pe':18}], '2026-11-26')
        self.assertIsNone(rows[-1]['change_pct'])
        self.assertIsNone(rows[-1]['baseline_date'])

    def test_year_boundary_zero_change_duplicate_and_invalid_values(self):
        rows = weekly_per_observations([
            {'date':'2026-12-27','pe':10}, {'date':'2027-01-01','pe':9},
            {'date':'2027-01-01','pe':10}, {'date':'2027-01-02','pe':float('inf')},
            {'date':'2027-01-03','pe':0}, {'date':'2027-01-04','pe':20},
            {'date':'bad','pe':3}, {'pe':5}], '2027-01-03')
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[-1]['week_start'], '2026-12-28')
        self.assertEqual(rows[-1]['change_pct'], 0)
        self.assertFalse(rows[-1]['is_partial_week'])
        self.assertEqual(rows[-1]['observations'], 1)

if __name__ == '__main__':
    unittest.main()
