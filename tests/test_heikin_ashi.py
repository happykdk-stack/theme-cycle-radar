import sys
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from heikin_ashi import ha_candles, ha_traffic_light

class HeikinAshiTests(unittest.TestCase):
    def test_recursive_candles(self):
        idx = pd.date_range("2025-01-01", periods=2)
        raw = pd.DataFrame({"Open":[10.,12.], "High":[14.,16.],
                            "Low":[9.,11.], "Close":[13.,15.]}, index=idx)
        result = ha_candles(raw)
        self.assertAlmostEqual(result["Close"].iloc[0], 11.5)
        self.assertAlmostEqual(result["Open"].iloc[0], 11.5)
        self.assertAlmostEqual(result["Open"].iloc[1], 11.5)
        self.assertAlmostEqual(result["Close"].iloc[1], 13.5)

    def test_actual_change_is_independent_of_ha_direction(self):
        from traffic_lights import exchange_schedule
        sessions = pd.DatetimeIndex(exchange_schedule("미국", "2025-01-01", "2025-08-29").index).tz_localize(None)
        prices = np.linspace(100., 180., len(sessions))
        frame = pd.DataFrame({"Open": prices - 1, "High": prices + 2,
                              "Low": prices - 2, "Close": prices, "Volume": 1000.}, index=sessions)
        frame.loc["2025-08-29", "Open"] = 190.
        frame.loc["2025-08-29", "High"] = 191.
        result = ha_traffic_light(frame, "미국", "2025-08-29T21:00Z")
        month = result["timeframes"]["monthly"]
        self.assertIn("actual_change_pct", month)
        self.assertAlmostEqual(month["actual_change_pct"], round((month["actual_close"] / month["actual_open"] - 1) * 100, 2))
        self.assertIn("ha_open", month)
        self.assertIn("ha_close", month)

    def test_future_prices_do_not_change_past_signal(self):
        from traffic_lights import exchange_schedule
        sessions = pd.DatetimeIndex(exchange_schedule("미국", "2025-01-01", "2025-08-29").index).tz_localize(None)
        close = np.linspace(100., 200., len(sessions))
        frame = pd.DataFrame({"Open":close-1, "High":close+2,
                              "Low":close-2, "Close":close,
                              "Volume":1000.}, index=sessions)
        earlier = ha_traffic_light(frame.loc[:"2025-08-28"], "미국", "2025-08-29T19:59Z")
        frame.loc["2025-08-29", "Close"] = 999999.
        after = ha_traffic_light(frame, "미국", "2025-08-29T19:59Z")
        self.assertEqual(earlier["signal"], after["signal"])
        self.assertEqual(earlier["timeframes"], after["timeframes"])
        self.assertEqual(earlier["method"], "Heikin-Ashi")

if __name__ == "__main__":
    unittest.main()
