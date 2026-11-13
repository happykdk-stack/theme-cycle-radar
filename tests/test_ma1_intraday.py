import json
import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from traffic_lights import exchange_schedule, traffic_light


class MA1IntradayTests(unittest.TestCase):
    def frame(self):
        dates = pd.DatetimeIndex(exchange_schedule('한국', '2025-06-01', '2025-08-29').index).tz_localize(None)
        f = pd.DataFrame({'Close': 120.0}, index=dates)
        for date, price in [('2025-07-31', 150), ('2025-08-22', 120), ('2025-08-26', 100), ('2025-08-27', 105)]:
            f.loc[date, 'Close'] = price
        return f

    def test_intraday_daily_rise_is_twenty_points_without_ma5(self):
        f = self.frame()
        r = traffic_light(f, '한국', '2025-08-27T01:00Z', include_intraday=True)
        live = r['intraday']
        self.assertEqual(live['bullish_score'], 20)
        self.assertEqual([live['timeframes'][k]['state'] for k in ('monthly', 'weekly', 'daily')], ['down', 'down', 'up'])
        self.assertEqual(live['timeframes']['daily']['previous_ma1'], 100)
        self.assertEqual(live['timeframes']['daily']['ma1'], 105)
        self.assertEqual(live['asof'], '2025-08-27')
        self.assertEqual(r['asof'], '2025-08-26')
        self.assertEqual(r['green_history']['asof'], '2025-08-26')
        completed = traffic_light(f, '한국', '2025-08-27T01:00Z')
        self.assertEqual({**r, 'intraday': None}, completed)
        json.dumps(r, allow_nan=False)

    def test_future_prices_and_today_quote_cannot_change_completed_history(self):
        f = self.frame()
        r = traffic_light(f, '한국', '2025-08-27T01:00Z', include_intraday=True)
        f.loc['2025-08-28':, 'Close'] = 999999
        self.assertEqual(r, traffic_light(f, '한국', '2025-08-27T01:00Z', include_intraday=True))
        f.loc['2025-08-27', 'Close'] = 1000
        changed = traffic_light(f, '한국', '2025-08-27T01:00Z', include_intraday=True)
        self.assertEqual(changed['intraday']['bullish_score'], 100)
        self.assertEqual({**r, 'intraday': None}, {**changed, 'intraday': None})

    def test_intraday_is_available_only_during_exchange_session(self):
        f = self.frame()
        for now in ('2025-08-26T23:59Z', '2025-08-27T06:30Z', '2025-08-30T01:00Z'):
            with self.subTest(now=now):
                self.assertIsNone(traffic_light(f, '한국', now, include_intraday=True)['intraday'])
        after = traffic_light(f, '한국', '2025-08-27T06:30Z', include_intraday=True)
        self.assertEqual(after['timeframes']['daily']['state'], 'up')
        self.assertEqual(after['bullish_score'], 20)

    def test_missing_previous_session_is_unavailable_and_equal_price_is_flat(self):
        f = self.frame().drop(pd.Timestamp('2025-08-26'))
        r = traffic_light(f, '한국', '2025-08-27T01:00Z', include_intraday=True)
        self.assertIsNone(r['intraday'])
        self.assertEqual(r['signal'], 'gray')
        self.assertIsNone(r['bullish_score'])
        f = self.frame()
        f.loc['2025-08-27', 'Close'] = 100
        r = traffic_light(f, '한국', '2025-08-27T01:00Z', include_intraday=True)
        self.assertEqual(r['intraday']['timeframes']['daily']['state'], 'mixed')
        self.assertEqual(r['intraday']['bullish_score'], 0)
