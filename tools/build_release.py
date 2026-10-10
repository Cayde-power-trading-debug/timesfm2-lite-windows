"""Build a weights-free portable release from this repository."""
import argparse,hashlib,json,re,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
VERSION='1.0.0'
EXCLUDE={'.git','__pycache__','runtime','models','下载缓存','输入与输出','dist','.venv'}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'dist')
    args=parser.parse_args()
    out=args.output.resolve()
    if out==ROOT:raise ValueError('Output must not be the repository root')
    files=[]
    for path in ROOT.rglob('*'):
        if not path.is_file() or any(part in EXCLUDE for part in path.relative_to(ROOT).parts):continue
        if path==out or out in path.parents:continue
        rel=path.relative_to(ROOT)
        if path.suffix in ('.pyc','.log') or path.name in ('本地服务.json','环境检测.json','真实预测自检.json','已安装依赖锁定.txt'):continue
        if path.suffix.lower() in ('.ckpt','.safetensors','.pt','.pth','.db','.sqlite','.sqlite3','.xlsx'):
            raise ValueError(f'Model, runtime or business data must not be published: {rel}')
        if path.name=='.env' or path.name.startswith('.env.'):raise ValueError(f'Environment secrets excluded: {rel}')
        if 'vendor' not in rel.parts:
            text=path.read_bytes()
            for pattern in (rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',rb'gh[pousr]_[A-Za-z0-9]{20,}',rb'github_pat_[A-Za-z0-9_]{20,}',rb'AKIA[A-Z0-9]{16}'):
                if re.search(pattern,text):raise ValueError(f'Potential credential requires review: {rel}')
        files.append((path,rel.as_posix()))
    integrity=json.loads((ROOT/'vendor/integrity.json').read_text(encoding='utf-8'))
    for name,key in [('python-3.11.9-embed-amd64.zip','python_zip_sha256'),('get-pip.py','get_pip_sha256')]:
        if hashlib.sha256((ROOT/'vendor'/name).read_bytes()).hexdigest()!=integrity[key]:raise ValueError(f'Bundled integrity mismatch: {name}')
    manifest={'version':VERSION,'model_weights_included':False,'files':[{'path':rel,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()} for path,rel in sorted(files,key=lambda pair:pair[1])]}
    out.mkdir(parents=True,exist_ok=True)
    archive=out/f'timesfm2-lite-windows-v{VERSION}.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for path,rel in files:z.write(path,f'timesfm2-lite-windows/{rel}')
        z.writestr('timesfm2-lite-windows/发布清单.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    (out/'SHA256SUMS.txt').write_text(f'{digest}  {archive.name}\n',encoding='ascii')
    print(json.dumps({'archive':str(archive),'bytes':archive.stat().st_size,'files':len(files),'sha256':digest,'model_weights_included':False},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
