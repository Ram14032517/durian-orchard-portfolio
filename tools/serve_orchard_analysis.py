"""Local-only map server with cached NASA POWER daily point requests."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse,parse_qs
from pathlib import Path
from datetime import date,datetime,timezone,timedelta
import json,hashlib,threading,csv,io
import requests
ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'research_data/five_province_history/point_weather_cache'
EXPORTS=ROOT/'research_data/five_province_history/exports'
LOCK=threading.Lock()
PARAMS='T2M,T2M_MAX,T2M_MIN,RH2M,PRECTOTCORR,ALLSKY_SFC_SW_DWN,WS2M'

def verified_cache(path):
    """Read a cache entry only if the recorded bytes and structure still agree."""
    try:
        raw=path.read_bytes()
        meta=json.loads(path.with_suffix('.source.json').read_text(encoding='utf-8'))
        if hashlib.sha256(raw).hexdigest()!=meta['sha256']:return None
        data=json.loads(raw)
        if not data.get('properties',{}).get('parameter'):return None
        return data,meta
    except (OSError,ValueError,KeyError,TypeError,AttributeError):
        return None

def cache_is_fresh(path, end, today=None, now=None):
    """Refresh recent periods every 6h; older periods every 30d for revisions."""
    today=today or date.today()
    now=now or datetime.now(timezone.utc)
    ttl=21600 if end>=today-timedelta(days=31) else 30*86400
    try:
        cached=verified_cache(path)
        if cached is None:return False
        _,meta=cached
        age=(now-datetime.fromisoformat(meta['retrieved_utc'])).total_seconds()
        return 0<=age<ttl
    except (OSError,ValueError,KeyError,TypeError):
        return False

def daily_rows(data,start,end):
    """Preserve all requested days and parameter missingness, including zero rain."""
    p=data['properties']['parameter'];fill=data.get('header',{}).get('fill_value',-999)
    rows=[]
    for i in range((end-start).days+1):
        day=start+timedelta(days=i);key=day.strftime('%Y%m%d')
        row={'date':day.isoformat()}
        for k in PARAMS.split(','):
            v=p.get(k,{}).get(key)
            row[k]=None if v is None or v in (fill,-999) else v
        rows.append(row)
    return rows

def save_weather_export(payload):
    """Save the displayed snapshot locally, with a server-controlled filename."""
    start=date.fromisoformat(payload['start']);end=date.fromisoformat(payload['end'])
    if not date(1981,1,1)<=start<=end<=date.today() or (end-start).days>731:
        raise ValueError('ช่วงวันที่ส่งออกไม่ถูกต้อง')
    text=payload['csv']
    if not isinstance(text,str) or len(text.encode('utf-8'))>2_000_000:
        raise ValueError('ไฟล์ส่งออกต้องไม่เกิน 2 MB')
    reader=csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    required={'area','province_code','date','selected_latitude','selected_longitude','data_latitude','data_longitude','source_basis','time_standard'}
    if not required.issubset(reader.fieldnames or []):raise ValueError('คอลัมน์ส่งออกไม่ครบ')
    count=0
    for row in reader:
        if row['area'] not in ('A','B') or not start<=date.fromisoformat(row['date'])<=end:
            raise ValueError('แถวส่งออกอยู่นอกพื้นที่หรือวันที่เลือก')
        count+=1
    if not 1<=count<=1464:raise ValueError('จำนวนแถวส่งออกไม่ถูกต้อง')
    raw=text.encode('utf-8');digest=hashlib.sha256(raw).hexdigest()
    filename=f'weather_AB_{start}_{end}_{digest[:12]}.csv'
    EXPORTS.mkdir(parents=True,exist_ok=True);path=EXPORTS/filename
    try:
        with path.open('xb') as f:f.write(raw)
    except FileExistsError:
        if path.read_bytes()!=raw:raise ValueError('ชื่อไฟล์ซ้ำกับข้อมูลอื่น')
    return {'url':f'/research_data/five_province_history/exports/{filename}',
            'filename':filename,'rows':count,'sha256':digest,
            'folder':'research_data/five_province_history/exports'}

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT),**kwargs)
    def send_head(self):
        # Do not expose .git, .secrets, source files, or directory listings.
        path=Path(self.translate_path(self.path)).resolve()
        roots=[ROOT/'research_data'/p for p in ('five_province_history','priority_provinces','thailand_comparison','regional_orchards')]
        regional_bundle=ROOT/'research_data/five_province_history/training/training_bundle.zip'
        if (not any(path.is_relative_to(p.resolve()) for p in roots) or not path.is_file()
            or any(p.startswith('.') for p in path.relative_to(ROOT).parts) or 'point_weather_cache' in path.parts
            or (path.suffix.lower() not in {'.html','.js','.css','.json','.geojson','.csv','.md','.ipynb','.png','.svg','.jpg'}
                and path != regional_bundle)):
            self.send_error(404);return None
        return super().send_head()
    def do_GET(self):
        parsed=urlparse(self.path)
        if parsed.path!='/api/weather':return super().do_GET()
        try:
            q=parse_qs(parsed.query);lat=round(float(q['lat'][0]),5);lon=round(float(q['lon'][0]),5)
            start=date.fromisoformat(q['start'][0]);end=date.fromisoformat(q['end'][0])
            if not (5<=lat<=21 and 97<=lon<=106 and date(1981,1,1)<=start<=end<=date.today() and (end-start).days<=731):
                raise ValueError('เลือกพิกัดประเทศไทยและช่วงเวลาไม่เกินสองปี ตั้งแต่ปี 1981 ถึงปัจจุบัน')
            args=dict(parameters=PARAMS,community='AG',latitude=lat,longitude=lon,start=start.strftime('%Y%m%d'),end=end.strftime('%Y%m%d'),format='JSON',**{'time-standard':'LST'})
            key=hashlib.sha256(json.dumps(args,sort_keys=True).encode()).hexdigest()
            CACHE.mkdir(parents=True,exist_ok=True);path=CACHE/f'{key}.json'
            with LOCK:
                cached=verified_cache(path)
                stale=False
                if cached and cache_is_fresh(path,end):data,provenance=cached
                else:
                    try:
                        r=requests.get('https://power.larc.nasa.gov/api/temporal/daily/point',params=args,timeout=120);r.raise_for_status();data=r.json()
                        if not data.get('properties',{}).get('parameter'):raise RuntimeError('NASA response has no daily data')
                        provenance=dict(url=r.url,retrieved_utc=datetime.now(timezone.utc).isoformat(),sha256=hashlib.sha256(r.content).hexdigest())
                        path.write_bytes(r.content)
                        path.with_suffix('.source.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
                    except (requests.RequestException,ValueError,RuntimeError):
                        if not cached:raise
                        data,provenance=cached
                        stale=True
            rows=daily_rows(data,start,end)
            payload=dict(rows=rows,latitude=lat,longitude=lon,time_standard='LST',source='NASA POWER daily point; grid-based, not orchard sensor',cache_key=key,stale_cache=stale)
            payload['coverage']={k:{'valid_days':sum(r[k] is not None for r in rows),'requested_days':len(rows)} for k in PARAMS.split(',')}
            payload['provenance']=provenance
            self.send_json(200,payload)
        except (ValueError,KeyError) as e:self.send_json(400,{'error':str(e)})
        except Exception as e:self.send_json(502,{'error':str(e)})
    def do_POST(self):
        if urlparse(self.path).path!='/api/weather-export':self.send_error(404);return
        origin=self.headers.get('Origin')
        port=self.server.server_port
        if origin and origin not in (f'http://127.0.0.1:{port}',f'http://localhost:{port}'):
            self.send_json(403,{'error':'บันทึกได้จากหน้าโครงการในเครื่องเท่านั้น'});return
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=2_100_000:raise ValueError('ขนาดคำขอไม่ถูกต้อง')
            if 'application/json' not in self.headers.get('Content-Type',''):
                raise ValueError('ต้องส่งข้อมูล JSON')
            payload=json.loads(self.rfile.read(size))
            self.send_json(200,save_weather_export(payload))
        except (ValueError,KeyError,TypeError) as e:self.send_json(400,{'error':str(e)})
        except OSError:self.send_json(500,{'error':'บันทึกไฟล์ในเครื่องไม่สำเร็จ ตรวจสิทธิ์โฟลเดอร์ exports'})
    def send_json(self,status,payload):
        body=json.dumps(payload,ensure_ascii=False,allow_nan=False).encode()
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
if __name__=='__main__':
    print('http://127.0.0.1:8871/research_data/five_province_history/UNIFIED_MAP.html',flush=True)
    ThreadingHTTPServer(('127.0.0.1',8871),Handler).serve_forever()
