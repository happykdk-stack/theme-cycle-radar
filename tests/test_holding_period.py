import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from update_v3 import HORIZONS,horizon_report
class HoldingPeriodTests(unittest.TestCase):
 def test_insufficient(self):
  rows=[{f"return_{h}d_pct":1 for h in HORIZONS} for _ in range(8)]
  self.assertEqual(horizon_report(rows)["status"],"insufficient")
 def test_training_selection_ignores_test(self):
  rows=[]
  for i in range(20):
   rows.append({f"return_{h}d_pct":(3 if h==10 else 1) if i<14 else (-10 if h==10 else 2) for h in HORIZONS})
  r=horizon_report(rows)
  self.assertEqual(r["best_days"],10)
  self.assertLess(next(x for x in r["table"] if x["days"]==10)["test"]["avg_return_pct"],0)
if __name__=="__main__":unittest.main()
