from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse,unquote
from datetime import datetime
import json,threading,uuid,secrets,os,argparse,webbrowser,traceback,time,mimetypes
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from core import ROOT,HOME,prepare_input,ModelRuntime,model_config
from exporter import save_run

class Service:
    def __init__(self,home,runner=None):
        self.home=Path(home);self.runner=runner or ModelRuntime();self.token=secrets.token_urlsafe(24);self.jobs={};self.active=None;self.lock=threading.Lock()
    def submit(self,payload):
        prepared=prepare_input(payload);horizon=int(payload.get('horizon',24));device=payload.get('device',model_config()['device'])
        if not 1<=horizon<=2048:raise ValueError('预测步数须为1至2048')
        if device not in ('auto','cpu','gpu'):raise ValueError('设备选项错误')
        with self.lock:
            if self.active:raise BlockingIOError('已有任务运行，完成后再提交')
            run_id=datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6]
            self.active=run_id;self.jobs[run_id]={'job_id':run_id,'status':'running','progress':5,'stage':'检查输入和时间轴','started_at':time.time()}
        def work():
            state=self.jobs[run_id]
            try:
                def progress(p,s):state.update(progress=p,stage=s)
                predictions,meta=self.runner.forecast(prepared,horizon,requested=device,progress=progress)
                progress(90,'保存输入及预测HTML');exports=save_run(self.home,prepared,predictions,meta,run_id)
                state.update(status='done',progress=100,stage='完成，HTML已保存',predictions=predictions,meta=meta,exports=exports,elapsed_seconds=round(time.time()-state['started_at'],2))
            except Exception as e:
                state.update(status='failed',stage='任务失败',error=str(e),elapsed_seconds=round(time.time()-state['started_at'],2))
                log=self.home/'日志';log.mkdir(parents=True,exist_ok=True);(log/(run_id+'.txt')).write_text(traceback.format_exc(),encoding='utf8')
            finally:
                with self.lock:self.active=None
        threading.Thread(target=work,daemon=True).start();return run_id

def create_server(port=8899,home=HOME,runner=None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,fmt,*args):pass
        def allowed(self):
            origin=self.headers.get('Origin')
            return origin is None or origin in (f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}')
        def send(self,data,code=200,content_type='application/json; charset=utf-8'):
            raw=json.dumps(data,ensure_ascii=False,allow_nan=False).encode() if isinstance(data,(dict,list)) else data.encode() if isinstance(data,str) else data
            self.send_response(code);self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(raw)
        def do_GET(self):
            if not self.allowed():self.send({'error':'仅允许本地页面访问'},403);return
            path=unquote(urlparse(self.path).path);service=self.server.service
            if path=='/api/health':
                import importlib.util
                self.send({'ok':True,'app':'TimesFM2 Lite','token':service.token,'active_job':service.active,'context_len':model_config()['context_len'],'installed':importlib.util.find_spec('torch') is not None,'weights_exist':(service.home/'models'/'timesfm-2.0-500m-pytorch'/'torch_model.ckpt').is_file()});return
            if path.startswith('/api/jobs/'):
                state=service.jobs.get(path.rsplit('/',1)[1]);self.send(state if state else {'error':'任务不存在'},200 if state else 404);return
            if path in ('/','/输入与预测.html'):
                self.send((ROOT/'输入与预测.html').read_bytes(),content_type='text/html; charset=utf-8');return
            if path.startswith('/runs/'):
                parts=path.split('/')
                if len(parts)==4 and parts[2] in service.jobs and parts[3] in ('输入.html','预测结果.html','输入.csv','预测.csv','复现.json','校验.json'):
                    file=service.home/'输入与输出'/parts[2]/parts[3]
                    if file.is_file():self.send(file.read_bytes(),content_type='text/html; charset=utf-8' if file.suffix=='.html' else 'application/json; charset=utf-8' if file.suffix=='.json' else 'text/csv; charset=utf-8');return
            self.send({'error':'页面不存在'},404)
        def do_POST(self):
            if not self.allowed() or self.headers.get('X-Lite-Token')!=self.server.service.token:self.send({'error':'请求来源或本地令牌不正确'},403);return
            try:
                length=int(self.headers.get('Content-Length',0))
                if not 0<length<=10_000_000:raise ValueError('输入为空或超过10MB')
                payload=json.loads(self.rfile.read(length));path=urlparse(self.path).path
                if path=='/api/preview':self.send(prepare_input(payload));return
                if path=='/api/predict':self.send({'job_id':self.server.service.submit(payload)},202);return
                self.send({'error':'接口不存在'},404)
            except BlockingIOError as e:self.send({'error':str(e)},409)
            except (ValueError,TypeError,KeyError) as e:self.send({'error':str(e)},400)
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler);server.service=Service(home,runner);return server

def main():
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8899);p.add_argument('--open',action='store_true');v=p.parse_args()
    server=create_server(v.port);HOME.mkdir(parents=True,exist_ok=True);pid_file=HOME/'本地服务.json'
    pid_file.write_text(json.dumps({'pid':os.getpid(),'port':server.server_port,'app':str(ROOT/'app.py')},ensure_ascii=False),encoding='utf8')
    url=f'http://127.0.0.1:{server.server_port}';print('TimesFM2 Lite:',url,flush=True)
    if v.open:webbrowser.open(url)
    try:server.serve_forever()
    finally:server.server_close();pid_file.unlink(missing_ok=True)

if __name__=='__main__':main()
