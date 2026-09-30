// Monthly regional context and dated evidence stay separate from live point weather.
const reportMonths=['มกราคม','กุมภาพันธ์','มีนาคม','เมษายน','พฤษภาคม','มิถุนายน','กรกฎาคม','สิงหาคม','กันยายน','ตุลาคม','พฤศจิกายน','ธันวาคม'];
const reportShort=['ม.ค.','ก.พ.','มี.ค.','เม.ย.','พ.ค.','มิ.ย.','ก.ค.','ส.ค.','ก.ย.','ต.ค.','พ.ย.','ธ.ค.'];
let reportYear=2025,reportMonth=7;
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function regionFor(code){return Object.values(DATA.phenology.regions).find(r=>r.provinces.includes(code));}
function stagesFor(code,month){return regionFor(code).periods.filter(p=>p.months.includes(month));}
function stageChips(code,month){return stagesFor(code,month).map(p=>`<span class="stage-chip stage-${p.stage}">${esc(DATA.phenology.stages[p.stage].short)}</span>`).join('');}
function monthWeather(code){return DATA.monthly_weather.find(r=>r.province_code===code&&r.year_ce===reportYear&&r.month===reportMonth);}
function monthHarvest(code){return DATA.harvest.find(r=>r.province_code===code&&r.year_ce===reportYear&&r.month_number===reportMonth);}
function selectReportMonth(month){
  reportMonth=month;
  const ym=`${reportYear}-${String(month).padStart(2,'0')}`;
  $('month').value=ym;$('start').value=ym+'-01';$('end').value=new Date(Date.UTC(reportYear,month,0)).toISOString().slice(0,10);
  invalidateWeather('เลือกเดือนรายงานแล้ว: ตารางด้านบนใช้จุดอ้างอิงจังหวัด หากต้องการอากาศจุด A/B ให้กดดูอากาศด้านล่าง');
  context();
}
function renderMonthlyReport(){
  if(!A)return;
  const code=A.code,name=DATA.provinces.find(p=>p.province_code===code).province_name;
  $('report-province').value=code;
  $('month-buttons').innerHTML=reportShort.map((m,i)=>`<button class="month-card" data-month="${i+1}" aria-pressed="${reportMonth===i+1}" aria-label="รายงาน${reportMonths[i]} ${reportYear+543}"><strong>${m}</strong><small>${stagesFor(code,i+1).map(p=>esc(DATA.phenology.stages[p.stage].short)).join(' · ')}</small></button>`).join('');
  $('month-buttons').querySelectorAll('[data-month]').forEach(b=>b.onclick=()=>selectReportMonth(+b.dataset.month));
  $('report-title').textContent=`${name} · ${reportMonths[reportMonth-1]} ${reportYear+543}`;
  $('view-summary').textContent=`รายงาน: ${name} · ${reportMonths[reportMonth-1]} ${reportYear+543} | จุด A: ${A.label}${B?' | จุด B: '+B.label:''}`;
  const region=regionFor(code),source=DATA.phenology.calendar_source;
  $('report-stage').innerHTML=stageChips(code,reportMonth)+`<p class="scope-note">กรอบฤดูทั่วไป: ${esc(region.label)} · หมอนทองในฤดู ไม่ใช่ระยะยืนยันของจุด A หรือของปี ${reportYear+543}</p>`+
    stagesFor(code,reportMonth).map(p=>`<p><b>${esc(DATA.phenology.stages[p.stage].label)} (${esc(p.range)})</b><br>${esc(DATA.phenology.stages[p.stage].description)}</p>`).join('')+
    (region.note?`<p class="warn">${esc(region.note)}</p>`:'')+
    `<p class="scope-note"><a href="${esc(source.url)}" target="_blank" rel="noopener">${esc(source.title)}</a> · ${esc(source.locator)}</p>`;
  const w=monthWeather(code),h=monthHarvest(code),point=DATA.provinces.find(p=>p.province_code===code);
  const stats=[['ผลผลิตที่รายงาน',h?fmt(h.tonnes,0)+' ตัน':'ไม่มีระเบียน','สศก. ทั้งจังหวัด ทุกพันธุ์'],
    ['อุณหภูมิเฉลี่ย',w?fmt(w.temperature_c)+' °C':'—',w?`มีค่า ${w.days_temperature}/${w.expected_days} วัน`:'ไม่มีข้อมูลเดือนนี้'],
    ['ฝนรวม',w?fmt(w.rain_mm,2)+' มม.':'—',w?`มีค่า ${w.days_rain}/${w.expected_days} วัน`:'ไม่มีข้อมูลเดือนนี้'],
    ['ความชื้นอากาศ',w?fmt(w.humidity_pct)+' %':'—','เฉลี่ยวันที่มีค่า'],
    ['รังสีดวงอาทิตย์',w?fmt(w.solar_mj_m2_day,2):'—','MJ/m²/วัน; เฉลี่ยวันที่มีค่า'],
    ['ต่างจากเดือนเดียวกัน 1991–2020',w?fmt(w.temperature_anomaly_c)+' °C':'—','อุณหภูมิเฉลี่ย ไม่ใช่ผลต่อผลผลิต']];
  $('report-metrics').innerHTML=stats.map(([label,value,note])=>`<div class="report-stat">${esc(label)}<strong>${esc(value)}</strong><small>${esc(note)}</small></div>`).join('');
  $('report-weather-note').innerHTML=`อากาศ <a href="https://power.larc.nasa.gov/docs/services/api/temporal/daily/" target="_blank" rel="noopener">NASA POWER</a> ณ จุดอ้างอิงจังหวัด ${point.weather_latitude}, ${point.weather_longitude} ไม่ใช่ค่าเฉลี่ยทั้งจังหวัดหรืออากาศที่ polygon ดิน/อำเภอที่เลือก วันแบบ LST; เดือนที่ข้อมูลไม่ครบใช้เฉพาะวันที่มีค่า ผลผลิตจาก <a href="https://catalog.oae.go.th/dataset/durian_product_month" target="_blank" rel="noopener">สศก.</a> ไม่ยืนยันเหตุและผลจากอากาศ`;
  const events=DATA.phenology.events.filter(e=>e.province_code===code&&e.year===reportYear&&e.months.includes(reportMonth));
  $('report-events').innerHTML=events.length?events.map(e=>`<article class="evidence-item"><small>${esc(e.kind)} · ${esc(e.district||'ระดับจังหวัด')}</small><p><a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.title)}</a></p><p>${esc(e.summary)}</p><small>วันเหตุ/วันกำหนด: ${esc(e.event_date||'ไม่ระบุ')} · เผยแพร่: ${esc(e.published_date||'ไม่ระบุวันแน่นอน')} · ตรวจแหล่ง ${DATA.phenology.reviewed_on}</small></article>`).join(''):'<p class="scope-note">ยังไม่มีรายงานที่ตรวจยืนยันสำหรับจังหวัดและเดือน–ปีนี้ในฐาน ไม่ได้หมายความว่าไม่มีเหตุการณ์เกิดขึ้น และไม่ดึงข่าวปีอื่นมาแทน</p>';
  $('report-questions').innerHTML=stagesFor(code,reportMonth).map(p=>`<li>${esc(DATA.phenology.stages[p.stage].check)}</li>`).join('');
  $('report-compare').innerHTML=table(['จังหวัด','กรอบระยะทั่วไป','เฉลี่ย °C','ฝนรวม มม.','ตัน/เดือน'],DATA.provinces.map(p=>{const v=monthWeather(p.province_code),o=monthHarvest(p.province_code);return [`<button data-compare-province="${p.province_code}">${esc(p.province_name)}</button>`,stageChips(p.province_code,reportMonth),v?fmt(v.temperature_c):'—',v?fmt(v.rain_mm,2):'—',o?fmt(o.tonnes,0):'—'];}));
  $('report-compare').querySelectorAll('[data-compare-province]').forEach(b=>b.onclick=()=>{$('province').value=b.dataset.compareProvince;provinceChange();});
}
DATA.provinces.forEach(p=>$('report-province').add(new Option(p.province_name,p.province_code)));
for(let y=2026;y>=1981;y--)$('report-year').add(new Option(y+543,y));
$('report-year').value=reportYear;
$('report-year').onchange=()=>{reportYear=+$('report-year').value;selectReportMonth(reportMonth);};
$('report-province').onchange=()=>{$('province').value=$('report-province').value;provinceChange();};
// Existing area selection remains the single source of province state.
const contextBeforeMonthlyReport=context;
context=()=>{
  const end=$('end').value;if(end){reportYear=Number(end.slice(0,4));reportMonth=Number(end.slice(5,7));$('report-year').value=String(reportYear);}
  contextBeforeMonthlyReport();renderMonthlyReport();
};
// Keep the monthly report readable; preserve existing tools as expandable detail.
document.querySelectorAll('aside > section:not(.monthly-report)').forEach(section=>{
  const heading=section.querySelector('h2');if(!heading)return;
  if(section.querySelector('#district'))section.id='area-section';
  if(section.querySelector('#load'))section.id='weather-section';
  if(section.querySelector('#yield'))section.id='yield-section';
  const details=document.createElement('details'),summary=document.createElement('summary');
  summary.textContent=section.querySelector('#events')?'คลังลิงก์ประกอบเดิม (ไม่กรองเดือน/ปี)':heading.textContent;details.append(summary);heading.remove();
  if(section.id==='area-section')summary.textContent='พื้นที่และชุดดิน';
  if(section.id==='weather-section')summary.textContent='กราฟเปรียบเทียบอากาศ A/B';
  if(section.id==='yield-section')summary.textContent='ผลผลิตและผลทดลองโมเดล';
  if(section.id==='training-section')summary.textContent='ดาวน์โหลดข้อมูลสำหรับวิเคราะห์ / เทรน';
  while(section.firstChild)details.append(section.firstChild);
  section.append(details);
});
document.querySelector('.monthly-report').id='report-section';
document.querySelectorAll('.quick-nav a').forEach(link=>link.onclick=event=>{
  event.preventDefault();const target=document.querySelector(link.getAttribute('href'));
  const detail=target.querySelector(':scope > details');if(detail)detail.open=true;
  target.scrollIntoView({behavior:'auto',block:'start'});
});
// Hide supporting records until needed; headline values remain visible.
for(const [id,title] of [['report-events','รายงานเหตุการณ์ตรงเดือน–ปี'],['report-compare','เทียบทั้ง 5 จังหวัดในเดือนเดียวกัน']]){
  const node=$(id),heading=node.previousElementSibling;
  const detail=document.createElement('details'),summary=document.createElement('summary');summary.textContent=title;
  node.before(detail);detail.append(summary,node);if(heading?.tagName==='H3')heading.remove();
}
const graphButton=document.createElement('button');graphButton.type='button';graphButton.textContent='ดูกราฟอากาศเดือนนี้';
graphButton.onclick=()=>{selectReportMonth(reportMonth);const section=$('weather-section');section.querySelector('details').open=true;section.scrollIntoView({behavior:'auto',block:'start'});loadWeather();};
document.querySelector('.report-controls').append(graphButton);
const clearB=document.createElement('button');clearB.type='button';clearB.textContent='ล้างพื้นที่ B';
clearB.onclick=()=>{B=null;if(markerB){map.removeLayer(markerB);markerB=null;}$('compare-point').textContent='ยังไม่ได้เลือกพื้นที่ B';invalidateWeather('ล้างพื้นที่ B แล้ว กดดูอากาศเพื่อดู A');context();};
$('pin-b').after(clearB);
const downloadWeather=document.createElement('button');downloadWeather.id='download-weather';downloadWeather.type='button';downloadWeather.disabled=true;downloadWeather.textContent='ดาวน์โหลดอากาศ A/B เป็น CSV';
$('chart').after(downloadWeather);
$('weather').before($('chart-metric').closest('label'),$('chart-note'),$('chart'),downloadWeather);
const exportMessage=document.createElement('p');exportMessage.id='export-message';exportMessage.className='scope-note';exportMessage.setAttribute('role','status');downloadWeather.after(exportMessage);
function weatherCsv(snapshot){
  const metrics=Object.keys(chartMetrics),headers=['area','province_code','location_label','selected_latitude','selected_longitude','data_latitude','data_longitude','date',...metrics,'time_standard','source_basis','source_label','source_url','retrieved_utc','warning'];
  const quote=value=>'"'+String(value??'').replace(/"/g,'""')+'"';
  const records=[[snapshot.resultA,snapshot.a,'A'],[snapshot.resultB,snapshot.b,'B']].flatMap(([result,point,area])=>!result||!point?[]:result.rows.map(row=>[area,point.code,point.label,point.lat,point.lon,result.dataLat,result.dataLon,row.date,...metrics.map(key=>row[key]),result.timeStandard,result.basis,result.source,result.sourceUrl,result.retrievedUtc,result.warning]));
  return '\ufeff'+[headers,...records].map(row=>row.map(quote).join(',')).join('\r\n');
}
downloadWeather.onclick=async()=>{
  if(!weatherExportState)return;
  const snapshot=weatherExportState,content=weatherCsv(snapshot);downloadWeather.disabled=true;exportMessage.textContent='กำลังบันทึก CSV ในเครื่อง…';
  try{
    const response=await fetch('/api/weather-export',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({start:snapshot.start,end:snapshot.end,csv:content})});
    if(!(response.headers.get('content-type')||'').includes('application/json'))throw Error('ต้องเปิดผ่านเซิร์ฟเวอร์โครงการรุ่นล่าสุด');
    const result=await response.json();if(!response.ok)throw Error(result.error||`HTTP ${response.status}`);
    if(weatherExportState!==snapshot)return;
    exportMessage.textContent=`บันทึก ${result.rows} แถว (${snapshot.start} ถึง ${snapshot.end}) ใน ${result.folder}/ แล้ว • `;
    const link=document.createElement('a');link.href=result.url;link.download=result.filename;link.textContent='เปิด / ดาวน์โหลด CSV';exportMessage.append(link);
  }catch(error){
    exportMessage.textContent='บันทึกในเครื่องไม่ได้: '+error.message+' • ';
    const url=URL.createObjectURL(new Blob([content],{type:'text/csv;charset=utf-8'})),link=document.createElement('a');link.href=url;link.download=`weather_AB_${snapshot.start}_${snapshot.end}.csv`;link.textContent='ลองดาวน์โหลดผ่านเบราว์เซอร์';exportMessage.append(link);
    setTimeout(()=>URL.revokeObjectURL(url),60000);
  }finally{downloadWeather.disabled=!weatherExportState;}
};
const weatherLoaderBeforeUx=loadWeather;
loadWeather=async()=>{downloadWeather.disabled=true;weatherExportState=null;await weatherLoaderBeforeUx();downloadWeather.disabled=!weatherExportState||!chartRowsA.length;};
$('load').onclick=loadWeather;
$('pin-b').addEventListener('click',()=>context());
const invalidatorBeforeUx=invalidateWeather;
invalidateWeather=message=>{invalidatorBeforeUx(message);weatherExportState=null;downloadWeather.disabled=true;exportMessage.textContent='';};
const selectorBeforeUx=selectA;
selectA=point=>{weatherExportState=null;downloadWeather.disabled=true;exportMessage.textContent='';selectorBeforeUx(point);};
fetch('training/manifest.json').then(response=>{if(!response.ok)throw Error(response.status);return response.json();}).then(meta=>{
  const note=document.createElement('p');note.className='view-summary';note.textContent=`ชุดรายเดือน ${fmt(meta.rows,0)} แถว • ผ่านเงื่อนไข baseline ${fmt(meta.eligible_rows,0)} แถว • train ${meta.eligible_by_split.train} / validation ${meta.eligible_by_split.validation} / test ${meta.eligible_by_split.test}`;
  $('training-section').querySelector('.training-links').before(note);
}).catch(()=>{});
// Keep the province → district → soil sequence together in section 1.
document.querySelector('.report-controls').append($('overview'));
const areaButton=document.createElement('button');
areaButton.type='button';areaButton.textContent='เลือกอำเภอ / ชุดดิน';
areaButton.onclick=()=>{const details=$('district').closest('details');details.open=true;details.scrollIntoView({behavior:'smooth',block:'start'});$('district').focus();};
document.querySelector('.report-controls').append(areaButton);
const scope=document.createElement('p');scope.className='scope-note';
scope.className='warn';
scope.textContent='รายงานรายเดือน = อากาศจุดอ้างอิงจังหวัด + ผลผลิตทั้งจังหวัด • เลือกอำเภอ/ชุดดินในส่วน 1 เพื่อเปลี่ยนพื้นที่ดินและจุด A; อากาศรายเดือนไม่เปลี่ยน หากต้องการอากาศจุด A ให้เปิด “2. วันที่และอากาศ”';
document.querySelector('.report-controls').after(scope);
