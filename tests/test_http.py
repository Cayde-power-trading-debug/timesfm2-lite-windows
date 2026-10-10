import unittest,tempfile,threading,json,urllib.request,urllib.error,time,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import create_server

class FakeRunner:
 def forecast(self,prepared,horizon,requested,progress):
  progress(55,'transport test')
  from core import output_times
  from calendar_tools import Calendar
  return [{'time':t,'value':0.,'calendar':Calendar().label(t[:10])} for t in output_times(prepared,horizon)],{'device':'cpu','test':'transport only'}

class HTTPTest(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.server=create_server(0,Path(self.temp.name),FakeRunner());threading.Thread(target=self.server.serve_forever,daemon=True).start();self.url=f'http://127.0.0.1:{self.server.server_port}'
 def tearDown(self):self.server.shutdown();self.server.server_close();self.temp.cleanup()
 def read(self,path):return json.load(urllib.request.urlopen(self.url+path))
 def post(self,path,body,origin=None):
  headers={'Content-Type':'application/json','X-Lite-Token':self.server.service.token}
  if origin:headers['Origin']=origin
  return urllib.request.urlopen(urllib.request.Request(self.url+path,json.dumps(body).encode(),headers=headers))
 def test_preview_predict_and_export(self):
  self.assertTrue(self.read('/api/health')['ok'])
  payload={'text':'0\n1\n2','start':'2026-10-09T21:00','interval_minutes':60,'horizon':2}
  self.assertEqual(json.load(self.post('/api/preview',payload))['rows'][0]['value'],0)
  job=json.load(self.post('/api/predict',payload))['job_id']
  for _ in range(100):
   state=self.read('/api/jobs/'+job)
   if state['status'] in ('done','failed'):break
   time.sleep(.01)
  self.assertEqual(state['status'],'done',state)
  self.assertEqual(state['predictions'][0]['calendar']['label'],'工作日（补班）')
  report=urllib.request.urlopen(self.url+state['exports']['output_url']).read().decode()
  self.assertIn('工作日（补班）',report)
  self.assertTrue((Path(self.temp.name)/'输入与输出'/job/'输入.html').is_file())
 def test_remote_origin_and_missing_token_rejected(self):
  with self.assertRaises(urllib.error.HTTPError) as e:self.post('/api/preview',{},'https://example.com')
  self.assertEqual(e.exception.code,403)
  with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(urllib.request.Request(self.url+'/api/preview',b'{}',headers={'Content-Type':'application/json'}))
  self.assertEqual(e.exception.code,403)
 def test_bad_input_returns_error(self):
  with self.assertRaises(urllib.error.HTTPError) as e:self.post('/api/preview',{'text':'nan','start':'2026-10-01T00:00'})
  self.assertEqual(e.exception.code,400)

if __name__=='__main__':unittest.main()
