from pathlib import Path
from datetime import datetime,timedelta
import json,math,re,statistics,os,time,threading
from calendar_tools import Calendar
ROOT=Path(__file__).resolve().parent
HOME=Path(os.environ.get('NOVA_LITE_HOME',str(ROOT))).resolve()

def model_config():
    v=json.loads((ROOT/'config'/'model.json').read_text(encoding='utf8'))
    if not 32<=v['context_len']<=2048 or v['context_len']%32:raise ValueError('TimesFM 2.0上下文必须为32的倍数，最大2048')
    if not 1<=v['batch_size']<=4:raise ValueError('轻量版batch_size应为1至4')
    return v

def prepare_input(payload,calendar=None):
    cal=calendar or Calendar();step=int(payload.get('interval_minutes',60))
    if not 1<=step<=525600:raise ValueError('间隔分钟须为1至525600')
    text=str(payload.get('text','')).strip()
    if not text:raise ValueError('请输入时间与数字，或者填写开始时间后输入数字')
    records=[];lines=[x.strip() for x in text.splitlines() if x.strip()]
    dated=bool(re.match(r'^\d{4}-\d{2}-\d{2}',lines[0]))
    if any(lines[0].lower().startswith(h) for h in ('time,value','date,value','时间,数值','时间,数字')):lines=lines[1:];dated=True
    if dated:
        for i,line in enumerate(lines,1):
            m=re.match(r'^(\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?)\s*[,\t，]\s*(.+)$',line)
            if not m:raise ValueError(f'第{i}行格式错误：需要 YYYY-MM-DD HH:mm,数字')
            dt=datetime.fromisoformat(m[1]);v=float(re.split(r'[,\t，]',m[2])[0]);records.append((dt,v))
    else:
        try:start=datetime.fromisoformat(str(payload.get('start','')))
        except ValueError:raise ValueError('仅输入数字时需要开始时间')
        tokens=re.split(r'[,，\s]+',text)
        records=[(start+timedelta(minutes=i*step),float(v)) for i,v in enumerate(tokens)]
    if not records or len(records)>100000:raise ValueError('输入需为1至100000条记录')
    records.sort()
    if len({d for d,_ in records})!=len(records):raise ValueError('时间重复，请先核对')
    for dt,v in records:
        if not math.isfinite(v):raise ValueError('数值必须有限，不能是NaN/Infinity；零值保留')
        if dt.second or dt.microsecond or dt.tzinfo:raise ValueError('时间须精确到分钟，按北京时间填写，不含时区')
        if ((dt-records[0][0]).total_seconds()/60)%step:raise ValueError('时间不符合指定采样间隔')
    known=dict(records);dt=records[0][0];last=records[-1][0];rows=[];observed=[]
    if (last-dt).total_seconds()/(60*step)>100000:raise ValueError('补齐后超过100000条，请缩小范围')
    while dt<=last:
        missing=dt not in known
        if missing:
            if not payload.get('fill_missing',False):raise ValueError(f'{dt:%Y-%m-%d %H:%M}缺失；可启用因果中位数补齐')
            same=[v for t,v in observed if t.hour==dt.hour and t.minute==dt.minute][-7:]
            pool=same or [v for _,v in observed[-168:]]
            if not pool:raise ValueError('缺失前没有可用数值，不能凭空填补')
            value=float(statistics.median(pool))
        else:value=known[dt];observed.append((dt,value))
        rows.append({'time':dt.strftime('%Y-%m-%d %H:%M'),'value':value,'imputed':missing,'calendar':cal.label(dt.date().isoformat())})
        dt+=timedelta(minutes=step)
    return {'rows':rows,'values':[x['value'] for x in rows],'interval_minutes':step,'imputed_count':sum(x['imputed'] for x in rows),'calendar_sha256':cal.sha256,'calendar_version':cal.version,'calendar_snapshot':cal.doc}

def output_times(prepared,horizon):
    last=datetime.fromisoformat(prepared['rows'][-1]['time']);step=prepared['interval_minutes']
    return [(last+timedelta(minutes=step*i)).strftime('%Y-%m-%d %H:%M') for i in range(1,horizon+1)]

