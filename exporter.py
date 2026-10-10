from pathlib import Path
from datetime import datetime
import json,html,csv,hashlib
from urllib.parse import quote

def render_report(title,rows,meta):
    escape=lambda v:html.escape(str(v),quote=True)
    body=''.join('<tr><td>'+escape(x['time'])+'</td><td>'+escape(round(x['value'],6))+'</td><td>'+escape(x['calendar']['label'])+'</td><td>'+('因果中位数补齐' if x.get('imputed') else '原始输入/模型输出')+'</td></tr>' for x in rows)
    values=[x['value'] for x in rows];n=len(values);mn=min(values or [0]);mx=max(values or [1]);span=mx-mn or 1
    coords=' '.join(f'{20+i*960/max(1,n-1):.2f},{230-(v-mn)*200/span:.2f}' for i,v in enumerate(values))
    details=''.join('<dt>'+escape(k)+'</dt><dd>'+escape(v)+'</dd>' for k,v in meta.items())
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+escape(title)+'</title><style>body{font:15px system-ui;color:#172d44;background:#f3f6fa;margin:0;padding:32px}main{max-width:1100px;margin:auto;background:white;padding:28px;border-radius:16px}h1{font-size:24px}svg{width:100%;background:#f6f9fc}table{width:100%;border-collapse:collapse}td,th{padding:10px;text-align:left;border-bottom:1px solid #dae4ee}dt{font-weight:600;float:left;width:210px}dd{overflow-wrap:anywhere;margin-left:220px}.note{color:#677b8e}</style><main><h1>'+escape(title)+'</h1><p class="note">日历标签仅用于标注；未对TimesFM加入节假日修正。未知年份显示“日历未维护”。</p><svg viewBox="0 0 1000 250"><polyline fill="none" stroke="#2374de" stroke-width="2" points="'+coords+'"/></svg><details><summary>运行与复现参数</summary><dl>'+details+'</dl></details><table><thead><tr><th>北京时间</th><th>数值</th><th>日期标签</th><th>来源</th></tr></thead><tbody>'+body+'</tbody></table></main></html>'

def save_run(home,prepared,predictions,meta,run_id):
    dest=Path(home)/'输入与输出'/run_id;dest.mkdir(parents=True,exist_ok=False)
    raw=json.dumps({'input':prepared,'output':predictions,'meta':meta},ensure_ascii=False,indent=2,allow_nan=False)
    (dest/'复现.json').write_text(raw,encoding='utf8')
    input_file=dest/'输入.html';out_file=dest/'预测结果.html'
    input_file.write_text(render_report('TimesFM 2.0 · 输入',prepared['rows'],meta),encoding='utf8');out_file.write_text(render_report('TimesFM 2.0 · 预测结果',predictions,meta),encoding='utf8')
    for name,rows in [('输入.csv',prepared['rows']),('预测.csv',predictions)]:
        with (dest/name).open('w',newline='',encoding='utf-8-sig') as f:
            writer=csv.writer(f);writer.writerow(['时间','数值','日期标签','补齐']);writer.writerows([x['time'],x['value'],x['calendar']['label'],x.get('imputed',False)] for x in rows)
    (dest/'校验.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in dest.iterdir() if p.is_file()},ensure_ascii=False,indent=2),encoding='utf8')
    return {'run_id':run_id,'directory':str(dest),'input_url':f'/runs/{run_id}/'+quote('输入.html'),'output_url':f'/runs/{run_id}/'+quote('预测结果.html')}
