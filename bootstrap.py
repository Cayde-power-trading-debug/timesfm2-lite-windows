"""Download pinned official weights and verify the real runtime; never ship weights."""
import argparse,json,hashlib,sys,time,os
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))

def download_model(home):
    from huggingface_hub import HfApi,hf_hub_download
    conf=json.loads((ROOT/'config'/'model.json').read_text(encoding='utf8'))
    dest=Path(home)/'models'/'timesfm-2.0-500m-pytorch';dest.mkdir(parents=True,exist_ok=True)
    info=HfApi().model_info(conf['model_id'],revision=conf['revision'],files_metadata=True,token=False)
    item=next(x for x in info.siblings if x.rfilename=='torch_model.ckpt');expected=item.lfs.sha256
    for filename in ['config.json','README.md','torch_model.ckpt']:
        print('Downloading official model file:',filename,flush=True)
        hf_hub_download(repo_id=conf['model_id'],filename=filename,revision=conf['revision'],local_dir=dest,token=False)
    digest=hashlib.sha256()
    with (dest/'torch_model.ckpt').open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''):digest.update(chunk)
    if digest.hexdigest()!=expected:raise RuntimeError('官方checkpoint校验失败，请重新下载')
    manifest={'model_id':conf['model_id'],'revision':conf['revision'],'checkpoint_sha256':digest.hexdigest(),'bytes':(dest/'torch_model.ckpt').stat().st_size,'source':'Hugging Face official Google repo; pinned revision','downloaded_at':time.strftime('%Y-%m-%d %H:%M:%S')}
    (dest/'下载校验.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(manifest,ensure_ascii=False),flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['model','check','smoke','configure']);p.add_argument('--home',default=str(ROOT));p.add_argument('--device',default='auto',choices=['auto','cpu','gpu']);v=p.parse_args()
    os.environ['NOVA_LITE_HOME']=str(Path(v.home).resolve())
    os.environ['HF_HOME']=str(Path(v.home)/'下载缓存'/'huggingface');os.environ['HF_HUB_DISABLE_TELEMETRY']='1';os.environ['HF_HUB_DISABLE_XET']='1'
    if v.stage=='model':download_model(v.home);return
    if v.stage=='configure':
        path=ROOT/'config'/'model.json';conf=json.loads(path.read_text(encoding='utf8'));conf.update(context_len=2048,batch_size=1,device=v.device);path.write_text(json.dumps(conf,ensure_ascii=False,indent=2),encoding='utf8');print('Configured maximum trained context:2048, batch:1, device:'+v.device);return
    from core import select_device,prepare_input,ModelRuntime,model_config
    import torch,importlib.metadata
    device,reason=select_device(torch,v.device)
    summary={'python':sys.version.split()[0],'torch':torch.__version__,'timesfm':importlib.metadata.version('timesfm'),'cuda_runtime':torch.version.cuda,'device':device,'reason':reason,'context_len':model_config()['context_len'],'weights_exist':(Path(v.home)/'models'/'timesfm-2.0-500m-pytorch'/'torch_model.ckpt').is_file()}
    if v.stage=='smoke':
        import math
        data='\n'.join(str(100+20*math.sin(i*math.pi/12)) for i in range(2048))
        prepared=prepare_input({'text':data,'start':'2026-07-01T00:00','interval_minutes':60})
        rows,meta=ModelRuntime().forecast(prepared,24,requested=v.device,progress=lambda p,s:print(p,s,flush=True));summary['prediction']=meta;summary['prediction_rows']=len(rows)
    Path(v.home).mkdir(parents=True,exist_ok=True);(Path(v.home)/('真实预测自检.json' if v.stage=='smoke' else '环境检测.json')).write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