def select_device(torch,requested):
    if requested not in ('auto','cpu','gpu'):raise ValueError('设备须为auto/cpu/gpu')
    if requested=='cpu':return 'cpu','用户指定CPU'
    try:
        if not torch.cuda.is_available():raise RuntimeError('CUDA不可用')
        a=torch.ones((32,32),device='cuda');_=a@a;torch.cuda.synchronize();del a
        return 'gpu',torch.cuda.get_device_name(0)
    except Exception as e:
        if requested=='gpu':raise RuntimeError('指定GPU不能运行：'+str(e))
        return 'cpu','GPU不可用，自动使用CPU：'+str(e)

class ModelRuntime:
    def __init__(self):self.model=None;self.key=None;self.last_device=None;self.lock=threading.Lock()
    def forecast(self,prepared,horizon,requested='auto',progress=lambda p,s:None):
        try:return self._forecast(prepared,horizon,requested,progress)
        except RuntimeError as error:
            if requested!='auto' or self.last_device!='gpu' or not any(word in str(error).lower() for word in ['cuda','cublas','out of memory']):raise
            self.model=None;self.key=None
            import gc;gc.collect()
            progress(25,'GPU推理不可用，切换CPU')
            rows,meta=self._forecast(prepared,horizon,'cpu',progress)
            meta['device_reason']='GPU推理失败，自动CPU：'+str(error)
            return rows,meta
    def _forecast(self,prepared,horizon,requested,progress):
        conf=model_config()
        if not 1<=int(horizon)<=conf['horizon_limit']:raise ValueError('预测步数须为1至2048')
        if len(prepared['values'])<2:raise ValueError('至少输入2个时间点；建议不少于32个')
        checkpoint=HOME/'models'/'timesfm-2.0-500m-pytorch'/'torch_model.ckpt'
        if not checkpoint.is_file():raise RuntimeError('尚未下载模型，请运行一键安装，或 setup.ps1 -Task Model')
        try:import torch;import timesfm;import numpy as np
        except ImportError as e:raise RuntimeError('依赖尚未安装，请运行一键安装：'+str(e))
        torch.set_num_threads(max(1,min(8,os.cpu_count() or 1)))
        device,reason=select_device(torch,requested)
        self.last_device=device
        key=(device,conf['context_len'],int(horizon),conf['batch_size'])
        with self.lock:
            if self.key!=key:
                progress(20,'加载TimesFM 2.0模型到'+device.upper())
                self.model=None
                if torch.cuda.is_available():torch.cuda.empty_cache()
                self.model=timesfm.TimesFm(hparams=timesfm.TimesFmHparams(backend=device,context_len=conf['context_len'],horizon_len=int(horizon),per_core_batch_size=conf['batch_size'],input_patch_len=32,output_patch_len=128,num_layers=50,model_dims=1280,use_positional_embedding=False),checkpoint=timesfm.TimesFmCheckpoint(path=str(checkpoint)))
                self.key=key
            progress(55,'正在'+device.upper()+'推理；上下文2048点')
            context=prepared['values'][-conf['context_len']:];started=time.perf_counter()
            with torch.inference_mode():pred,_=self.model.forecast([np.asarray(context,dtype=np.float32)],freq=[0 if prepared['interval_minutes']<=1440 else 1 if prepared['interval_minutes']<=44640 else 2])
            if device=='gpu':torch.cuda.synchronize()
            elapsed=time.perf_counter()-started;values=np.asarray(pred)[0][:int(horizon)].tolist()
            if len(values)!=int(horizon) or not all(math.isfinite(v) for v in values):raise RuntimeError('模型未返回完整有限预测值')
            cal=Calendar(doc=prepared['calendar_snapshot']);rows=[{'time':t,'value':float(v),'calendar':cal.label(t[:10]),'imputed':False} for t,v in zip(output_times(prepared,int(horizon)),values)]
            meta={'model':'TimesFM 2.0 500M','model_id':conf['model_id'],'revision':conf['revision'],'device':device,'device_reason':reason,'torch':torch.__version__,'cuda_runtime':torch.version.cuda,'context_limit':conf['context_len'],'context_used':len(context),'input_rows':len(prepared['values']),'discarded_older_rows':max(0,len(prepared['values'])-len(context)),'horizon':int(horizon),'inference_seconds':round(elapsed,3),'calendar_version':prepared['calendar_version'],'calendar_sha256':prepared['calendar_sha256'],'calendar_features':'annotation_only','imputed_count':prepared['imputed_count']}
            return rows,meta
