import csv,sys,unittest,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from per_data import krx_csv_pe
class KRXTests(unittest.TestCase):
 def test_authorized_csv_only(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"per.csv"
   p.write_text("date,ticker,pe,source\n2026-11-12,^KS11,12.8,KRX licensed export\n2026-11-13,^KS11,13.2,KRX licensed export\n",encoding="utf-8")
   result=krx_csv_pe(p)
   self.assertEqual([x["pe"] for x in result["^KS11"]["history"]],[12.8,13.2])
 def test_reject_unattributed(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"per.csv"
   p.write_text("date,ticker,pe,source\n2026-11-13,^KS11,13.2,unknown\n",encoding="utf-8")
   with self.assertRaises(ValueError):krx_csv_pe(p)
if __name__=="__main__":unittest.main()
