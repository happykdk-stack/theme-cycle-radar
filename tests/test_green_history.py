import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from traffic_lights import traffic_light, green_history, exchange_schedule, combine
from update_v4 import build_v4


class GreenHistoryTests(unittest.TestCase):
    def frame(self):
        dates = pd.DatetimeIndex(exchange_schedule('한국', '2023-08-01', '2025-08-29').index).tz_localize(None)
        values = 300 + np.arange(len(dates)) * .1 + 20 * np.sin(np.arange(len(dates)) / 12)
        return pd.DataFrame({'Close': values, 'Open': values, 'Volume': 1000.}, index=dates)

    def test_history_matches_independent_daily_prefix_oracle(self):
        f = self.frame()
        # Evaluate each day's partial monthly/weekly candle independently.
        colors = []
        for day in f.index:
            states = []
            for frequency in ('M', 'W-FRI', 'D'):
                bars = f.Close.loc[:day].groupby(f.loc[:day].index.to_period(frequency)).last()
                ma = bars.rolling(5).mean()
                if len(bars) < 6 or pd.isna(ma.iloc[-2]):
                    states.append('insufficient')
                elif bars.iloc[-1] > ma.iloc[-1] > ma.iloc[-2]:
                    states.append('up')
                elif bars.iloc[-1] < ma.iloc[-1] < ma.iloc[-2]:
                    states.append('down')
                else:
                    states.append('mixed')
            colors.append(combine(states))
        expected = pd.Series(colors, index=f.index)
        r = traffic_light(f, '한국', '2025-08-29T06:30Z')
        self.assertEqual(r['green_history'], green_history(expected))
        self.assertGreater(len(r['green_history']['runs']), 2)
        self.assertTrue(r['green_history']['complete'])
        for date in ('2025-02-04', '2025-04-30', '2025-08-27'):
            prefix = traffic_light(f, '한국', date + 'T06:30Z')
            self.assertEqual(prefix['signal'], expected.loc[date])
            self.assertEqual(prefix['green_history'], green_history(expected.loc[:date]))
            changed = f.copy()
            changed.loc[changed.index > date, 'Close'] = 999999
            self.assertEqual(prefix, traffic_light(changed, '한국', date + 'T06:30Z'))

    def test_runs_weekend_single_day_and_year_boundary(self):
        dates = pd.to_datetime(['2024-02-28', '2024-02-29', '2024-03-01',
                                '2025-02-21', '2025-02-24', '2025-02-25', '2025-02-28'])
        s = pd.Series(['green', 'green', 'yellow', 'green', 'green', 'red', 'green'], index=dates)
        h = green_history(s)
        self.assertEqual(h['window_start'], '2024-02-28')
        self.assertEqual(h['runs'][1], {'start_date': '2025-02-21', 'end_date': '2025-02-24', 'active': False})
        self.assertEqual(h['latest_run'], {'start_date': '2025-02-28', 'end_date': '2025-02-28', 'active': True})
        self.assertEqual(h['latest_date'], '2025-02-28')
        s.iloc[-1] = 'yellow'
        self.assertEqual(green_history(s)['latest_date'], '2025-02-24')
        self.assertFalse(green_history(s)['latest_run']['active'])

    def test_none_outside_window_and_incomplete_are_distinct(self):
        dates = pd.date_range('2023-01-01', '2025-08-29', freq='B')
        s = pd.Series('yellow', index=dates)
        s.iloc[0] = 'green'
        h = green_history(s)
        self.assertEqual(h['runs'], [])
        self.assertIsNone(h['latest_run'])
        self.assertIsNone(h['latest_date'])
        self.assertTrue(h['complete'])
        s.iloc[-2] = 'gray'
        self.assertFalse(green_history(s)['complete'])
        self.assertFalse(green_history(s.tail(20))['complete'])

    def test_overlapping_run_keeps_start_before_window(self):
        dates = pd.date_range('2023-01-01', '2025-08-29', freq='B')
        s = pd.Series('green', index=dates)
        h = green_history(s)
        self.assertLess(h['latest_run']['start_date'], h['window_start'])
        self.assertTrue(h['latest_run']['active'])

    def test_missing_latest_session_breaks_run_but_preserves_history(self):
        f = self.frame()
        f.Close = 300 + np.arange(len(f))
        r = traffic_light(f.iloc[:-1], '한국', '2025-08-29T06:30Z')
        self.assertEqual(r['signal'], 'gray')
        self.assertEqual(r['green_history']['latest_date'], '2025-08-28')
        self.assertFalse(r['green_history']['latest_run']['active'])
        self.assertFalse(r['green_history']['complete'])

    def test_live_download_uses_two_years_only_for_securities(self):
        f = self.frame()
        with patch('update_v4.series_download', return_value=f) as fetch:
            build_v4(fetch=fetch, now='2025-08-29T06:30Z')
        calls = [call for call in fetch.call_args_list if call.args == ('102970.KS',)]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].kwargs, {'period': '2y'})
        self.assertTrue(all(not call.kwargs for call in fetch.call_args_list if call.args != ('102970.KS',)))
