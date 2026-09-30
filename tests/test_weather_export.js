// Exercise exported rows, rather than matching UI implementation strings.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const script=fs.readFileSync(path.join(__dirname,'../tools/orchard_monthly_report.js'),'utf8');
const start=script.indexOf('function weatherCsv(');
const end=script.indexOf('downloadWeather.onclick',start);
const exportCsv=new Function('chartMetrics',script.slice(start,end)+'; return weatherCsv;')({T2M:[],PRECTOTCORR:[]});

function fixture(){return {
  a:{code:'84',label:'สวน, "A"',lat:9.1,lon:99.2},b:{code:'86',label:'B',lat:10.4,lon:99.3},
  resultA:{rows:[{date:'2025-07-01',T2M:null,PRECTOTCORR:0}],dataLat:9.01557,dataLon:99.113,basis:'province_proxy',timeStandard:'LST',source:'สำรอง',sourceUrl:'https://power.larc.nasa.gov/',retrievedUtc:'',warning:'จุดอ้างอิงจังหวัด'},
  resultB:{rows:[{date:'2025-07-01',T2M:27,PRECTOTCORR:1}],dataLat:10.4,dataLon:99.3,basis:'selected_point',timeStandard:'LST',source:'API',sourceUrl:'https://power.larc.nasa.gov/',retrievedUtc:'2026-09-30',warning:null}
};}
test('CSV preserves missing values, measured zero, quoting and distinct source coordinates',()=>{
  const csv=exportCsv(fixture()),rows=csv.slice(1).split('\r\n');
  assert.equal(csv[0],'\ufeff');assert.equal(rows.length,3);
  assert.match(rows[0],/"selected_latitude","selected_longitude","data_latitude","data_longitude"/);
  assert.match(rows[1],/"สวน, ""A"""/);
  assert.match(rows[1],/"9.1","99.2","9.01557","99.113"/);
  assert.match(rows[1],/"2025-07-01","","0"/);
  assert.match(rows[1],/"province_proxy"/);assert.match(rows[2],/"selected_point"/);
});
test('A-only download contains no fabricated B records',()=>{
  const data=fixture();data.b=null;data.resultB=null;
  assert.equal(exportCsv(data).split('\r\n').length,2);
});
