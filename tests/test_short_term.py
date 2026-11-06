import sys
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from short_term import evaluate, build

class ShortTermTests(unittest.TestCase):
    def test_no_signal_without_bars(self):
        self.assertEqual(evaluate(pd.DataFrame())["status"], "N/A")

    def test_no_false_bounce(self):
        idx = pd.date_range("2026-11-06 09:00", periods=12, freq="5min", tz="Asia/Seoul")
        f = pd.DataFrame({"Open":np.full(12,100.),"High":np.full(12,101.),
                          "Low":np.full(12,99.),"Close":np.full(12,100.),
                          "Volume":np.full(12,100.)},index=idx)
        self.assertEqual(evaluate(f)["status"], "관찰")

    def test_market_gate(self):
        idx = pd.to_datetime(["2026-11-05 15:30","2026-11-06 15:30"]).tz_localize("Asia/Seoul")
        f = pd.DataFrame({"Open":[100.,95.],"High":[100.,95.],
                          "Low":[100.,95.],"Close":[100.,95.],
                          "Volume":[100.,100.]},index=idx)
        def fetch(symbol, interval, period):
            if symbol != "^KS11":raise AssertionError("5m data must not be fetched")
            return f
        result=build(now="2026-11-06T07:00:00Z",fetch=fetch)
        self.assertEqual(result["status"],"조건 미충족")
        self.assertEqual(result["candidates"],[])

if __name__ == "__main__":
    unittest.main()
