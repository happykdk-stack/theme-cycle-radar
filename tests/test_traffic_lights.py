import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from traffic_lights import traffic_light, combine, exchange_schedule
from update_v4 import build_v4, detect


class TrafficLightTests(unittest.TestCase):
    def frame(self, market='미국', end='2025-08-29', direction=1):
        schedule = exchange_schedule(market, '2025-01-01', end)
        dates = pd.DatetimeIndex(schedule.index).tz_localize(None)
        values = 300 + direction * np.arange(len(dates), dtype=float)
        return pd.DataFrame({'Open': values, 'Close': values, 'Volume': 1000.}, index=dates)

    def test_all_colors(self):
        for states, color in [(['up']*3,'green'), (['down']*3,'red'),
                              (['up','down','up'],'yellow'), (['mixed']*3,'yellow'),
                              (['up','insufficient','up'],'gray')]:
            self.assertEqual(combine(states), color)

    def test_rising_and_falling_and_flat(self):
        for direction, color in [(1,'green'),(-1,'red'),(0,'yellow')]:
            with self.subTest(direction=direction):
                r = traffic_light(self.frame(direction=direction), '미국', '2025-08-29T21:00Z')
                self.assertEqual(r['signal'], color)
                self.assertEqual(r['timeframes']['monthly']['asof'], '2025-08-29')
                json.dumps(r, allow_nan=False)

    def test_intraday_and_future_prices_do_not_leak(self):
        f = self.frame(end='2025-09-30')
        expected = traffic_light(f.loc[:'2025-08-28'], '미국', '2025-08-29T19:59Z')
        f.loc['2025-08-29':, 'Close'] = 999999
        actual = traffic_light(f, '미국', '2025-08-29T19:59Z')
        self.assertEqual(actual, expected)
        self.assertEqual(actual['asof'], '2025-08-28')
        self.assertEqual(actual['timeframes']['weekly']['asof'], '2025-08-28')
        self.assertEqual(actual['timeframes']['monthly']['asof'], '2025-08-28')

    def test_current_month_and_week_are_provisional(self):
        f = self.frame(end='2025-08-29')
        r = traffic_light(f, '미국', '2025-08-27T21:00Z')
        self.assertEqual(r['timeframes']['monthly']['asof'], '2025-08-27')
        self.assertEqual(r['timeframes']['weekly']['asof'], '2025-08-27')
        self.assertTrue(r['timeframes']['monthly']['provisional'])
        self.assertTrue(r['timeframes']['weekly']['provisional'])

    def test_krx_close_boundary(self):
        f = self.frame(market='한국')
        before = traffic_light(f, '한국', '2025-08-29T06:29Z')
        after = traffic_light(f, '한국', '2025-08-29T06:30Z')
        self.assertEqual(before['asof'], '2025-08-28')
        self.assertEqual(after['asof'], '2025-08-29')
        self.assertEqual(after['signal'], 'green')

    def test_holiday_friday_completes_on_thursday(self):
        f = self.frame(end='2025-04-17')  # Good Friday is April 18.
        r = traffic_light(f, '미국', '2025-04-17T20:01Z')
        self.assertEqual(r['timeframes']['weekly']['asof'], '2025-04-17')

    def test_early_close(self):
        f = self.frame(end='2025-11-28')
        before = traffic_light(f, '미국', '2025-11-28T17:59Z')
        after = traffic_light(f, '미국', '2025-11-28T18:00Z')
        self.assertEqual(before['asof'], '2025-11-26')
        self.assertEqual(after['asof'], '2025-11-28')
        self.assertEqual(after['timeframes']['weekly']['asof'], '2025-11-28')

    def test_midweek_month_end_does_not_complete_week(self):
        f = self.frame(end='2025-04-30')
        r = traffic_light(f, '미국', '2025-04-30T21:00Z')
        self.assertEqual(r['timeframes']['weekly']['asof'], '2025-04-30')
        self.assertEqual(r['timeframes']['monthly']['asof'], '2025-04-30')

    def test_six_months_required_and_partial_first_month_excluded(self):
        f = self.frame(end='2025-06-30')
        self.assertEqual(traffic_light(f,'미국','2025-06-30T21:00Z')['signal'], 'green')
        r = traffic_light(f.iloc[1:], '미국', '2025-06-30T21:00Z')
        self.assertEqual(r['signal'], 'gray')
        self.assertEqual(r['timeframes']['monthly']['state'], 'insufficient')

    def test_missing_and_stale_data_are_gray(self):
        f = self.frame()
        for broken in [f.iloc[:-1], f.drop(f.index[-3]), f.assign(Close=np.nan), f.assign(Close=np.inf)]:
            r = traffic_light(broken, '미국', '2025-08-29T21:00Z')
            self.assertEqual(r['signal'], 'gray')
            json.dumps(r, allow_nan=False)

    def test_empty_and_short_data(self):
        for f in [pd.DataFrame(), self.frame().tail(4)]:
            self.assertEqual(traffic_light(f,'미국','2025-08-29T21:00Z')['signal'],'gray')

    def test_interior_gap_does_not_erase_available_period_closes(self):
        f = self.frame()
        f = f.drop(pd.Timestamp('2025-06-03'))
        r = traffic_light(f, '미국', '2025-08-29T21:00Z')
        self.assertEqual(r['signal'], 'green')
        self.assertEqual(r['timeframes']['monthly']['state'], 'up')

    def test_missing_final_month_close_is_insufficient(self):
        f = self.frame().drop(pd.Timestamp('2025-07-31'))
        r = traffic_light(f, '미국', '2025-08-29T21:00Z')
        self.assertEqual(r['signal'], 'gray')
        self.assertEqual(r['timeframes']['monthly']['state'], 'insufficient')

    def test_sort_duplicates_and_timezone(self):
        f = self.frame()
        expected = traffic_light(f,'미국','2025-08-29T21:00Z')
        f.index = f.index.tz_localize('America/New_York')
        f = pd.concat([f, f.tail(1)]).iloc[::-1]
        self.assertEqual(traffic_light(f,'미국','2025-08-29T21:00Z'), expected)

    def test_transition_date_recomputed_without_future_leak(self):
        f = self.frame(end='2025-09-05')
        f.loc['2025-09-02':, 'Close'] = 100.
        r = traffic_light(f,'미국','2025-09-05T21:00Z')
        self.assertEqual(r['signal'], 'yellow')
        self.assertEqual(r['last_changed'], '2025-09-02')
        prior = traffic_light(f,'미국','2025-08-29T21:00Z')
        self.assertEqual(prior['signal'], 'green')
        self.assertIsNone(prior['last_changed'])
        self.assertTrue(all(e['date'] <= r['asof'] for e in r['transitions']))

    def test_price_and_ma_direction_disagreement_is_mixed(self):
        f = self.frame()
        # Latest close below MA5, but higher than six bars ago: MA5 still rises.
        f.iloc[-6:, f.columns.get_loc('Close')] = [100, 110, 110, 110, 110, 105]
        r = traffic_light(f,'미국','2025-08-29T21:00Z')
        self.assertEqual(r['timeframes']['daily']['state'], 'mixed')
        self.assertEqual(r['signal'], 'yellow')

    def test_build_preserves_all_v42_metrics(self):
        f = self.frame()
        r = build_v4(lambda ticker: f, now='2025-08-29T21:00Z')
        baseline = detect(f, f)
        self.assertEqual(r['version'], '4.2')
        self.assertEqual(len(r['themes']), 14)
        for theme in r['themes']:
            for key, value in baseline.items():
                self.assertEqual(theme[key], value, key)
            self.assertIn('etf_trend', theme)
        json.dumps(r, allow_nan=False)

    def test_failed_etf_remains_visible_gray(self):
        f = self.frame()
        def fetch(ticker):
            if ticker == 'SOXX':
                raise ValueError('offline')
            return f
        r = build_v4(fetch, now='2025-08-29T21:00Z')
        soxx = next(t for t in r['themes'] if t['ticker'] == 'SOXX')
        self.assertEqual(soxx['etf_trend']['signal'], 'gray')
        self.assertNotIn('cycle_score', soxx)
        self.assertEqual(r['status'], 'partial')

    def test_calendar_failure_is_reported(self):
        with patch('traffic_lights.exchange_schedule', side_effect=RuntimeError('calendar unavailable')):
            r = build_v4(lambda ticker:self.frame(), now='2025-08-29T21:00Z')
        self.assertTrue(all(t['etf_trend']['signal']=='gray' for t in r['themes']))
        self.assertTrue(any('calendar unavailable' in e['message'] for e in r['errors']))

    def test_securities_etf_is_separate_from_existing_theme_scores(self):
        f = self.frame(market='한국')
        calls = []
        def fetch(ticker):
            calls.append(ticker)
            return f
        r = build_v4(fetch, now='2025-08-29T21:00Z')
        self.assertEqual(r['securities_etf']['ticker'], '102970.KS')
        self.assertEqual(r['securities_etf']['etf_trend']['signal'], 'green')
        self.assertEqual(calls.count('102970.KS'), 1)
        self.assertEqual(len(r['themes']), 14)

    def test_failed_securities_etf_is_gray_without_losing_themes(self):
        f = self.frame()
        def fetch(ticker):
            if ticker == '102970.KS':
                raise RuntimeError('securities ETF unavailable')
            return f
        r = build_v4(fetch, now='2025-08-29T21:00Z')
        self.assertEqual(r['securities_etf']['etf_trend']['signal'], 'gray')
        self.assertEqual(r['status'], 'partial')
        self.assertEqual(len(r['themes']), 14)


if __name__ == '__main__':
    unittest.main()
