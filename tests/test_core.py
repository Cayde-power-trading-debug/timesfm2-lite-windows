import unittest,sys,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from calendar_tools import Calendar, parse_notice, validate_calendar
from core import prepare_input, output_times, model_config, select_device, ModelRuntime
from exporter import render_report

class CalendarTest(unittest.TestCase):
 def setUp(self):self.cal=Calendar()
 def test_official_vacation_and_makeup(self):
  self.assertEqual(self.cal.label('2026-09-26')['type'],'holiday')
  self.assertEqual(self.cal.label('2026-10-07')['type'],'holiday')
  self.assertEqual(self.cal.label('2026-10-10')['type'],'workday')
  self.assertEqual(self.cal.label('2026-10-11')['type'],'weekend')
  self.assertEqual(self.cal.label('2027-10-01')['type'],'unknown')
 def test_calendar_conflict_rejected(self):
  with self.assertRaises(ValueError):validate_calendar({'covered_years':[2026],'holidays':{'2026-10-01':'国庆节'},'workdays':{'2026':['2026-10-01']}})
 def test_notice_ranges(self):
  s='国务院办公厅关于2026年部分节假日安排的通知。一、元旦：1月1日（周四）至3日（周六）放假调休，共3天。1月4日（周日）上班。六、中秋节：9月25日（周五）至27日（周日）放假，共3天。七、国庆节：10月1日（周四）至7日（周三）放假调休，共7天。9月20日（周日）、10月10日（周六）上班。'
  v=parse_notice(s,2026)
  self.assertEqual(len(v['holidays']),13)
  self.assertIn('2026-09-27',v['holidays'])
  self.assertEqual(v['workdays']['2026'],['2026-01-04','2026-09-20','2026-10-10'])

class InputTest(unittest.TestCase):
 def test_real_zero_kept_missing_causal(self):
  p=prepare_input({'text':'2026-10-01 00:00,0\n2026-10-01 01:00,2\n2026-10-01 03:00,99','interval_minutes':60,'fill_missing':True})
  self.assertEqual(p['values'],[0.,2.,1.,99.])
  self.assertEqual(p['rows'][2]['imputed'],True)
 def test_nan_duplicate_and_irregular_reject(self):
  for text in ['2026-10-01 00:00,nan','2026-10-01 00:00,1\n2026-10-01 00:00,2','2026-10-01 00:00,1\n2026-10-01 00:31,2']:
   with self.assertRaises(ValueError):prepare_input({'text':text,'interval_minutes':60})
 def test_numbers_time_generation(self):
  p=prepare_input({'text':'1\n2\n0','start':'2026-10-08T00:00','interval_minutes':60})
  self.assertEqual(p['rows'][-1]['time'],'2026-10-08 02:00')
  self.assertEqual(output_times(p,2),['2026-10-08 03:00','2026-10-08 04:00'])
 def test_max_context(self):
  self.assertEqual(model_config()['context_len'],2048)
 def test_exported_csv_can_be_reimported(self):
  p=prepare_input({'text':'时间,数值,日期标签,补齐\n2026-10-01 00:00,0,伪标签,False\n2026-10-01 01:00,2,伪标签,False','interval_minutes':60})
  self.assertEqual(p['values'],[0.,2.])
  self.assertEqual(p['rows'][0]['calendar']['type'],'holiday')
 def test_auto_device_works_without_gpu(self):
  class CUDA:
   def is_available(self):return False
  class Torch:cuda=CUDA()
  self.assertEqual(select_device(Torch(),'auto')[0],'cpu')
  with self.assertRaises(RuntimeError):select_device(Torch(),'gpu')
 def test_gpu_oom_auto_falls_back_but_explicit_gpu_does_not(self):
  class Runner(ModelRuntime):
   def _forecast(self,p,h,requested,progress):
    self.last_device='gpu' if requested!='cpu' else 'cpu'
    if requested!='cpu':raise RuntimeError('CUDA out of memory')
    return [],{'device':'cpu'}
  self.assertEqual(Runner().forecast({},1,'auto')[1]['device'],'cpu')
  with self.assertRaises(RuntimeError):Runner().forecast({},1,'gpu')
 def test_export_escapes_title(self):
  v=render_report('输入<script>alert(1)</script>',[{'time':'2026-10-01 00:00','value':0,'calendar':{'label':'国庆节','type':'holiday'}}],{'device':'cpu'})
  self.assertNotIn('<script>alert(1)</script>',v)
  self.assertIn('国庆节',v)
  self.assertIn('0',v)

if __name__=='__main__':unittest.main()
