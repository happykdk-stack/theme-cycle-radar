import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import numpy as np,pandas as pd
from update_v3 import calculate_v3
class V3Tests(unittest.TestCase):
 def test_flat_market_has_no_signals(self):
  idx=pd.bdate_range("2025-01-01",periods=160)
  d=pd.DataFrame({"Open":np.full(160,100.),"Close":np.full(160,100.),"Volume":np.full(160,1000.)},index=idx)
  r=calculate_v3(d,d)
  self.assertEqual(r["signals_v3"],[])
  self.assertIsNone(r["stats_v3"]["20d"]["win_rate_pct"])
 def test_last_day_cannot_have_future_return(self):
  idx=pd.bdate_range("2025-01-01",periods=160)
  c=np.linspace(100,150,160)
  d=pd.DataFrame({"Open":c,"Close":c,"Volume":np.full(160,1000.)},index=idx)
  r=calculate_v3(d,pd.DataFrame({"Close":np.full(160,100.)},index=idx))
  self.assertTrue(all(x["return_20d_pct"] is None for x in r["signals_v3"] if x["date"]>=str(idx[-20].date())))
if __name__=="__main__":unittest.main()
