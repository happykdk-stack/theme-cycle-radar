import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from per_data import discover_ecos_kospi_per
class DiscoveryTests(unittest.TestCase):
 def test_unique_verified_series(self):
  def fake(service,key,*parts):
   if service=="StatisticTableList":return {"StatisticTableList":{"row":[{"STAT_CODE":"ABC","STAT_NAME":"코스피 주가이익비율 PER","SRCH_YN":"Y"}]}}
   return {"StatisticItemList":{"row":[{"ITEM_CODE":"KOSPI","ITEM_NAME":"코스피","CYCLE":"M"}]}}
  with patch("per_data.ecos_json",side_effect=fake):
   self.assertEqual(discover_ecos_kospi_per("test")[:2],("ABC","KOSPI"))
 def test_ambiguous_is_rejected(self):
  with patch("per_data.ecos_json",return_value={"StatisticTableList":{"row":[]}}):
   with self.assertRaises(ValueError):discover_ecos_kospi_per("test")
if __name__=="__main__":unittest.main()
