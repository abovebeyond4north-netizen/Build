import {CsvError,parseCSV,transform,profile,serializeCSV,serializeJSON,reportData} from './csv-engine.js';
const $ = id=>document.getElementById(id);
const state={input:null,output:null,filename:'dataset.csv'};
const sample=`Full Name, City ,Units,Revenue,Notes\r\n Alice , Ottawa ,2,100.50, first order \r\n Bob , Toronto ,1,75, repeat customer \r\n Alice , Ottawa ,2,100.50, first order \r\n  ,  , , , \r\n Chris , Montreal ,3,150.00,"multi-line\r\ncomment"\r\n Dana , Kingston ,1,40,=2+2\r\n`;
const checks=['trimCells','normalizeHeaders','dropEmptyRows','removeDuplicates'];
function safeName(name){return String(name).replace(/\.[^.]*$/,'').replace(/[^a-zA-Z0-9_-]+/g,'_').slice(0,65)||'dataset';}
function setStatus(message,fail=false){$('status').textContent=message;$('status').classList.toggle('error',fail);}
async function ingest(text,name){
  try {
    if(new Blob([text]).size>5*1024*1024)throw new CsvError('File exceeds the 5 MB safety limit.');
    const table=parseCSV(text);
    state.input=table;state.output=null;state.filename=name;
    $('runButton').disabled=false;
    $('resultStatus').textContent='READY TO PROCESS';
    $('inputRows').textContent=table.rows.length.toLocaleString();
    $('outputRows').textContent='—';$('removedRows').textContent='—';$('columnCount').textContent=table.headers.length;
    setStatus(`Loaded ${name}: ${table.rows.length.toLocaleString()} rows and ${table.headers.length} columns.`);
    run();
  }catch(error){state.input=null;state.output=null;disableExports();$('runButton').disabled=true;
    $('resultStatus').textContent='INPUT ERROR';$('inputRows').textContent='—';$('outputRows').textContent='—';$('removedRows').textContent='—';$('columnCount').textContent='—';
    $('preview').replaceChildren(); setStatus(error.message,true);}
}
function run(){
  if(!state.input)return;
  try{
    state.output=transform(state.input,Object.fromEntries(checks.map(k=>[k,$(k).checked])));
    const output=state.output;
    $('outputRows').textContent=output.rows.length.toLocaleString();
    $('removedRows').textContent=(state.input.rows.length-output.rows.length).toLocaleString();
    $('resultStatus').textContent='TRANSFORMATION COMPLETE';
    $('columnCount').textContent=output.headers.length;
    $('previewLabel').textContent=`${output.rows.length.toLocaleString()} records`;
    renderTable(output);
    ['downloadCsv','downloadJson','downloadReport'].forEach(k=>$(k).disabled=false);
    setStatus('Processing complete. Review your data or download an export.');
  } catch(error){disableExports();setStatus(error.message,true);}
}
function renderTable(table){
  const wrap=document.createElement('div');wrap.className='table-scroll';
  const grid=document.createElement('table');grid.className='results-table';
  const thead=document.createElement('thead'),hr=document.createElement('tr');
  for(const h of table.headers){const th=document.createElement('th');th.textContent=h;hr.append(th);}
  thead.append(hr);grid.append(thead);
  const tbody=document.createElement('tbody');
  for(const row of table.rows.slice(0,12)){
    const tr=document.createElement('tr');for(const cell of row){const td=document.createElement('td');td.textContent=cell;tr.append(td);}tbody.append(tr);
  }
  grid.append(tbody);wrap.append(grid);$('preview').replaceChildren(wrap);
}
function disableExports(){['downloadCsv','downloadJson','downloadReport'].forEach(k=>$(k).disabled=true);}
function download(data,filename,mime){
  const blob=new Blob([data],{type:mime}); const url=URL.createObjectURL(blob);
  const a=document.createElement('a');a.href=url;a.download=filename;document.body.append(a);a.click();a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}
$('loadSample').addEventListener('click',()=>ingest(sample,'sample_orders.csv'));
$('runButton').addEventListener('click',run);
checks.forEach(k=>$(k).addEventListener('change',()=>{if(state.input)run();}));
$('downloadCsv').addEventListener('click',()=>state.output&&download(serializeCSV(state.output),`${safeName(state.filename)}_clean.csv`,'text/csv;charset=utf-8'));
$('downloadJson').addEventListener('click',()=>state.output&&download(serializeJSON(state.output),`${safeName(state.filename)}_clean.json`,'application/json;charset=utf-8'));
$('downloadReport').addEventListener('click',()=>state.output&&download(JSON.stringify(reportData(state.input,state.output),null,2),`${safeName(state.filename)}_report.json`,'application/json;charset=utf-8'));
$('dropZone').addEventListener('click',()=>$('fileInput').click());
$('dropZone').addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();$('fileInput').click();}});
$('fileInput').addEventListener('change',async e=>{const f=e.target.files?.[0];if(f)await handleFile(f);e.target.value='';});
async function handleFile(f){if(f.size>5*1024*1024){setStatus('File exceeds the 5 MB safety limit.',true);return;}await ingest(await f.text(),f.name);}
for(const type of ['dragover','dragenter'])$('dropZone').addEventListener(type,e=>{e.preventDefault();$('dropZone').classList.add('over');});
for(const type of ['dragleave','drop'])$('dropZone').addEventListener(type,e=>{e.preventDefault();$('dropZone').classList.remove('over');});
$('dropZone').addEventListener('drop',async e=>{const f=e.dataTransfer?.files?.[0];if(f)await handleFile(f);});
if('serviceWorker' in navigator && (location.protocol==='https:' || location.hostname==='localhost')) {
  window.addEventListener('load',()=>navigator.serviceWorker.register('/sw.js').catch(()=>{}));
}