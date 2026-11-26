import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from per_slopes import daily_per_slopes
from traffic_lights import exchange_schedule


class PERSlopeTests(unittest.TestCase):
    def sessions(self, market='미국'):
        return [d.date().isoformat() for d in exchange_schedule(market, '2026-10-01', '2026-11-30').index]

    def test_exact_exchange_session_endpoints_and_direction(self):
        days = self.sessions()
        for movement in (-.2, 0., .2):
            history = [{'date': d, 'pe': 20 + movement * i} for i, d in enumerate(days)]
            result = daily_per_slopes(history, '미국', days[-1])
            row = result[20]
            self.assertEqual(row['baseline_date'], days[5])
            self.assertAlmostEqual(row['slope_per_session'], movement)
            self.assertAlmostEqual(row['change_pct'], round(((20 + movement*20)/(20 + movement*5)-1)*100, 6))
            self.assertEqual(result[14]['status'], 'missing_baseline')
            self.assertEqual(result[15]['status'], 'ok')

    def test_missing_baseline_is_not_replaced_by_nearby_observation(self):
        days = self.sessions()
        history = [{'date': d, 'pe': 20.} for i, d in enumerate(days) if i != 5]
        row = next(r for r in daily_per_slopes(history, '미국', days[-1]) if r['date'] == days[20])
        self.assertEqual(row['baseline_date'], days[5])
        self.assertEqual(row['status'], 'missing_baseline')
        self.assertIsNone(row['slope_per_session'])

    def test_holiday_and_weekend_observations_are_not_trading_sessions(self):
        history = [{'date': d, 'pe': 10.} for d in ('2026-11-21', '2026-11-26')]
        self.assertTrue(all(r['status'] == 'non_session' for r in daily_per_slopes(history, '미국', '2026-11-26')))

    def test_future_data_cannot_change_prior_results(self):
        days = self.sessions()
        history = [{'date': d, 'pe': 20+i/10} for i, d in enumerate(days)]
        earlier = daily_per_slopes(history, '미국', days[20])
        history[-1]['pe'] = 999.
        self.assertEqual(earlier, daily_per_slopes(history, '미국', days[20]))
        self.assertEqual(earlier[-1]['date'], days[20])

    def test_invalid_points_and_calendar_errors_never_become_zero(self):
        history = [{'date': 'bad', 'pe': 10}, {'date': '2026-11-25', 'pe': 0},
                   {'date': '2026-11-24', 'pe': float('nan')}]
        self.assertEqual(daily_per_slopes(history, '미국', '2026-11-26'), [])
        with patch('per_slopes.exchange_schedule', side_effect=RuntimeError('offline')):
            rows = daily_per_slopes([{'date': '2026-11-25', 'pe': 20}], '미국', '2026-11-26')
        self.assertEqual(rows[0]['status'], 'calendar_error')
        self.assertIsNone(rows[0]['slope_per_session'])
