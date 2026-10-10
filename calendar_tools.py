"""Official vacation dates, makeup workdays, and auditable yearly maintenance."""
from pathlib import Path
from datetime import date,timedelta,datetime
from html.parser import HTMLParser
import json,re,hashlib,argparse,urllib.request,urllib.parse,shutil

ROOT=Path(__file__).resolve().parent
CALENDAR=ROOT/'calendar'/'holidays.json'
def validate_calendar(doc):
    years=doc.get('covered_years',[])
    if not years or any(type(y)!=int or not 2000<=y<=2100 for y in years):raise ValueError('covered_years须填写已核对年份')
    holidays=doc.get('holidays',{});works=doc.get('workdays',{})
    if not isinstance(holidays,dict) or not isinstance(works,dict):raise ValueError('日历格式错误')
    for d,name in holidays.items():
        if date.fromisoformat(d).year not in years or not isinstance(name,str) or not name.strip():raise ValueError('节假日日期或名称错误')
    for year,ds in works.items():
        if int(year) not in years or not isinstance(ds,list):raise ValueError('补班年份错误')
        for d in ds:
            if date.fromisoformat(d).year!=int(year):raise ValueError('补班日期年份错误')
            if d in holidays:raise ValueError(f'{d}同时被标注放假和补班')
    return doc

class Calendar:
    def __init__(self,path=CALENDAR,doc=None):
        raw=Path(path).read_bytes() if doc is None else json.dumps(doc,ensure_ascii=False,sort_keys=True).encode()
        self.doc=validate_calendar(json.loads(raw))
        self.sha256=hashlib.sha256(raw).hexdigest();self.version=self.doc.get('version','manual')
        self.workdays={d for ds in self.doc['workdays'].values() for d in ds}
    def label(self,day):
        d=date.fromisoformat(str(day)[:10]);key=d.isoformat()
        if d.year not in self.doc['covered_years']:return {'type':'unknown','label':'日历未维护','holiday_name':'','verified':False}
        if key in self.workdays:return {'type':'workday','label':'工作日（补班）','holiday_name':'','verified':True}
        if key in self.doc['holidays']:return {'type':'holiday','label':'节假日 · '+self.doc['holidays'][key],'holiday_name':self.doc['holidays'][key],'verified':True}
        if d.weekday()>=5:return {'type':'weekend','label':'周末','holiday_name':'','verified':True}
        return {'type':'workday','label':'工作日','holiday_name':'','verified':True}

class TextExtractor(HTMLParser):
    def __init__(self):super().__init__();self.parts=[];self.ignore=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.ignore+=1
        elif tag in ('p','div','br','li'):self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.ignore=max(0,self.ignore-1)
    def handle_data(self,data):
        if not self.ignore:self.parts.append(data)

def parse_notice(text,year):
    if '<' in text:
        p=TextExtractor();p.feed(text);text=''.join(p.parts)
    text=re.sub(r'\s+','',text)
    if f'{year}年部分节假日安排' not in text:raise ValueError('通知标题与指定年份不一致')
    sections=list(re.finditer(r'[一二三四五六七八九十]+、(元旦|春节|清明节|劳动节|端午节|中秋节|国庆节)[：:]',text))
    if not sections:raise ValueError('未识别到官方放假段落，不能自动应用')
    holidays={};works=set()
    for i,m in enumerate(sections):
        section=text[m.end():sections[i+1].start() if i+1<len(sections) else len(text)]
        before=section.split('放假',1)[0]
        pat=r'(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日(?:[（(][^）)]*[）)])?(?:至(?:(\d{4})年)?(?:(\d{1,2})月)?(\d{1,2})日)?'
        match=re.search(pat,before)
        if not match:raise ValueError(f'无法解析{m[1]}放假日期')
        sy,sm,sd,ey,em,ed=match.groups();first=date(int(sy or year),int(sm),int(sd));last=date(int(ey or sy or year),int(em or sm),int(ed or sd))
        if last<first or (last-first).days>15:raise ValueError('跨年或异常日期须人工核对')
        if first.year!=year or last.year!=year:raise ValueError('跨年放假日期须单独人工合并')
        count=re.search(r'共(\d+)天',section)
        if count and int(count[1])!=(last-first).days+1:raise ValueError('识别的放假天数不符合原文')
        for n in range((last-first).days+1):holidays[(first+timedelta(days=n)).isoformat()]=m[1]
        for chunk in re.findall(r'[^。；]+上班',section):
            for y,mo,da in re.findall(r'(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日',chunk):works.add(date(int(y or year),int(mo),int(da)).isoformat())
    return validate_calendar({'version':f'official-{year}-candidate','covered_years':[year],'holidays':holidays,'workdays':{str(year):sorted(works)}})

def main():
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='op',required=True)
    d=s.add_parser('download');d.add_argument('--year',type=int,required=True);d.add_argument('--url',required=True)
    a=s.add_parser('apply');a.add_argument('--candidate',required=True);a.add_argument('--confirmed',action='store_true')
    v=p.parse_args();dest=ROOT/'calendar'/'维护记录';dest.mkdir(parents=True,exist_ok=True)
    if v.op=='download':
        url=urllib.parse.urlparse(v.url)
        if url.scheme!='https' or not (url.hostname=='gov.cn' or str(url.hostname).endswith('.gov.cn')):raise ValueError('仅接收HTTPS政府网站通知')
        with urllib.request.urlopen(v.url,timeout=45) as response:
            host=urllib.parse.urlparse(response.url).hostname
            if not (host=='gov.cn' or str(host).endswith('.gov.cn')):raise ValueError('通知跳转到非政府网站')
            raw=response.read(5_000_000)
        text=raw.decode('utf-8');candidate=parse_notice(text,v.year)
        candidate['source']={'url':v.url,'html_sha256':hashlib.sha256(raw).hexdigest(),'downloaded_at':datetime.now().astimezone().isoformat(),'status':'待人工核对'}
        (dest/f'{v.year}_官方通知.html').write_bytes(raw)
        path=dest/f'{v.year}_候选日历.json';path.write_text(json.dumps(candidate,ensure_ascii=False,indent=2),encoding='utf8');print('请核对候选后再apply：',path)
    else:
        if not v.confirmed:raise ValueError('核对原文后须加 --confirmed 才会应用')
        candidate=validate_calendar(json.loads(Path(v.candidate).read_text(encoding='utf8')))
        if set(candidate['holidays'].values())!={'元旦','春节','清明节','劳动节','端午节','中秋节','国庆节'}:raise ValueError('候选未覆盖全部7类节假日，须人工补全')
        old=validate_calendar(json.loads(CALENDAR.read_text(encoding='utf8')));years=set(candidate['covered_years'])
        old['holidays']={d:n for d,n in old['holidays'].items() if date.fromisoformat(d).year not in years};old['holidays'].update(candidate['holidays'])
        old['workdays'].update(candidate['workdays']);old['covered_years']=sorted(set(old['covered_years'])|years)
        old['version']='calendar-'+datetime.now().strftime('%Y%m%d%H%M%S');old.setdefault('year_sources',{}).update({str(y):candidate.get('source',{'status':'人工确认'}) for y in years})
        validate_calendar(old);shutil.copy2(CALENDAR,dest/(old['version']+'_旧日历.json'))
        temp=CALENDAR.with_suffix('.tmp');temp.write_text(json.dumps(old,ensure_ascii=False,indent=2),encoding='utf8');temp.replace(CALENDAR);print('日历已应用，重启轻量工具生效')

if __name__=='__main__':main()
