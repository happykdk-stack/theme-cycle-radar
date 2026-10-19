import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import numpy as np,pandas as pd
from update_v2 import calculate_v2
class V2Tests(unittest.TestCase):
 def test_no_future_leak_and_no_signals_on_flat_market(self):
  idx=pd.bdate_range("2025-01-01",periods=120)
  f=pd.DataFrame({"Open":np.full(120,100.),"Close":np.full(120,100.),"Volume":np.full(120,1000.)},index=idx)
  r=calculate_v2(f,f)
  self.assertEqual(len(r["signals_v2"]),0)
  self.assertIsNone(r["stats_v2"]["5d"]["win_rate_pct"])
 def test_no_fabricated_returns_without_open(self):
  idx=pd.bdate_range("2025-01-01",periods=120)
  close=np.linspace(100,180,120)
  f=pd.DataFrame({"Close":close,"Volume":np.full(120,1500.)},index=idx)
  r=calculate_v2(f,pd.DataFrame({"Close":np.full(120,100.)},index=idx))
  self.assertTrue(all(s["return_5d_pct"] is None for s in r["signals_v2"]))
if __name__=="__main__":unittest.main()
